"""Agent Registry — registra e consulta agentes ativos (E1-S4 / FR7).

API de alto nível sobre o Store (ADR-9: persistência só via Store). Mantém o
estado dos agentes (idle/busy/error) e o tipo; o ``session_id`` vem do índice
de sessões do Store (fonte única para resume — FR13), evitando duplicação.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .state.store import Store


class AgentState(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"


@dataclass(frozen=True)
class AgentRecord:
    id: str
    type: str
    state: AgentState
    session_id: str | None


class Registry:
    """Registro de agentes, persistido via Store."""

    def __init__(self, store: Store):
        self._store = store

    def register(
        self,
        agent_id: str,
        agent_type: str,
        *,
        session_id: str | None = None,
        state: AgentState = AgentState.IDLE,
    ) -> AgentRecord:
        self._store.upsert_agent(agent_id, agent_type, str(state))
        if session_id is not None:
            self._store.set_session(agent_id, session_id)
        return self.get(agent_id)  # type: ignore[return-value]

    def get(self, agent_id: str) -> AgentRecord | None:
        row = self._store.get_agent(agent_id)
        if row is None:
            return None
        return AgentRecord(
            id=row["id"],
            type=row["type"],
            state=AgentState(row["state"]),
            session_id=self._store.get_session(agent_id),
        )

    def list(self) -> list[AgentRecord]:
        out = []
        for row in self._store.list_agents():
            out.append(
                AgentRecord(
                    id=row["id"],
                    type=row["type"],
                    state=AgentState(row["state"]),
                    session_id=self._store.get_session(row["id"]),
                )
            )
        return out

    def set_state(self, agent_id: str, state: AgentState) -> None:
        self._store.set_agent_state(agent_id, str(state))

    def set_session(self, agent_id: str, session_id: str) -> None:
        self._store.set_session(agent_id, session_id)

    def unregister(self, agent_id: str) -> None:
        self._store.remove_agent(agent_id)
