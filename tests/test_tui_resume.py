"""Critério final v0.3.0 (nível controller): criar team, rodar, falhar, retomar."""

import asyncio
import json

from maestro.engine.orchestrator import Orchestrator
from maestro.engine.registry import Registry
from maestro.engine.state.store import Store
from maestro.tui.controller import TUIController


def test_criar_rodar_falhar_retomar_sem_repetir(tmp_path):
    chamadas = []

    async def ask(agent_id, prompt):
        chamadas.append(agent_id)
        if agent_id == "codex":
            return json.dumps({"state": "BLOCKED"})  # falha intermediária
        return json.dumps({"state": "DONE", "result": "ok"})

    with Store(tmp_path / "m.db") as s:
        ctrl = TUIController(Registry(s), s, Orchestrator(ask, store=s))
        # 1) criar team pela TUI (controller)
        ctrl.save_team(
            "fluxo",
            [("coder", "claude", "impl"), ("reviewer", "codex", "rev"), ("final", "claude", "fim")],
        )
        team = ctrl.get_team("fluxo")
        # 2) executar -> falha no reviewer(codex)
        r1 = asyncio.run(ctrl.run_team(team, "construir X"))
        assert r1.escalated and ctrl.can_resume()
        run_id = ctrl.last_run_id()
        assert s.get_chain(run_id)["status"] == "escalated"

        # 3) retomar trocando o agente da etapa falha (codex -> claude)
        chamadas.clear()
        r2 = asyncio.run(ctrl.resume_last(swap_agent="claude"))
        assert r2.ok
        # 4) NAO repetiu a etapa 0 (coder ja DONE): so rodaram idx 1 e 2
        assert len(chamadas) == 2
        assert "codex" not in chamadas  # etapa falha foi trocada
        steps = s.get_steps(run_id)
        assert [st["state"] for st in steps] == ["DONE", "DONE", "DONE"]
        assert steps[1]["agent"] == "claude"
        assert s.get_chain(run_id)["status"] == "done"
        assert not ctrl.can_resume()  # nada mais a retomar
