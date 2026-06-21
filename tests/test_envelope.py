"""Testes do envelope JSON estrito (E3-S1 / ADR-7): roundtrip e rejeição."""

import json

import pytest

from maestro.engine.envelope import (
    Envelope,
    EnvelopeError,
    EnvelopeState,
    encode,
    parse,
)


def test_roundtrip():
    env = Envelope(
        sender="claude",
        recipient="orchestrator",
        message_id="m1",
        task_id="t1",
        state=EnvelopeState.DONE,
        result="42",
        artifacts=["./a.txt"],
        note="ok",
    )
    s = encode(env)
    back = parse(s)
    assert back == env
    # campos de fio usam from/to
    d = json.loads(s)
    assert d["from"] == "claude" and d["to"] == "orchestrator"


def test_requisicao_sem_state():
    env = Envelope(sender="orchestrator", recipient="codex", message_id="m2", task="some")
    assert parse(encode(env)).state is None


def test_rejeita_json_invalido():
    with pytest.raises(EnvelopeError):
        parse("{nao eh json")


def test_rejeita_estado_invalido():
    bad = json.dumps({"v": 1, "message_id": "m", "from": "a", "to": "b", "state": "PRONTO"})
    with pytest.raises(EnvelopeError):
        parse(bad)


def test_rejeita_campo_faltando():
    bad = json.dumps({"v": 1, "from": "a", "to": "b"})  # sem message_id
    with pytest.raises(EnvelopeError):
        parse(bad)


def test_rejeita_campo_extra():
    bad = json.dumps({"v": 1, "message_id": "m", "from": "a", "to": "b", "x": 1})
    with pytest.raises(EnvelopeError):
        parse(bad)


def test_rejeita_excesso_de_bytes():
    env = Envelope(sender="a", recipient="b", message_id="m", result="x" * 5000)
    with pytest.raises(EnvelopeError):
        encode(env)
    # parse também rejeita string grande
    with pytest.raises(EnvelopeError):
        parse('{"v":1,"message_id":"m","from":"a","to":"b","note":"' + "y" * 5000 + '"}')
