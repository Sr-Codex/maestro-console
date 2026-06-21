"""Observabilidade integrada (V2-S5): logbook por etapa no orquestrador."""

import asyncio
import json

from maestro.bootstrap import log_path
from maestro.engine.logbook import Logbook
from maestro.engine.orchestrator import Orchestrator
from maestro.engine.teams import Role, Team


def test_delegate_loga_task_agente_estado_duracao(tmp_path):
    lb = Logbook(tmp_path / "h.log")

    async def ask(agent_id, prompt):
        return json.dumps({"state": "DONE", "result": "ok"})

    async def main():
        orch = Orchestrator(ask, logbook=lb)
        await orch.delegate("claude", "faça", task_id="abcd1234xyz")

    asyncio.run(main())
    lines = lb.lines()
    assert len(lines) == 1
    assert "abcd1234" in lines[0]  # task_id (8)
    assert "claude -> DONE" in lines[0]
    assert "s)" in lines[0]  # duração


def test_run_team_loga_por_etapa(tmp_path):
    lb = Logbook(tmp_path / "h.log")

    async def ask(agent_id, prompt):
        return json.dumps({"state": "DONE", "result": "r"})

    team = Team("t", [Role("coder", "claude", "i"), Role("reviewer", "codex", "i")])

    async def main():
        await Orchestrator(ask, logbook=lb).run_team(team, "x")

    asyncio.run(main())
    lines = lb.lines()
    assert len(lines) == 2
    assert any("claude -> DONE" in ln for ln in lines)
    assert any("codex -> DONE" in ln for ln in lines)


def test_log_path_sob_home(tmp_path):
    assert log_path(tmp_path) == tmp_path / "logs" / "handoffs.log"
