"""RunManager — ciclo de vida de UMA execução em background (V4-S2).

Garante execução única (guard anti-duplicação por cliques repetidos), expõe
start/cancel/resume e publica progresso (StepProgress) a assinantes SSE (V4-S3).
Reusa o TUIController/engine — sem duplicar regras.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable


class AlreadyRunning(RuntimeError):
    pass


class RunManager:
    def __init__(self, controller):
        self._ctrl = controller
        self._task: asyncio.Task | None = None
        self._listeners: list[Callable] = []

    # -- SSE (V4-S3) ----------------------------------------------------
    def subscribe(self, cb: Callable) -> None:
        self._listeners.append(cb)

    def unsubscribe(self, cb: Callable) -> None:
        if cb in self._listeners:
            self._listeners.remove(cb)

    def _emit(self, sp) -> None:
        for cb in list(self._listeners):
            cb(sp)

    # -- ciclo de vida --------------------------------------------------
    def active(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self, team_name: str, intent: str) -> str:
        if self.active():
            raise AlreadyRunning("já existe uma execução ativa")
        team = self._ctrl.get_team(team_name)
        if team is None:
            raise LookupError(f"team {team_name!r} não encontrado")
        run_id = str(uuid.uuid4())
        self._task = asyncio.create_task(
            self._ctrl.run_team(team, intent, run_id=run_id, progress=self._emit)
        )
        return run_id

    async def resume(self, *, swap_agent=None, reprompt=None) -> str:
        if self.active():
            raise AlreadyRunning("já existe uma execução ativa")
        if not self._ctrl.can_resume():
            raise LookupError("não há cadeia para retomar")
        run_id = self._ctrl.last_run_id()
        self._task = asyncio.create_task(
            self._ctrl.resume_last(swap_agent=swap_agent, reprompt=reprompt, progress=self._emit)
        )
        return run_id

    def cancel(self) -> bool:
        if self.active():
            self._task.cancel()
            return True
        return False

    async def wait(self):
        """Aguarda a execução atual terminar (uso em testes)."""
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
