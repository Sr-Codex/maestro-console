"""Testes do scheduler de routines (V10-S2) — clock/sleep injetáveis."""

import asyncio

from maestro.engine.envelope import Envelope, EnvelopeState
from maestro.engine.routines import Routine, Routines
from maestro.engine.scheduler import due, serve, tick_once
from maestro.engine.state.store import Store


def _env():
    return Envelope(
        sender="claude", recipient="orchestrator", message_id="m", state=EnvelopeState.DONE
    )


class _Ctrl:
    def __init__(self):
        self.calls = []

    async def delegate(self, agent_id, task):
        self.calls.append((agent_id, task))
        return _env()


def _R(name, interval, enabled=True, last_run=None):
    return Routine(name, name, "claude", ["p"], interval, enabled=enabled, last_run=last_run)


# -- due() -------------------------------------------------------------
def test_due_nunca_rodou():
    assert [r.name for r in due([_R("a", 60)], now=0)] == ["a"]


def test_due_respeita_intervalo():
    r = _R("a", 60, last_run=100)
    assert due([r], now=159) == []  # 59s < 60
    assert [x.name for x in due([r], now=160)] == ["a"]  # 60s >= 60


def test_due_ignora_desabilitada():
    assert due([_R("a", 60, enabled=False)], now=10_000) == []


# -- tick_once ---------------------------------------------------------
def test_tick_dispara_so_vencidas(tmp_path):
    store = Store(tmp_path / "m.db")
    rs = Routines(store)
    a = rs.create("venc", "claude", ["p"], interval_s=60)  # nunca rodou -> vence
    b = rs.create("nova", "claude", ["p"], interval_s=60)
    # b já rodou agora -> não vence em now=0
    b.last_run = 0.0
    rs.save(b)
    ctrl = _Ctrl()
    fired = asyncio.run(tick_once(ctrl, rs, now=0.0))
    assert fired == [a.id]
    # a agora tem last_run=0 -> não dispara de novo no mesmo instante
    assert asyncio.run(tick_once(ctrl, rs, now=0.0)) == []
    store.close()


def test_tick_redispara_apos_intervalo(tmp_path):
    store = Store(tmp_path / "m.db")
    rs = Routines(store)
    a = rs.create("x", "claude", ["p"], interval_s=10)
    asyncio.run(tick_once(_Ctrl(), rs, now=0.0))
    assert asyncio.run(tick_once(_Ctrl(), rs, now=5.0)) == []  # ainda não
    assert asyncio.run(tick_once(_Ctrl(), rs, now=10.0)) == [a.id]  # venceu
    assert rs.get(a.id).run_count == 2
    store.close()


# -- serve -------------------------------------------------------------
def test_serve_max_ticks_e_clock_fake(tmp_path):
    store = Store(tmp_path / "m.db")
    rs = Routines(store)
    a = rs.create("x", "claude", ["p"], interval_s=10)
    clock = {"t": 0.0}

    def now_fn():
        return clock["t"]

    async def sleep_fn(_s):
        clock["t"] += 10.0  # cada tick avança 10s -> sempre vence

    ctrl = _Ctrl()
    ticks = asyncio.run(serve(ctrl, rs, now_fn=now_fn, sleep_fn=sleep_fn, max_ticks=3))
    assert ticks == 3
    assert rs.get(a.id).run_count == 3  # disparou nos 3 ticks
    store.close()


def test_serve_should_continue_para(tmp_path):
    store = Store(tmp_path / "m.db")
    rs = Routines(store)
    rs.create("x", "claude", ["p"], interval_s=1)
    state = {"n": 0}

    def cont():
        state["n"] += 1
        return state["n"] <= 2  # deixa rodar 2 ticks

    async def sleep_fn(_s):
        pass

    ticks = asyncio.run(
        serve(_Ctrl(), rs, now_fn=lambda: 999.0, sleep_fn=sleep_fn, should_continue=cont)
    )
    assert ticks == 2
    store.close()
