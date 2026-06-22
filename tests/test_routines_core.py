"""Testes do core de routines (V10-S1) — CRUD + run_routine_once."""

import asyncio

from maestro.engine.envelope import Envelope, EnvelopeState
from maestro.engine.routines import Routines, run_routine_once
from maestro.engine.state.store import Store


def _routines(tmp_path):
    store = Store(tmp_path / "m.db")
    return Routines(store), store


def _env(state, result=None):
    return Envelope(
        sender="claude", recipient="orchestrator", message_id="m", state=state, result=result
    )


class _Ctrl:
    def __init__(self, envs):
        self._envs = list(envs)
        self.calls = []

    async def delegate(self, agent_id, task):
        self.calls.append((agent_id, task))
        return self._envs[len(self.calls) - 1]


# -- CRUD --------------------------------------------------------------
def test_create_get_list(tmp_path):
    r, store = _routines(tmp_path)
    a = r.create("testes", "claude", ["rode testes", "reporte"], interval_s=600)
    g = r.get(a.id)
    assert g.name == "testes" and g.agent == "claude"
    assert g.steps == ["rode testes", "reporte"] and g.interval_s == 600
    assert g.enabled is True and g.run_count == 0 and g.last_run is None
    assert [x.id for x in r.list()] == [a.id]
    store.close()


def test_enable_disable(tmp_path):
    r, store = _routines(tmp_path)
    a = r.create("x", "claude", ["p"], 60)
    r.set_enabled(a.id, False)
    assert r.get(a.id).enabled is False
    r.set_enabled(a.id, True)
    assert r.get(a.id).enabled is True
    store.close()


def test_delete_e_persistencia(tmp_path):
    r, store = _routines(tmp_path)
    a = r.create("keep", "claude", ["p"], 60)
    store.close()
    store2 = Store(tmp_path / "m.db")
    r2 = Routines(store2)
    assert r2.get(a.id).name == "keep"
    r2.delete(a.id)
    assert r2.get(a.id) is None
    store2.close()


# -- run_routine_once --------------------------------------------------
def test_run_sequencial_todos_done(tmp_path):
    r, store = _routines(tmp_path)
    rt = r.create("seq", "claude", ["p1", "p2", "p3"], 60)
    ctrl = _Ctrl([_env(EnvelopeState.DONE)] * 3)
    run = asyncio.run(run_routine_once(ctrl, rt, r, now=1000.0))
    assert run.ok and run.stopped_at is None
    assert [c[1] for c in ctrl.calls] == ["p1", "p2", "p3"]
    g = r.get(rt.id)
    assert g.run_count == 1 and g.last_run == 1000.0
    store.close()


def test_run_para_no_nao_done(tmp_path):
    r, store = _routines(tmp_path)
    rt = r.create("seq", "claude", ["p1", "p2", "p3"], 60)
    ctrl = _Ctrl([_env(EnvelopeState.DONE), _env(EnvelopeState.BLOCKED), _env(EnvelopeState.DONE)])
    run = asyncio.run(run_routine_once(ctrl, rt, r, now=2000.0))
    assert not run.ok and run.stopped_at == 1
    assert [c[1] for c in ctrl.calls] == ["p1", "p2"]  # p3 não roda
    assert r.get(rt.id).run_count == 1  # conta a execução mesmo parando
    store.close()


def test_run_count_acumula(tmp_path):
    r, store = _routines(tmp_path)
    rt = r.create("x", "claude", ["p"], 60)
    ctrl = _Ctrl([_env(EnvelopeState.DONE)] * 2)
    asyncio.run(run_routine_once(ctrl, rt, r, now=1.0))
    rt2 = r.get(rt.id)
    asyncio.run(run_routine_once(ctrl, rt2, r, now=2.0))
    assert r.get(rt.id).run_count == 2 and r.get(rt.id).last_run == 2.0
    store.close()
