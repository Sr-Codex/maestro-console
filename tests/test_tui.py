"""Testes do TUI controller (E4-S2). O loop (app.run) é só render fino."""

import asyncio

from maestro.engine.orchestrator import Orchestrator
from maestro.engine.registry import AgentState, Registry
from maestro.engine.state.store import Store
from maestro.tui.controller import TUIController


def _build(tmp_path, ask):
    s = Store(tmp_path / "m.db")
    reg = Registry(s)
    orch = Orchestrator(ask, store=s)
    return s, TUIController(reg, s, orch), reg


def test_agents_text(tmp_path):
    async def ask(a, p):
        return ""

    s, ctrl, reg = _build(tmp_path, ask)
    try:
        assert "nenhum agente" in ctrl.agents_text()
        reg.register("claude", "claude-code", state=AgentState.IDLE)
        txt = ctrl.agents_text()
        assert "claude" in txt and "idle" in txt
    finally:
        s.close()


def test_history_text(tmp_path):
    async def ask(a, p):
        return ""

    s, ctrl, _ = _build(tmp_path, ask)
    try:
        assert "sem histórico" in ctrl.history_text()
    finally:
        s.close()


def test_delegate(tmp_path):
    import json

    async def ask(agent_id, prompt):
        return json.dumps({"state": "DONE", "result": "ok"})

    s, ctrl, _ = _build(tmp_path, ask)
    try:
        env = asyncio.run(ctrl.delegate("claude", "faça"))
        assert str(env.state) == "DONE" and env.result == "ok"
        # delegate logou no store -> aparece no historico
        assert "DONE" in ctrl.history_text()
    finally:
        s.close()


def test_app_importavel():
    from maestro.tui import app

    assert hasattr(app, "run")
