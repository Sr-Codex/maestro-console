"""Scheduler de routines — dispara as vencidas (V10-S2).

Agendamento in-app (decisão de foundation, Opção 1): um laço `serve` que, a cada
tick, roda as routines vencidas. Clock e sleep são INJETÁVEIS (testes sem relógio
real). Usado pelo `maestro routine serve` (CLI) e pelo tick do canvas.
"""

from __future__ import annotations

import asyncio
import time

from .routines import Routine, Routines, run_routine_once


def due(routines: list[Routine], now: float) -> list[Routine]:
    """Routines vencidas: habilitadas e (nunca rodou) ou (passou o intervalo)."""
    out: list[Routine] = []
    for r in routines:
        if not r.enabled:
            continue
        if r.last_run is None or (now - r.last_run) >= r.interval_s:
            out.append(r)
    return out


async def tick_once(controller, routines: Routines, *, now: float) -> list[str]:
    """Roda todas as routines vencidas uma vez. Retorna os ids disparados."""
    fired: list[str] = []
    for r in due(routines.list(), now):
        await run_routine_once(controller, r, routines, now=now)
        fired.append(r.id)
    return fired


async def serve(
    controller,
    routines: Routines,
    *,
    interval_s: float = 5.0,
    now_fn=time.time,
    sleep_fn=asyncio.sleep,
    should_continue=None,
    max_ticks: int | None = None,
) -> int:
    """Laço do scheduler: tick → sleep. Retorna o nº de ticks executados.

    `should_continue()`/`max_ticks` permitem parar (testes/encerramento gracioso).
    """
    ticks = 0
    while True:
        if should_continue is not None and not should_continue():
            break
        if max_ticks is not None and ticks >= max_ticks:
            break
        await tick_once(controller, routines, now=now_fn())
        ticks += 1
        await sleep_fn(interval_s)
    return ticks
