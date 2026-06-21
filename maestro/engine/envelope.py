"""Envelope — mensagem entre orquestrador e agentes (FR15).

E1-S5 define apenas a **estrutura em memória** (o que o Message Bus trafega).
O formato de fio **JSON estrito + JSON Schema + encode/parse + limite de bytes
+ rejeição de inválido** (ADR-7) é implementado no E3-S1, sobre esta mesma
estrutura.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


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
