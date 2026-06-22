"""Testes dos helpers de routines do canvas (V10-S4) — sem GTK."""

import threading

from maestro.engine.envelope import Envelope, EnvelopeState
from maestro.engine.routines import Routines
from maestro.engine.state.store import Store
from maestro.native.orchestrate import run_one_routine_in_thread, run_routines_tick_in_thread
from maestro.native.routines_ui import parse_steps, routine_rows


class _Ctrl:
    async def delegate(self, agent_id, task):
        return Envelope(
            sender=agent_id, recipient="orchestrator", message_id="m", state=EnvelopeState.DONE
        )


def test_parse_steps():
    assert parse_steps("a && b && c") == ["a", "b", "c"]
    assert parse_steps("só um") == ["só um"]
    assert parse_steps("  &&  ") == []


def test_routine_rows(tmp_path):
    store = Store(tmp_path / "m.db")
    rs = Routines(store)
    rs.create("ci", "claude", ["p"], interval_s=30)
    row = routine_rows(rs)[0]
    assert row["name"] == "ci" and row["enabled"] is True and row["run_count"] == 0
    assert "ci" in row["label"] and "on" in row["label"]
    store.close()


def test_run_one_routine_in_thread(tmp_path):
    store = Store(tmp_path / "m.db")
    rs = Routines(store)
    r = rs.create("x", "claude", ["p1", "p2"], 60)
    done = threading.Event()
    box = {}

    def on_done(run):
        box["ok"] = run.ok
        done.set()

    run_one_routine_in_thread(_Ctrl(), r, rs, on_done)
    assert done.wait(timeout=5.0)
    assert box["ok"] is True
    assert rs.get(r.id).run_count == 1
    store.close()


def test_run_routines_tick_in_thread_dispara_vencidas(tmp_path):
    store = Store(tmp_path / "m.db")
    rs = Routines(store)
    r = rs.create("x", "claude", ["p"], interval_s=1)  # nunca rodou -> vence
    done = threading.Event()
    box = {}

    def on_done(fired):
        box["fired"] = fired
        done.set()

    run_routines_tick_in_thread(_Ctrl(), rs, on_done)
    assert done.wait(timeout=5.0)
    assert box["fired"] == [r.id]
    assert rs.get(r.id).run_count == 1
    store.close()
