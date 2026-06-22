"""Testes do agent-to-note (V9-S4) — fluxo nota->agente->nota, sem GTK."""

import asyncio
import threading

from maestro.engine.envelope import Envelope, EnvelopeState
from maestro.engine.notes import Notes
from maestro.engine.state.store import Store
from maestro.native.orchestrate import run_note_to_agent, run_note_to_agent_in_thread


def _env(state, result=None):
    return Envelope(
        sender="claude", recipient="orchestrator", message_id="m1", state=state, result=result
    )


class _Ctrl:
    def __init__(self, env):
        self._env = env
        self.calls = []

    async def delegate(self, agent_id, task):
        self.calls.append((agent_id, task))
        return self._env


def _notes(tmp_path):
    store = Store(tmp_path / "m.db")
    return Notes(store), store


def test_nota_alimenta_prompt_e_resposta_volta(tmp_path):
    n, store = _notes(tmp_path)
    note = n.create("Tarefa", "faça X", x=0, y=0)
    ctrl = _Ctrl(_env(EnvelopeState.DONE, result="feito Y"))
    env, updated = asyncio.run(run_note_to_agent(ctrl, note, "claude", n))
    assert ctrl.calls == [("claude", "faça X")]  # corpo da nota -> prompt
    assert updated
    persisted = n.get(note.id).body
    assert "faça X" in persisted and "## resposta de claude" in persisted and "feito Y" in persisted
    store.close()


def test_nao_done_nao_altera_nota(tmp_path):
    n, store = _notes(tmp_path)
    note = n.create("T", "corpo original")
    ctrl = _Ctrl(_env(EnvelopeState.BLOCKED, result=None))
    env, updated = asyncio.run(run_note_to_agent(ctrl, note, "claude", n))
    assert not updated
    assert n.get(note.id).body == "corpo original"  # intacta
    store.close()


def test_corpo_vazio_usa_titulo(tmp_path):
    n, store = _notes(tmp_path)
    note = n.create("Pergunta", "")
    ctrl = _Ctrl(_env(EnvelopeState.DONE, result="resposta"))
    asyncio.run(run_note_to_agent(ctrl, note, "claude", n))
    assert ctrl.calls[0] == ("claude", "Pergunta")  # corpo vazio -> título
    store.close()


def test_in_thread(tmp_path):
    n, store = _notes(tmp_path)
    note = n.create("T", "x")
    ctrl = _Ctrl(_env(EnvelopeState.DONE, result="ok"))
    done = threading.Event()
    box = {}

    def on_done(env, updated, nt):
        box["updated"] = updated
        done.set()

    t = run_note_to_agent_in_thread(ctrl, note, "claude", n, on_done)
    assert isinstance(t, threading.Thread)
    assert done.wait(timeout=5.0)
    assert box["updated"] is True
    assert "ok" in n.get(note.id).body
    store.close()
