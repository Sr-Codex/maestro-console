"""Testes do streaming até o SSE (V5-S2): OutputBus, RunManager, session passthrough."""

import asyncio

from maestro.engine.orchestrator import OutputBus
from maestro.engine.runner import RunResult, RunStatus
from maestro.engine.session import SessionManager
from maestro.engine.state.store import Store
from maestro.web.runs import RunManager


def test_output_bus():
    got = []
    bus = OutputBus()
    bus.emit("claude", "x")  # sem assinante -> no-op
    assert got == []
    bus.set(lambda a, c: got.append((a, c)))
    bus.emit("claude", "abc")
    assert got == [("claude", "abc")]
    bus.clear()
    bus.emit("claude", "y")
    assert got == [("claude", "abc")]


def test_runmanager_liga_output_ao_sse():
    class Ctrl:
        output_bus = OutputBus()

    rm = RunManager(Ctrl())
    eventos = []
    rm.subscribe(eventos.append)
    # a engine emitiria isto ao vivo:
    Ctrl.output_bus.emit("codex", "trabalhando...")
    assert eventos == [{"type": "output", "agent": "codex", "chunk": "trabalhando..."}]


def test_session_repassa_on_output(tmp_path):
    recebido = {}

    async def fake(profile, prompt, *, workspace, session_id, resume, timeout, on_output=None):
        recebido["on_output"] = on_output
        if on_output:
            on_output("pedaço-ao-vivo")
        return RunResult(RunStatus.OK, 0, "ok", "", 0.0, False)

    chunks = []

    async def main():
        with Store(tmp_path / "m.db") as s:
            sm = SessionManager(s)
            await sm.run_in_session(
                None, "a", "t", workspace="/w", timeout=1, run_fn=fake, on_output=chunks.append
            )

    asyncio.run(main())
    assert recebido["on_output"] is not None
    assert chunks == ["pedaço-ao-vivo"]
