"""Testes do prompt-wrapper + retry (E3-S2)."""

import asyncio

from maestro.engine.envelope import EnvelopeState
from maestro.engine.wrapper import ENVELOPE_INSTRUCTIONS, request_envelope, wrap_task


def test_wrap_task_inclui_instrucoes():
    p = wrap_task("faça X")
    assert "faça X" in p
    assert ENVELOPE_INSTRUCTIONS in p
    assert "DONE" in p


def _ask_const(text):
    async def ask(_prompt):
        return text

    return ask


def test_payload_valido_vira_envelope():
    async def main():
        ask = _ask_const('{"state":"DONE","result":"42","artifacts":[],"note":null}')
        env = await request_envelope(ask, "t", agent_id="claude", message_id="m1")
        assert env.state is EnvelopeState.DONE
        assert env.result == "42"
        assert env.sender == "claude" and env.recipient == "orchestrator"
        assert env.message_id == "m1"

    asyncio.run(main())


def test_extrai_json_de_texto_ao_redor():
    async def main():
        ask = _ask_const('blá blá\n{"state":"DONE","result":"ok"}\nfim')
        env = await request_envelope(ask, "t", agent_id="codex", message_id="m2")
        assert env.state is EnvelopeState.DONE and env.result == "ok"

    asyncio.run(main())


def test_retry_depois_sucesso():
    seq = ["lixo sem json", '{"state":"DONE","result":"ok"}']

    async def ask(_prompt):
        return seq.pop(0)

    async def main():
        env = await request_envelope(ask, "t", agent_id="a", message_id="m3", max_retries=2)
        assert env.state is EnvelopeState.DONE

    asyncio.run(main())


def test_esgota_retry_retorna_failed():
    async def main():
        ask = _ask_const("nunca tem json valido")
        env = await request_envelope(ask, "t", agent_id="a", message_id="m4", max_retries=1)
        assert env.state is EnvelopeState.FAILED  # falha explícita, não sucesso parcial
        assert "inválido" in (env.note or "")

    asyncio.run(main())


def test_state_invalido_rejeitado():
    async def main():
        ask = _ask_const('{"state":"PRONTO","result":"x"}')
        env = await request_envelope(ask, "t", agent_id="a", message_id="m5", max_retries=0)
        assert env.state is EnvelopeState.FAILED

    asyncio.run(main())
