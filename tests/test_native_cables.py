"""Testes do V6-S4 (cabos + rodar time em thread) — sem GTK."""

import threading
import time

from maestro.native.orchestrate import run_team_in_thread
from maestro.native.state import cable_segments


def test_cable_segments_liga_consecutivos():
    # boxes = (x, y, w, h) por nó
    boxes = [(0, 0, 420, 220), (500, 0, 420, 220), (1000, 100, 420, 220)]
    segs = cable_segments(boxes)
    # 3 nós -> 2 cabos
    assert len(segs) == 2
    # 1º: borda direita do nó0 (x+w, y+h/2) -> borda esquerda do nó1 (x, y+h/2)
    assert segs[0] == (420, 110, 500, 110)
    assert segs[1] == (920, 110, 1000, 210)


def test_cable_segments_um_no_sem_cabo():
    assert cable_segments([(0, 0, 420, 220)]) == []
    assert cable_segments([]) == []


def test_cable_segments_tamanhos_diferentes():
    # cada card com tamanho próprio: endpoint usa o tamanho do PRÓPRIO nó
    boxes = [(0, 0, 400, 200), (700, 0, 300, 100)]
    segs = cable_segments(boxes)
    # direita do A: (0+400, 0+100); esquerda-centro do B: (700, 0+50)
    assert segs == [(400, 100, 700, 50)]


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
