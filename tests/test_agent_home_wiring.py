"""ADR-31: a fiação da camada descartável em TODAS as entradas (gi-free, roda no CI).

O `wrap()` é provado sob bwrap real em `test_agent_home_sandbox.py`; aqui, que cada
caminho de spawn entrega o id certo: interativo (`agent_argv`), headless
(`run_in_session` → `run_agent`), nó de CONTA (nunca recebe a credencial do dono), o
leitor de custo do Codex (sessões por nó) e o `floors` (projeto na config é recusado).
"""

import asyncio
from types import SimpleNamespace

import pytest

from maestro.engine import agent_home, agent_run, floors
from maestro.engine import orchestrator as orch_mod
from maestro.engine.accounts import Account
from maestro.engine.adapters.base import load_profiles
from maestro.engine.runner import RunResult, RunStatus
from maestro.engine.session import SessionManager
from maestro.engine.state.store import Store
from maestro.native import agents


def _captura(monkeypatch, mod, attr):
    seen = {}

    def fake(argv, **kw):
        seen.update(kw)
        return ["bwrap", "--", *argv]

    monkeypatch.setattr(mod, attr, fake)
    return seen


@pytest.mark.parametrize("com_conta", [False, True])
def test_interativo_passa_o_no_e_conta_nao_recebe(monkeypatch, tmp_path, com_conta):
    seen = _captura(monkeypatch, agents, "sandbox_wrap")
    acct = Account("c", "claude", "c", root=tmp_path) if com_conta else None
    agents.agent_argv(load_profiles()["claude"], str(tmp_path), node="claude-2",
                      ask_bus_dir=str(tmp_path / "bus"), account=acct)
    assert seen["node"] == (None if com_conta else "claude-2")


@pytest.mark.parametrize("com_conta", [False, True])
def test_headless_passa_o_no_e_conta_nao_recebe(monkeypatch, tmp_path, com_conta):
    seen = _captura(monkeypatch, agent_run, "sandbox_wrap")

    async def fake_headless(argv, **kw):
        return RunResult(RunStatus.OK, 0, "ok", "", 0.0, False)

    monkeypatch.setattr(agent_run, "run_headless", fake_headless)
    acct = Account("c", "claude", "c", root=tmp_path) if com_conta else None
    with Store(tmp_path / "m.db") as store:
        sm = SessionManager(store)
        asyncio.run(sm.run_in_session(load_profiles()["claude"], "claude-7", "oi",
                                      workspace=str(tmp_path), timeout=5, account=acct))
    assert seen["node"] == (None if com_conta else "claude-7")


def test_custo_do_codex_le_as_sessoes_do_no(monkeypatch, tmp_path):
    vistos = []
    monkeypatch.setattr(orch_mod, "usage_from_session",
                        lambda name, sid, config_dir=None: vistos.append(config_dir))

    class FakeSM:
        async def run_in_session(self, profile, agent_id, prompt, **kw):
            return SimpleNamespace(stdout="ok")

        def session_id(self, agent_id):
            return "sid"

    ask = orch_mod.make_agent_ask(FakeSM(), {"codex-3": SimpleNamespace(name="codex")},
                                  SimpleNamespace(create=lambda a: str(tmp_path)),
                                  timeout=5, on_usage=lambda *_: None)
    asyncio.run(ask("codex-3", "oi"))
    assert vistos == [str(agent_home.codex_home("codex-3"))]


def test_floor_recusa_projeto_dentro_da_config_do_cli():
    roots = floors._profile_rw_roots()
    assert (agent_home.user_home() / ".claude").resolve() in roots
    assert (agent_home.user_home() / ".codex").resolve() in roots


def test_perfis_nao_pedem_mais_config_rw():
    for nome in ("claude", "codex"):
        assert not [p for p in load_profiles()[nome].rw_paths if agent_home.is_protected(p)]
