"""Dashboard ao vivo + coerência de task_id + cancelamento (V3-S4)."""

import asyncio
import json

from maestro.engine.orchestrator import Orchestrator
from maestro.engine.registry import Registry
from maestro.engine.state.store import Store
from maestro.engine.teams import Role, Team
from maestro.tui.controller import TUIController

TEAM = Team("t", [Role("coder", "claude", "i"), Role("reviewer", "codex", "i")])


def test_dashboard_mostra_task_id_e_duracao_durante_execucao(tmp_path):
    seen = {}

    async def ask(agent_id, prompt):
        # captura o dashboard durante a execução (no meio da cadeia)
        seen["dash"] = ctrl.dashboard_text()
        return json.dumps({"state": "DONE", "result": "ok"})

    with Store(tmp_path / "m.db") as s:
        reg = Registry(s)
        reg.register("claude", "claude-code")
        reg.register("codex", "codex")
        ctrl = TUIController(reg, s, Orchestrator(ask, store=s))
        asyncio.run(ctrl.run_team(TEAM, "go"))
        d = seen["dash"]
        assert "Tarefa ativa:" in d
        assert ctrl.last_run_id()[:8] in d  # task_id aparece na tarefa ativa
        assert "s" in d  # duração (Xs)


def test_historico_coerente_com_task_id(tmp_path):
    async def ask(agent_id, prompt):
        return json.dumps({"state": "DONE", "result": "ok"})

    with Store(tmp_path / "m.db") as s:
        ctrl = TUIController(Registry(s), s, Orchestrator(ask, store=s))
        asyncio.run(ctrl.run_team(TEAM, "go"))
        rid = ctrl.last_run_id()
        # checkpoints e log usam o MESMO task_id/run_id
        assert s.get_chain(rid)["status"] == "done"
        assert len(s.get_steps(rid)) == 2
        assert all(e["task_id"] == rid for e in s.list_envelopes())


def test_cancelamento_limpa_estado(tmp_path):
    async def ask(agent_id, prompt):
        await asyncio.sleep(5)
        return json.dumps({"state": "DONE", "result": "ok"})

    async def main():
        with Store(tmp_path / "m.db") as s:
            ctrl = TUIController(Registry(s), s, Orchestrator(ask, store=s))
            task = asyncio.create_task(ctrl.run_team(TEAM, "go"))
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            # tarefa ativa liberada; último marcado como cancelado
            assert ctrl._active is None
            assert ctrl._last["state"] == "CANCELADO"

    asyncio.run(main())
