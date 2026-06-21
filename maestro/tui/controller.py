"""TUI Controller — lógica da interface, desacoplada do render (E4-S2 / FR11).

Expõe o que a TUI precisa: listar agentes/estado, ver histórico e disparar uma
delegação. Testável sem terminal (o app.py é só o render/loop por cima).
"""

from __future__ import annotations

from ..engine import history
from ..engine.orchestrator import Orchestrator
from ..engine.registry import AgentRecord, Registry
from ..engine.state.store import Store


class TUIController:
    def __init__(self, registry: Registry, store: Store, orchestrator: Orchestrator):
        self._registry = registry
        self._store = store
        self._orch = orchestrator

    def list_agents(self) -> list[AgentRecord]:
        return self._registry.list()

    def agents_text(self) -> str:
        agents = self.list_agents()
        if not agents:
            return "(nenhum agente registrado)"
        return "\n".join(f"- {a.id} [{a.type}] estado={a.state}" for a in agents)

    def history_text(self, limit: int = 20) -> str:
        return history.format_history(history.recent(self._store, limit=limit))

    async def delegate(self, agent_id: str, task: str):
        return await self._orch.delegate(agent_id, task)
