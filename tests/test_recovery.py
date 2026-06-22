"""Testes de recuperação de cadeias (V3-S3): checkpoint, resume sem repetir."""

import asyncio
import json

from maestro.engine.orchestrator import Orchestrator
from maestro.engine.state.store import Store
from maestro.engine.teams import Role, Team

TEAM = Team(
    "t",
    [Role("coder", "claude", "i"), Role("reviewer", "codex", "i"), Role("final", "claude", "i")],
)


def test_checkpoint_e_status(tmp_path):
    async def ask(agent_id, prompt):
        return json.dumps({"state": "DONE", "result": f"r-{agent_id}"})

    async def main():
        with Store(tmp_path / "m.db") as s:
            orch = Orchestrator(ask, store=s)
            res = await orch.run_team(TEAM, "go", task_id="run1")
            assert res.ok
            steps = s.get_steps("run1")
            assert [st["idx"] for st in steps] == [0, 1, 2]
            assert all(st["state"] == "DONE" for st in steps)
            assert s.get_chain("run1")["status"] == "done"

    asyncio.run(main())


def test_falha_intermediaria_persiste_e_escala(tmp_path):
    async def ask(agent_id, prompt):
        return (
            json.dumps({"state": "BLOCKED"})
            if agent_id == "codex"
            else json.dumps({"state": "DONE", "result": "ok"})
        )

    async def main():
        with Store(tmp_path / "m.db") as s:
            orch = Orchestrator(ask, store=s)
            res = await orch.run_team(TEAM, "go", task_id="run2")
            assert res.escalated
            steps = s.get_steps("run2")
            # etapa 0 DONE, etapa 1 BLOCKED, etapa 2 nao rodou
            assert steps[0]["state"] == "DONE" and steps[1]["state"] == "BLOCKED"
            assert len(steps) == 2
            assert s.get_chain("run2")["status"] == "escalated"

    asyncio.run(main())


def test_resume_nao_repete_etapas_concluidas(tmp_path):
    chamadas = []

    # codex falha na 1a vez; apos "swap" para claude, completa
    async def ask(agent_id, prompt):
        chamadas.append(agent_id)
        if agent_id == "codex":
            return json.dumps({"state": "BLOCKED"})
        return json.dumps({"state": "DONE", "result": "ok"})

    async def main():
        with Store(tmp_path / "m.db") as s:
            orch = Orchestrator(ask, store=s)
            r1 = await orch.run_team(TEAM, "go", task_id="run3")
            assert r1.escalated
            chamadas.clear()
            # retoma trocando o agente da etapa que falhou (codex -> claude)
            r2 = await orch.resume_chain(TEAM, "go", "run3", swap_agent="claude")
            assert r2.ok
            # NAO repetiu a etapa 0 (coder/claude ja concluida): so rodou idx 1 e 2
            assert "codex" not in chamadas  # codex (etapa falha) foi trocado
            assert len(chamadas) == 2  # apenas etapas 1 (agora claude) e 2
            steps = s.get_steps("run3")
            assert [st["state"] for st in steps] == ["DONE", "DONE", "DONE"]
            assert steps[1]["agent"] == "claude"  # swap aplicado
            assert s.get_chain("run3")["status"] == "done"

    asyncio.run(main())


def test_resume_com_reprompt(tmp_path):
    prompts = []

    async def ask(agent_id, prompt):
        prompts.append(prompt)
        # falha so na 1a passada do codex; com reprompt, completa
        if agent_id == "codex" and "TENTE DE NOVO" not in prompt:
            return json.dumps({"state": "FAILED"})
        return json.dumps({"state": "DONE", "result": "ok"})

    async def main():
        with Store(tmp_path / "m.db") as s:
            orch = Orchestrator(ask, store=s)
            await orch.run_team(TEAM, "go", task_id="run4")
            prompts.clear()
            r = await orch.resume_chain(TEAM, "go", "run4", reprompt="TENTE DE NOVO")
            assert r.ok
            assert any("TENTE DE NOVO" in p for p in prompts)

    asyncio.run(main())
