"""Testes de run_team (V2-S2): progresso por etapa, escalação e cancelamento."""

import asyncio
import json

from maestro.engine.orchestrator import Orchestrator
from maestro.engine.teams import Role, Team


def _done(result):
    return json.dumps({"state": "DONE", "result": result})


def test_run_team_progresso_e_encaminhamento():
    events = []

    async def ask(agent_id, prompt):
        # encaminha: extrai "entrada: N" e soma 1 (ou 0)
        import re

        m = re.search(r"entrada: (\d+)", prompt)
        return _done(str((int(m.group(1)) if m else 0) + 1))

    team = Team("t", [Role("coder", "claude", "i"), Role("reviewer", "codex", "i")])

    async def main():
        orch = Orchestrator(ask)
        return await orch.run_team(team, "0", on_step=events.append)

    res = asyncio.run(main())
    assert res.ok
    assert [e.result for e in res.envelopes] == ["1", "2"]
    # progresso: start+done por papel, mesmo task_id
    phases = [(e.role, e.phase) for e in events]
    assert phases == [
        ("coder", "start"),
        ("coder", "done"),
        ("reviewer", "start"),
        ("reviewer", "done"),
    ]
    assert len({e.task_id for e in events}) == 1
    done_events = [e for e in events if e.phase == "done"]
    assert all(e.state == "DONE" and e.duration_s >= 0 for e in done_events)


def test_run_team_escala_e_para():
    async def ask(agent_id, prompt):
        return json.dumps({"state": "BLOCKED"}) if agent_id == "codex" else _done("1")

    team = Team(
        "t",
        [Role("coder", "claude", "i"), Role("reviewer", "codex", "i"), Role("x", "claude", "i")],
    )

    async def main():
        return await Orchestrator(ask).run_team(team, "go")

    res = asyncio.run(main())
    assert res.escalated and len(res.envelopes) == 2  # parou no reviewer
    assert "BLOCKED" in res.reason


def test_run_team_cancelavel():
    started = []

    async def ask(agent_id, prompt):
        started.append(agent_id)
        await asyncio.sleep(5)  # trava; será cancelado
        return _done("1")

    team = Team("t", [Role("a", "claude", "i"), Role("b", "codex", "i")])

    async def main():
        orch = Orchestrator(ask)
        task = asyncio.create_task(orch.run_team(team, "go"))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return "cancelled"
        return "nao-cancelou"

    assert asyncio.run(main()) == "cancelled"
    assert started == ["claude"]  # só a 1ª etapa começou; a 2ª não rodou
