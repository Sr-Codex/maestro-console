"""Contas por nó (docs/31/ADR-28) — resolvedor, argv, sandbox, usage, sessões.

Gi-free. Cobre as emendas do Fable que são LÓGICA (as de UI ficam no
test_accounts_ui.py): E1 (rw_paths por SUBSTITUIÇÃO — o ~/.claude do dono NÃO fica rw
no nó de conta), E5 (máscara tmpfs ANTES do bind da própria conta; vale pra nó default),
E6 (precedência: env do nó vence o da conta), §5.2 (associação órfã NUNCA cai calada
pro default), E3 (leitores de sessão seguem o config-dir) e E4 (headless resolve conta).
"""

from __future__ import annotations

import asyncio
import json

import pytest

from maestro.engine import accounts as acc
from maestro.engine import sandbox
from maestro.engine.adapters.base import load_profiles
from maestro.engine.agent_run import run_agent
from maestro.engine.orphans import detect_orphans
from maestro.engine.session_capture import newest_session_id, project_dir
from maestro.engine.state.store import Store
from maestro.engine.usage import usage_from_session
from maestro.native.agents import agent_argv
from maestro.native.state import CanvasModel


def _pair_index(args, flag, value):
    """Índice da OCORRÊNCIA de (flag, value) — o wrap já tem um --tmpfs /tmp base."""
    for i, a in enumerate(args):
        if a == flag and i + 1 < len(args) and args[i + 1] == value:
            return i
    return -1


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def _acct(tmp_path, name="trabalho", agent="claude", env=""):
    return acc.Account(name=name, agent=agent, slug=acc.slugify(name), env=env,
                       root=tmp_path / "accounts")


# --- básicos: slug / var / env ---------------------------------------------


def test_slugify_e_env_var():
    assert acc.slugify("Conta de Trabalho!") == "conta-de-trabalho"
    assert acc.slugify("  ") == "conta"  # nunca slug vazio
    assert acc.env_var_for("claude") == "CLAUDE_CONFIG_DIR"
    assert acc.env_var_for("codex") == "CODEX_HOME"


def test_parse_env_ignora_comentario_e_linha_solta():
    env = acc.parse_env("A=1\n# B=2\nsem-igual\nC = x y ")
    assert env == {"A": "1", "C": "x y"}


def test_sandbox_env_precedencia_no_vence_conta(tmp_path):
    # E6: chave definida no env POR NÓ é OMITIDA do setenv da conta
    a = _acct(tmp_path, env="FOO=conta\nBAR=2")
    out = a.sandbox_env(skip=frozenset({"FOO"}))
    assert "FOO" not in out and out["BAR"] == "2"
    assert out["CLAUDE_CONFIG_DIR"] == str(a.config_dir())


# --- registro (Store) --------------------------------------------------------


def test_add_find_remove_roundtrip(store, tmp_path):
    root = tmp_path / "accounts"
    a = acc.add_account(store, "trabalho", "claude", root=root)
    assert a is not None and a.config_dir().is_dir()  # mkdir no add
    assert acc.add_account(store, "trabalho", "claude", root=root) is None  # dup
    assert acc.add_account(store, "  ", "claude", root=root) is None  # vazio
    found = acc.find_account(store, "trabalho", "claude", root=root)
    assert found is not None and found.slug == "trabalho"
    assert acc.remove_account(store, "trabalho", "claude", root=root) is True
    assert acc.find_account(store, "trabalho", root=root) is None
    assert acc.remove_account(store, "trabalho", "claude", root=root) is False
    # o dir FICA no disco (credencial não se apaga por engano — §4.1)
    assert a.config_dir().is_dir()


def test_slug_colide_ganha_sufixo(store, tmp_path):
    root = tmp_path / "accounts"
    a1 = acc.add_account(store, "Trabalho", "claude", root=root)
    a2 = acc.add_account(store, "trabalho!", "claude", root=root)  # mesmo slug base
    assert a1 is not None and a2 is not None
    assert a1.slug != a2.slug  # dirs distintos


# --- resolução nó → conta (invariante §5.2) ---------------------------------


def test_resolve_default_sem_conta(store):
    assert acc.resolve(store, "claude-2", "claude") is None
    assert acc.resolve(None, "claude-2", "claude") is None  # store ausente = default


