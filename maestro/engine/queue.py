"""Task Queue — despacho concorrente com teto + callback (E3-S3 / FR9).

Enfileira tarefas e as executa via um ``worker`` injetado, limitando a
concorrência ao **teto de agentes** (semáforo). A serialização por sessão
(1 tarefa ativa por agente) é garantida pelo worker quando ele usa o
SessionManager (mutex por sessão, E2-S3). Dispara um callback com o resultado.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ..config import DEFAULT_AGENT_CEILING

Worker = Callable[["Task"], Awaitable[Any]]


@dataclass
class Task:
    id: str
    agent_id: str
    prompt: str
    callback: Callable[[Any], None] | None = None


class TaskQueue:
    def __init__(self, worker: Worker, *, ceiling: int = DEFAULT_AGENT_CEILING):
        if ceiling < 1:
            raise ValueError("ceiling deve ser >= 1")
        self._worker = worker
        self._sem = asyncio.Semaphore(ceiling)

    async def submit(self, task: Task) -> Any:
        async with self._sem:
            result = await self._worker(task)
        if task.callback is not None:
            task.callback(result)
        return result

    async def submit_all(self, tasks: list[Task]) -> list[Any]:
        return await asyncio.gather(*(self.submit(t) for t in tasks))
