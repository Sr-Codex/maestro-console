"""Testes do V6-S4 (cabos + rodar time em thread) — sem GTK."""

import threading
import time

from maestro.native.orchestrate import run_team_in_thread


class _FakeController:
    """Controller falso cujo run_team é async e emite StepProgress via progress()."""

    def __init__(self):
        self.steps = []

    async def run_team(self, team, intent, *, progress=None):
        from maestro.engine.orchestrator import StepProgress

        for i, role in enumerate(["coder", "reviewer"]):
            progress(StepProgress(i, role, role, "t1", "start"))
            progress(StepProgress(i, role, role, "t1", "done", state="DONE"))
        return None


def test_run_team_in_thread_emite_passos():
    ctrl = _FakeController()
    seen = []
    done = threading.Event()

    def on_step(sp):
        seen.append((sp.agent, sp.phase, sp.state))
        if sp.agent == "reviewer" and sp.phase == "done":
            done.set()

    t = run_team_in_thread(ctrl, object(), "faça algo", on_step)
    assert isinstance(t, threading.Thread)
    assert done.wait(timeout=5.0), "thread não concluiu a tempo"
    t.join(timeout=5.0)
    assert ("coder", "start", None) in seen
    assert ("reviewer", "done", "DONE") in seen


def test_run_team_in_thread_e_daemon():
    ctrl = _FakeController()
    t = run_team_in_thread(ctrl, object(), "x", lambda sp: None)
    assert t.daemon is True
    t.join(timeout=5.0)
    # pequena folga para o worker encerrar
    time.sleep(0.01)
