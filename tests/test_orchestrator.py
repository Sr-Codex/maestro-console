"""Testes do Orchestrator (E3-S4): handoff A->B->A, encaminhamento e escalação."""

import asyncio
import json

from maestro.engine.orchestrator import Orchestrator, Step
from maestro.engine.state.store import Store


def _env(state="DONE", result="0"):
    return json.dumps({"state": state, "result": result})


def test_handoff_encaminha_resultado():
    """A produz, B recebe o result de A, A2 recebe o de B (cadeia +1 cada)."""
    seen_prompts = []

    async def ask(agent_id, prompt):
        seen_prompts.append((agent_id, prompt))
        # incrementa o valor após "valor=" no prompt (ou 0)
        import re

        m = re.search(r"valor=(\d+)", prompt)
        val = int(m.group(1)) if m else 0
        return _env(result=str(val + 1))

    steps = [
        Step("claude", lambda prev: f"valor={prev or 0}"),
        Step("codex", lambda prev: f"valor={prev}"),
        Step("claude", lambda prev: f"valor={prev}"),
    ]

    async def main():
        orch = Orchestrator(ask)
        return await orch.run_chain(steps)

    res = asyncio.run(main())
    assert res.ok and not res.escalated
    assert len(res.envelopes) == 3
    # encaminhamento real: 0 ->1 ->2 ->3
    assert [e.result for e in res.envelopes] == ["1", "2", "3"]
    assert [a for a, _ in seen_prompts] == ["claude", "codex", "claude"]


def test_escalacao_em_estado_nao_done():
    async def ask(agent_id, prompt):
        return _env(state="BLOCKED", result=None) if agent_id == "codex" else _env(result="1")

    steps = [
        Step("claude", lambda prev: "t1"),
        Step("codex", lambda prev: "t2"),
        Step("claude", lambda prev: "t3"),  # não deve rodar
    ]

    async def main():
        return await Orchestrator(ask).run_chain(steps)

    res = asyncio.run(main())
    assert res.escalated is True
    assert len(res.envelopes) == 2  # parou no codex, não travou
    assert "BLOCKED" in res.reason


def test_delegate_loga_no_store(tmp_path):
    async def ask(agent_id, prompt):
        return _env(result="42")

    async def main():
        with Store(tmp_path / "m.db") as s:
            orch = Orchestrator(ask, store=s)
            await orch.delegate("claude", "faça")
            assert s.count_envelopes() == 1

    asyncio.run(main())


def test_chains_concorrentes_nao_interferem():
    async def ask(agent_id, prompt):
        await asyncio.sleep(0.01)
        return _env(result="1")

    async def main():
        orch = Orchestrator(ask)
        steps = [Step("a", lambda p: "x"), Step("b", lambda p: "y")]
        results = await asyncio.gather(*[orch.run_chain(steps) for _ in range(5)])
        return results

    results = asyncio.run(main())
    assert all(r.ok and len(r.envelopes) == 2 for r in results)
