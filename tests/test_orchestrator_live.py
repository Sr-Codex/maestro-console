"""Handoff A->B->A REAL via stack completo (E3-S4) — opt-in.

    MAESTRO_LIVE=1 .venv/bin/pytest tests/test_orchestrator_live.py
A mecânica (cadeia A->B->A) já foi validada 100%/30 na Fase 0.1 (headless);
aqui confirmamos o ORQUESTRADOR de produto end-to-end (sessão+sandbox+envelope).
"""

import asyncio
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


def test_cadeia_real_claude_codex_claude(tmp_path):
    profs = load_profiles()
    agents = {"claude": profs["claude"], "codex": profs["codex"]}

    async def main():
        with Store(tmp_path / "m.db") as s:
            sm = SessionManager(s)
            ws = Workspace(tempfile.mkdtemp(prefix="maestro_ws_"))
            ask = make_agent_ask(sm, agents, ws, timeout=150)
            orch = Orchestrator(ask, store=s)
            steps = [
                Step("claude", lambda p: "Quanto e 1000 mais 1? O result e o numero."),
                Step("codex", lambda p: f"Quanto e {p} mais 1? O result e o numero."),
                Step("claude", lambda p: f"Quanto e {p} mais 1? O result e o numero."),
            ]
            return await orch.run_chain(steps)

    res = asyncio.run(main())
    assert res.ok, f"escalou: {res.reason}"
    assert "1003" in (res.envelopes[-1].result or "")