def test_resolve_conta_registrada(store, tmp_path):
    root = tmp_path / "accounts"
    acc.add_account(store, "trabalho", "claude", root=root)
    store.set_ui("nodecfg_claude-2_account", "trabalho")
    a = acc.resolve(store, "claude-2", "claude", root=root)
    assert a is not None and a.name == "trabalho"


def test_resolve_associacao_orfa_nunca_cai_pro_default(store, tmp_path):
    # §5.2: nó aponta conta que sumiu do registro → sintetiza (CLI pedirá login),
    # NUNCA devolve None (que significaria rodar calado na conta do dono).
    store.set_ui("nodecfg_claude-2_account", "fantasma")
    a = acc.resolve(store, "claude-2", "claude", root=tmp_path / "accounts")
    assert a is not None and a.slug == "fantasma"
    # sem agent-base conhecido não há como derivar var/dir → None documentado
    assert acc.resolve(store, "claude-2", None, root=tmp_path / "accounts") is None


def test_c7_base_desambigua_homonimos_config_dir(store, tmp_path):
    """C7 (review docs/33): contas HOMÔNIMAS em agentes diferentes têm config_dir DISTINTO
    — resolver depende do `agent` base. O `_acct_cfg_dir` da detecção de órfão TEM de passar
    o base (como os outros 4 pontos): sem ele, o transcript no dir da conta certa não é achado
    e o nó de crash não é marcado órfão (perda de recuperação)."""
    root = tmp_path / "accounts"
    acc.add_account(store, "trabalho", "claude", root=root)
    acc.add_account(store, "trabalho", "codex", root=root)  # mesmo nome, outro agente
    store.set_ui("nodecfg_claude-2_account", "trabalho")
    a_claude = acc.resolve(store, "claude-2", "claude", root=root)
    a_codex = acc.resolve(store, "claude-2", "codex", root=root)
    assert a_claude is not None and a_claude.agent == "claude"
    assert a_codex is not None and a_codex.agent == "codex"
    # o base MUDA o dir → um caller que o omite (o bug C7) não tem como acertar
    assert a_claude.config_dir() != a_codex.config_dir()


# --- sandbox: máscara tmpfs (E5) + substituição (E1) -------------------------


