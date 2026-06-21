"""Message Bus — pub/sub assíncrono em memória (E1-S5 / FR8).

Roteia **Envelopes** por ``recipient``, de forma desacoplada: o bus não conhece
CLIs, adapters nem agentes — só entrega mensagens a quem assinou aquele nome.
Suporta múltiplos assinantes por nome (fan-out).
"""

from __future__ import annotations

import asyncio

from .envelope import Envelope


class MessageBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue[Envelope]]] = {}

    def subscribe(self, name: str) -> asyncio.Queue[Envelope]:
        """Assina mensagens destinadas a ``name``; retorna a fila de entrega."""
        queue: asyncio.Queue[Envelope] = asyncio.Queue()
        self._subs.setdefault(name, []).append(queue)
        return queue

    def unsubscribe(self, name: str, queue: asyncio.Queue[Envelope]) -> None:
        queues = self._subs.get(name)
        if not queues:
            return
        if queue in queues:
            queues.remove(queue)
        if not queues:
            del self._subs[name]

    async def publish(self, env: Envelope) -> int:
        """Entrega ``env`` a todos os assinantes de ``env.recipient``.

        Retorna o número de assinantes que receberam (0 = ninguém escutando).
        """
        if not isinstance(env, Envelope):
            raise TypeError("o bus trafega apenas Envelope")
        queues = list(self._subs.get(env.recipient, ()))
        for queue in queues:
            await queue.put(env)
        return len(queues)

    def subscriber_count(self, name: str) -> int:
        return len(self._subs.get(name, ()))
