"""Testes do Message Bus (E1-S5): roteamento por recipient, fan-out, tipagem."""

import asyncio

from maestro.engine.bus import MessageBus
from maestro.engine.envelope import Envelope, EnvelopeState


def _env(recipient: str, mid: str = "m1") -> Envelope:
    return Envelope(sender="orchestrator", recipient=recipient, message_id=mid, task="x")


def test_publish_entrega_ao_assinante():
    async def main():
        bus = MessageBus()
        q = bus.subscribe("claude")
        delivered = await bus.publish(_env("claude"))
        assert delivered == 1
        got = await q.get()
        assert got.recipient == "claude"
        assert got.task == "x"

    asyncio.run(main())


def test_roteamento_por_recipient():
    async def main():
        bus = MessageBus()
        q_claude = bus.subscribe("claude")
        await bus.publish(_env("codex"))  # ninguém assina codex
        assert q_claude.empty()

    asyncio.run(main())


def test_sem_assinante_retorna_zero():
    async def main():
        bus = MessageBus()
        assert await bus.publish(_env("ninguem")) == 0

    asyncio.run(main())


def test_fan_out_multiplos_assinantes():
    async def main():
        bus = MessageBus()
        q1 = bus.subscribe("claude")
        q2 = bus.subscribe("claude")
        delivered = await bus.publish(_env("claude"))
        assert delivered == 2
        assert (await q1.get()).message_id == "m1"
        assert (await q2.get()).message_id == "m1"

    asyncio.run(main())


def test_unsubscribe():
    async def main():
        bus = MessageBus()
        q = bus.subscribe("claude")
        bus.unsubscribe("claude", q)
        assert bus.subscriber_count("claude") == 0
        assert await bus.publish(_env("claude")) == 0

    asyncio.run(main())


def test_publish_so_aceita_envelope():
    async def main():
        bus = MessageBus()
        import pytest

        with pytest.raises(TypeError):
            await bus.publish({"recipient": "claude"})  # type: ignore[arg-type]

    asyncio.run(main())


def test_carrega_estado_de_resultado():
    async def main():
        bus = MessageBus()
        q = bus.subscribe("orchestrator")
        env = Envelope(
            sender="claude",
            recipient="orchestrator",
            message_id="r1",
            state=EnvelopeState.DONE,
            result="42",
        )
        await bus.publish(env)
        got = await q.get()
        assert got.state is EnvelopeState.DONE
        assert got.result == "42"

    asyncio.run(main())