def test_wrap_mask_antes_do_bind_da_propria_conta(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    root = tmp_path / "accounts"
    own = root / "claude" / "trabalho"
    own.mkdir(parents=True)
    ws = tmp_path / "ws"
    ws.mkdir()
    args = sandbox.wrap(["cli"], workspace=ws, rw_paths=[str(own)],
                        mask_paths=[str(root)])
    i_mask = _pair_index(args, "--tmpfs", str(root))
    i_bind = _pair_index(args, "--bind", str(own))
    assert i_mask != -1 and i_bind != -1
    assert i_mask < i_bind  # ordem de mount: tmpfs esconde, bind reaparece por cima


def test_wrap_mask_inexistente_e_pulada(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    monkeypatch.setenv("MAESTRO_HOME", str(tmp_path))  # isola: sem <home>/ask-bus/box real (S1)
    ws = tmp_path / "ws"
    ws.mkdir()
    args = sandbox.wrap(["cli"], workspace=ws, mask_paths=[str(tmp_path / "nao-existe")])
    assert "--tmpfs" not in args[args.index("/tmp") + 1:]  # só o /tmp base


def test_agent_argv_conta_substitui_rw_e_seta_var(tmp_path, monkeypatch):
    # E1: com conta, ~/.claude NÃO é montado rw; só o config-dir da conta.
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    prof = load_profiles()["claude"]
    a = _acct(tmp_path, env="EXTRA=1")
    ws = tmp_path / "ws"
    ws.mkdir()
    args = agent_argv(prof, str(ws), account=a)
    joined = " ".join(args)
    assert str(a.config_dir()) in joined
    for p in prof.rw_paths:  # nenhum path default do adapter montado rw (E1)
        assert f"--bind {p}" not in joined
    assert "--setenv CLAUDE_CONFIG_DIR" in joined
    assert "--setenv EXTRA 1" in joined
    # raiz mascarada ANTES do bind da própria conta (E5)
    i_mask = _pair_index(args, "--tmpfs", str(a.root))
    i_bind = _pair_index(args, "--bind", str(a.config_dir()))
    assert i_mask != -1 and i_bind != -1 and i_mask < i_bind


def test_agent_argv_no_default_tambem_mascara(tmp_path, monkeypatch):
    # E5c: nó default não lê credencial das contas — raiz mascarada mesmo sem conta.
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    root = tmp_path / "accounts"
    root.mkdir()
    monkeypatch.setattr(acc, "accounts_root", lambda: root)
    prof = load_profiles()["claude"]
    ws = tmp_path / "ws"
    ws.mkdir()
    args = agent_argv(prof, str(ws))
    assert _pair_index(args, "--tmpfs", str(root)) != -1


def test_agent_argv_e6_no_vence_conta(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    prof = load_profiles()["claude"]
    a = _acct(tmp_path, env="FOO=conta")
    ws = tmp_path / "ws"
    ws.mkdir()
    args = agent_argv(prof, str(ws), account=a, node_env_keys=frozenset({"FOO"}))
    assert "--setenv FOO" not in " ".join(args)  # conta omite o que o nó define


# --- headless (E4): run_agent troca rw_paths e injeta a var ------------------


def test_run_agent_headless_usa_conta(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    captured: dict = {}

    async def fake_headless(argv, *, timeout, on_output=None):
        captured["argv"] = argv

    monkeypatch.setattr("maestro.engine.agent_run.run_headless", fake_headless)
    prof = load_profiles()["claude"]
    a = _acct(tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir()
    asyncio.run(run_agent(prof, "oi", workspace=ws, timeout=5, account=a))
    joined = " ".join(captured["argv"])
    assert str(a.config_dir()) in joined
    assert "--setenv CLAUDE_CONFIG_DIR" in joined
    for p in prof.rw_paths:
        assert f"--bind {p}" not in joined  # E1 também no headless


# --- leitores de sessão seguem a conta (E3 / §5.5) ---------------------------


def _claude_jsonl(cfg_dir, ws, sid):
    pdir = project_dir(ws, config_dir=cfg_dir)
    pdir.mkdir(parents=True, exist_ok=True)
    line = {"type": "assistant",
            "message": {"model": "claude-sonnet-5",
                        "usage": {"input_tokens": 10, "output_tokens": 5}}}
    (pdir / f"{sid}.jsonl").write_text(json.dumps(line) + "\n", encoding="utf-8")


def test_usage_from_session_config_dir(tmp_path):
    cfg = tmp_path / "accounts" / "claude" / "trabalho"
    ws = str(tmp_path / "ws" / "n1")
    _claude_jsonl(cfg, ws, "sid-1")
    assert usage_from_session("claude", "sid-1") is None  # default não vê a conta
    u = usage_from_session("claude", "sid-1", config_dir=str(cfg))
    assert u is not None and u.output_tokens == 5


def test_newest_session_id_config_dir(tmp_path):
    cfg = tmp_path / "accounts" / "claude" / "trabalho"
    ws = str(tmp_path / "ws" / "n1")
    _claude_jsonl(cfg, ws, "sid-2")
    assert newest_session_id(ws, home=tmp_path / "home") is None
    assert newest_session_id(ws, config_dir=str(cfg)) == "sid-2"


def test_detect_orphans_config_dir_for(tmp_path):
    cfg = tmp_path / "accounts" / "claude" / "trabalho"
    ws = str(tmp_path / "ws")
    _claude_jsonl(cfg, f"{ws}/claude-2", "sid-3")
    m = CanvasModel(Store(tmp_path / "m.db"))
    roster = [{"nid": "claude-2", "kind": "agent", "base": "claude"}]
    home = tmp_path / "home"  # sem transcript no default
    assert detect_orphans(m, roster, crashed=True, ws_base=ws, home=home) == []
    out = detect_orphans(m, roster, crashed=True, ws_base=ws, home=home,
                         config_dir_for=lambda nid: str(cfg))
    assert out == ["claude-2"]
    assert m.node_cfg("claude-2", "session") == "sid-3"


def test_store_delete_session(store):
    store.set_session("claude-2", "sid-x")
    store.delete_session("claude-2")
    assert store.get_session("claude-2") is None
    store.delete_session("nunca-existiu")  # idempotente
