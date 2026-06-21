"""VS-1 / E3-S5 — confiabilidade em TAREFA REAL de codificação — opt-in.

    MAESTRO_LIVE=1 .venv/bin/pytest tests/test_realtask_live.py
A (claude) escreve uma função real no seu workspace; verificamos OBJETIVAMENTE
executando a função. Mede a QUALIDADE da tarefa do agente (além do encanamento).
N pequeno por padrão (custo de tokens); ajuste com REALTASK_N.
"""

import asyncio
import importlib.util
import os
import tempfile

import pytest

from maestro.engine.adapters.base import load_profiles
from maestro.engine.orchestrator import Orchestrator, Step, make_agent_ask
from maestro.engine.sandbox import bwrap_available
from maestro.engine.session import SessionManager
from maestro.engine.state.store import Store
from maestro.engine.workspace import Workspace

pytestmark = pytest.mark.skipif(
    os.environ.get("MAESTRO_LIVE") != "1" or not bwrap_available(),
    reason="live: requer MAESTRO_LIVE=1 e bwrap",
)

N = int(os.environ.get("REALTASK_N", "3"))


def _is_prime_ok(path: str) -> bool:
    spec = importlib.util.spec_from_file_location("prime_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    f = mod.is_prime
    return f(7) is True and f(8) is False and f(2) is True and f(1) is False


async def _one_run(tmp_path, idx: int) -> bool:
    with Store(tmp_path / f"db{idx}.db") as s:
        sm = SessionManager(s)
        ws = Workspace(tempfile.mkdtemp(prefix="ws_"))
        orch = Orchestrator(
            make_agent_ask(sm, {"claude": load_profiles()["claude"]}, ws, timeout=180), store=s
        )
        res = await orch.run_chain(
            [
                Step(
                    "claude",
                    lambda _p: (
                        "Escreva uma funcao Python is_prime(n) CORRETA no arquivo prime.py "
                        "no diretorio atual (codigo completo). Depois responda com result='ok'."
                    ),
                ),
            ]
        )
        target = ws.path("claude") / "prime.py"
        if not (res.ok and target.exists()):
            return False
        try:
            return _is_prime_ok(str(target))
        except Exception:
            return False


def test_tarefa_real_confiabilidade(tmp_path):
    ok = sum(asyncio.run(_one_run(tmp_path, i)) for i in range(N))
    print(f"\nVS-1 tarefa real: {ok}/{N} = {100 * ok / N:.0f}%")
    assert ok >= 1  # evidência mínima de viabilidade em tarefa real
