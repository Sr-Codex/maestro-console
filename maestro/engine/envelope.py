"""Envelope — mensagem entre orquestrador e agentes (FR15).

E1-S5 define apenas a **estrutura em memória** (o que o Message Bus trafega).
O formato de fio **JSON estrito + JSON Schema + encode/parse + limite de bytes
+ rejeição de inválido** (ADR-7) é implementado no E3-S1, sobre esta mesma
estrutura.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

import jsonschema

# Limite de bytes por mensagem (ADR-7). Artefatos grandes vão por caminho.
MAX_ENVELOPE_BYTES = 4096

_SCHEMA_PATH = Path(__file__).parent / "schema" / "envelope.schema.json"


class EnvelopeError(ValueError):
    """Envelope inválido (formato, schema, estado ou tamanho) — rejeitado."""


@lru_cache(maxsize=1)
def _schema() -> dict:
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


class EnvelopeState(StrEnum):
    """Estado de um resultado de agente (None em mensagens de requisição)."""

    DONE = "DONE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    NEEDS_INPUT = "NEEDS_INPUT"


@dataclass(frozen=True)
class Envelope:
    sender: str
    recipient: str
    message_id: str
    task_id: str | None = None
    state: EnvelopeState | None = None
    task: str | None = None
    result: str | None = None
    artifacts: list[str] = field(default_factory=list)
    note: str | None = None
    v: int = 1


def encode(env: Envelope, *, max_bytes: int = MAX_ENVELOPE_BYTES) -> str:
    """Serializa um Envelope em JSON estrito. Levanta se exceder max_bytes."""
    data = {
        "v": env.v,
        "message_id": env.message_id,
        "task_id": env.task_id,
        "from": env.sender,
        "to": env.recipient,
        "state": env.state.value if env.state is not None else None,
        "task": env.task,
        "result": env.result,
        "artifacts": list(env.artifacts),
        "note": env.note,
    }
    s = json.dumps(data, ensure_ascii=False)
    if len(s.encode("utf-8")) > max_bytes:
        raise EnvelopeError(f"envelope excede {max_bytes} bytes (use artifacts por caminho)")
    return s


def parse(s: str, *, max_bytes: int = MAX_ENVELOPE_BYTES) -> Envelope:
    """Valida e desserializa um Envelope JSON estrito. Rejeita inválido."""
    if len(s.encode("utf-8")) > max_bytes:
        raise EnvelopeError(f"envelope excede {max_bytes} bytes")
    try:
        data = json.loads(s)
    except (json.JSONDecodeError, TypeError) as e:
        raise EnvelopeError(f"JSON inválido: {e}") from e
    try:
        jsonschema.validate(data, _schema())
    except jsonschema.ValidationError as e:
        raise EnvelopeError(f"falha de schema: {e.message}") from e
    state = data.get("state")
    return Envelope(
        sender=data["from"],
        recipient=data["to"],
        message_id=data["message_id"],
        task_id=data.get("task_id"),
        state=EnvelopeState(state) if state is not None else None,
        task=data.get("task"),
        result=data.get("result"),
        artifacts=list(data.get("artifacts", [])),
        note=data.get("note"),
        v=data["v"],
    )
