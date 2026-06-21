"""Configuração da engine (E2-S5).

Valores ajustáveis em runtime. O **teto de agentes** é configurável de
propósito (não fixo): o hardware do usuário vai ganhar mais RAM, então o limite
deve subir por configuração/variável de ambiente, sem mexer no código.

A enforcement do teto (semáforo) entra na fila/orquestrador (E3).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Default conservador para o uConsole atual (3.7GB). Suba conforme a RAM crescer
# via env MAESTRO_AGENT_CEILING. O benchmark VS-2 (swap-off) informa o valor seguro.
DEFAULT_AGENT_CEILING = 3


@dataclass(frozen=True)
class Config:
    agent_ceiling: int = DEFAULT_AGENT_CEILING

    @classmethod
    def from_env(cls) -> Config:
        raw = os.environ.get("MAESTRO_AGENT_CEILING")
        if raw is None:
            return cls()
        try:
            value = int(raw)
        except ValueError as e:
            raise ValueError(f"MAESTRO_AGENT_CEILING inválido: {raw!r}") from e
        if value < 1:
            raise ValueError("MAESTRO_AGENT_CEILING deve ser >= 1")
        return cls(agent_ceiling=value)
