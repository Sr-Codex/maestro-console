"""Routines — prompts agendados, multi-step e mediados (V10-S1).

Uma routine roda uma sequência de passos (prompts) num agente, em intervalos.
Execução MEDIADA: cada passo = controller.delegate; o próximo só roda se o
anterior retornar DONE (mesma filosofia de chain/handoff). Mantém run_count e
last_run. Pausar/retomar = enabled False/True.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field

from .envelope import EnvelopeState
from .state.store import Store


@dataclass
class Routine:
    id: str
    name: str
    agent: str
    steps: list[str]
    interval_s: float
    enabled: bool = True
    run_count: int = 0
    last_run: float | None = None


@dataclass
class RoutineRun:
    envelopes: list = field(default_factory=list)
    ok: bool = True
    stopped_at: int | None = None  # índice do passo que parou (não-DONE)


def _from_row(r: dict) -> Routine:
    return Routine(
        id=r["id"],
        name=r["name"],
        agent=r["agent"],
        steps=json.loads(r["steps_json"]),
        interval_s=r["interval_s"],
        enabled=bool(r["enabled"]),
        run_count=r["run_count"],
        last_run=r["last_run"],
    )


class Routines:
    """CRUD de routines sobre o Store."""

    def __init__(self, store: Store):
        self._store = store

    def create(self, name: str, agent: str, steps: list[str], interval_s: float) -> Routine:
        r = Routine(str(uuid.uuid4()), name, agent, list(steps), float(interval_s))
        self.save(r)
        return r

    def save(self, r: Routine) -> None:
        self._store.upsert_routine(
            r.id,
            r.name,
            r.agent,
            json.dumps(r.steps),
            r.interval_s,
            r.enabled,
            r.run_count,
            r.last_run,
        )

    def get(self, routine_id: str) -> Routine | None:
        row = self._store.get_routine(routine_id)
        return _from_row(row) if row else None

    def list(self) -> list[Routine]:
        return [_from_row(r) for r in self._store.list_routines()]

    def delete(self, routine_id: str) -> None:
        self._store.remove_routine(routine_id)

    def set_enabled(self, routine_id: str, enabled: bool) -> None:
        r = self.get(routine_id)
        if r is not None:
            r.enabled = enabled
            self.save(r)


async def run_routine_once(
    controller, routine: Routine, routines: Routines, *, now: float | None = None
) -> RoutineRun:
    """Roda os passos em sequência (para no 1º não-DONE). Atualiza run_count/last_run."""
    run = RoutineRun()
    for i, step in enumerate(routine.steps):
        env = await controller.delegate(routine.agent, step)
        run.envelopes.append(env)
        if env.state is not EnvelopeState.DONE:
            run.ok = False
            run.stopped_at = i
            break
    routine.run_count += 1
    routine.last_run = time.time() if now is None else now
    routines.save(routine)
    return run
