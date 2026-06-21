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


# -- V2-S3: dashboard + run_team --------------------------------------
import json  # noqa: E402

from maestro.engine.teams import Role, Team  # noqa: E402


def test_dashboard_inicial(tmp_path):
    async def ask(a, p):
        return ""

    s, ctrl, reg = _build(tmp_path, ask)
    try:
        reg.register("claude", "claude-code", state=AgentState.IDLE)
        d = ctrl.dashboard_text()
        assert "dashboard" in d
        assert "claude" in d
        assert "Tarefa ativa: (nenhuma)" in d
        assert "Último resultado: (nenhum)" in d
    finally:
        s.close()


def test_run_team_atualiza_dashboard_e_estados(tmp_path):
    async def ask(agent_id, prompt):
        return json.dumps({"state": "DONE", "result": f"r-{agent_id}"})

    s, ctrl, reg = _build(tmp_path, ask)
    try:
        reg.register("claude", "claude-code")
        reg.register("codex", "codex")
        team = Team("t", [Role("coder", "claude", "i"), Role("reviewer", "codex", "i")])
        res = asyncio.run(ctrl.run_team(team, "faça"))
        assert res.ok
        d = ctrl.dashboard_text()
        assert "coder(claude) → reviewer(codex)" in d
        assert "-> DONE" in d
        # agentes voltaram a idle após DONE
        assert ctrl._registry.get("claude").state is AgentState.IDLE
        assert ctrl._registry.get("codex").state is AgentState.IDLE
    finally:
        s.close()


def test_run_team_escala_marca_agente(tmp_path):
    async def ask(agent_id, prompt):
        return (
            json.dumps({"state": "BLOCKED"})
            if agent_id == "codex"
            else json.dumps({"state": "DONE", "result": "1"})
        )

    s, ctrl, reg = _build(tmp_path, ask)
    try:
        reg.register("claude", "claude-code")
        reg.register("codex", "codex")
        team = Team("t", [Role("coder", "claude", "i"), Role("reviewer", "codex", "i")])
        res = asyncio.run(ctrl.run_team(team, "go"))
        assert res.escalated
        assert "ESCALOU" in ctrl.dashboard_text()
        assert ctrl._registry.get("codex").state is AgentState.BLOCKED
    finally:
        s.close()
