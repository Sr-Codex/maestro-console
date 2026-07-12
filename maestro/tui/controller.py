"""TUI Controller — lógica da interface, desacoplada do render (V2-S3 / FR11).

Dashboard (agentes+estados, tarefa ativa, fila, último resultado, rotas) e
execução de cadeias de Team com progresso por etapa. Testável sem terminal.
"""

from __future__ import annotations

import asyncio
import time
import uuid

from ..engine import history
from ..engine.orchestrator import ChainResult, Orchestrator, StepProgress
from ..engine.registry import AgentRecord, AgentState, Registry
from ..engine.state.store import Store
from ..engine.teams import Role, Team, Teams

# envelope state (no passo done) -> estado do agente no dashboard
_STATE_MAP = {
    "DONE": AgentState.IDLE,
    "BLOCKED": AgentState.BLOCKED,
    "FAILED": AgentState.FAILED,
    "NEEDS_INPUT": AgentState.BLOCKED,
}


class TUIController:
    def __init__(
        self,
        registry: Registry,
        store: Store,
        orchestrator: Orchestrator,
        teams: Teams | None = None,
    ):
        self._registry = registry
        self._store = store
        self._orch = orchestrator
        self._teams = teams or Teams(store)
        self._active: dict | None = None
        self._last: dict | None = None
        self._resume_ctx: tuple | None = None  # (team, intent, run_id) p/ retomar
        self._progress = None  # callback opcional do app para exibir progresso
        self.agents: dict = {}  # id->profile (setado pelo bootstrap); p/ instâncias runtime

    def add_agent_instance(self, new_id: str, base_id: str) -> None:
        """Registra um novo agente reusando o profile de ``base_id`` (mesmo CLI).

        Permite criar mais terminais de agente no canvas em runtime — o
        ``delegate``/``maestro-ask`` passa a resolver ``new_id`` (workspace/sessão
        próprios por id). Levanta se base desconhecido ou id já existente.
        """
        if not self.agents or base_id not in self.agents:
            raise ValueError(f"agente base desconhecido: {base_id}")
        if new_id in self.agents:
            raise ValueError(f"id de agente já existe: {new_id}")
        self.agents[new_id] = self.agents[base_id]  # mesma profile (mesmo binário)
        self._registry.register(new_id, base_id)  # type = base (claude/codex)

    def remove_agent_instance(self, nid: str) -> None:
        """Desregistra um agente-INSTÂNCIA (ao fechar/dispensar o nó) — libera o id p/ reuso
        e evita a colisão 'id já existe' em recruit futuro. Idempotente."""
        self.agents.pop(nid, None)
        try:
            self._registry.unregister(nid)
        except Exception:  # noqa: BLE001 — remoção best-effort não pode derrubar o close
            pass

    # -- consultas ------------------------------------------------------
    def list_agents(self) -> list[AgentRecord]:
        return self._registry.list()

    def agents_text(self) -> str:
        agents = self.list_agents()
        if not agents:
            return "(nenhum agente registrado)"
        return "\n".join(f"  - {a.id} [{a.type}] estado={a.state}" for a in agents)

    def history_text(self, limit: int = 10) -> str:
        return history.format_history(history.recent(self._store, limit=limit))

    def list_teams(self) -> list[str]:
        return self._teams.list()

    def get_team(self, name: str) -> Team | None:
        return self._teams.get(name)

    def team_detail_text(self, name: str) -> str:
        t = self._teams.get(name)
        if t is None:
            return f"(team {name!r} não encontrado)"
        linhas = [f"{name}: {t.route}"]
        linhas += [f"  - {r.name} [{r.agent}]: {r.instruction}" for r in t.roles]
        return "\n".join(linhas)

    def save_team(self, name: str, roles: list[tuple[str, str, str]]) -> Team:
        """Cria/edita um team. roles = [(papel, agente, instrução), ...]."""
        team = Team(name.strip(), [Role(p.strip(), a.strip(), i.strip()) for p, a, i in roles])
        self._teams.save(team)  # valida
        return team

    def duplicate_team(self, src: str, new_name: str) -> Team:
        return self._teams.duplicate(src, new_name.strip())

    def delete_team(self, name: str) -> None:
        self._teams.delete(name)

    def team_exists(self, name: str) -> bool:
        return self._teams.exists(name)

    # -- dashboard ------------------------------------------------------
    def dashboard_text(self) -> str:
        if self._active:
            a = self._active
            elapsed = time.monotonic() - a.get("t0", time.monotonic())
            ativa = (
                f"{a['task_id'][:8]} | {a['route']} | etapa: {a['current']} "
                f"[{a['state']}] {elapsed:.0f}s"
            )
        else:
            ativa = "(nenhuma)"
        if self._last:
            ll = self._last
            res = (ll.get("result") or ll.get("reason") or "")[:60]
            ultimo = f"{ll['route']} -> {ll['state']} | {res}"
        else:
            ultimo = "(nenhum)"
        return (
            "== maestro console — dashboard ==\n"
            f"Agentes:\n{self.agents_text()}\n"
            f"Tarefa ativa: {ativa}\n"
            "Fila: (vazia)\n"
            f"Último resultado: {ultimo}\n"
            f"Rotas recentes:\n{self.history_text()}"
        )

    # -- execução -------------------------------------------------------
    def _on_step(self, sp: StepProgress) -> None:
        cur = f"{sp.role}({sp.agent})"
        if sp.phase == "start":
            self._active = {
                "task_id": sp.task_id,
                "route": self._active_route(),
                "current": cur,
                "state": "busy",
                "t0": time.monotonic(),
            }
            self._registry.set_state(sp.agent, AgentState.BUSY)
        else:  # done
            if self._active:
                self._active["current"] = cur
                self._active["state"] = sp.state or "?"
            self._registry.set_state(sp.agent, _STATE_MAP.get(sp.state, AgentState.IDLE))
        if self._progress is not None:
            self._progress(sp)

    def _active_route(self) -> str:
        return self._active["route"] if self._active else "?"

    def last_run_id(self) -> str | None:
        return self._last.get("task_id") if self._last else None

    async def run_team(
        self, team: Team, intent: str, *, run_id: str | None = None, progress=None
    ) -> ChainResult:
        run_id = run_id or str(uuid.uuid4())  # task_id coerente em log/histórico/checkpoint
        self._run_id = run_id
        self._active = {
            "task_id": run_id,
            "route": team.route,
            "current": "-",
            "state": "start",
            "t0": time.monotonic(),
        }
        self._progress = progress
        try:
            res = await self._orch.run_team(team, intent, task_id=run_id, on_step=self._on_step)
        except asyncio.CancelledError:
            self._last = {
                "task_id": run_id,
                "route": team.route,
                "state": "CANCELADO",
                "result": None,
            }
            self._active = None
            self._progress = None
            raise
        result = res.envelopes[-1].result if res.envelopes else None
        self._last = {
            "task_id": run_id,
            "route": team.route,
            "state": "DONE" if res.ok else "ESCALOU",
            "result": result,
            "reason": res.reason,
        }
        # contexto p/ retomar (apenas quando escalou)
        self._resume_ctx = (team, intent, run_id) if res.escalated else None
        self._active = None
        self._progress = None
        return res

    def can_resume(self) -> bool:
        return self._resume_ctx is not None

    async def resume_last(self, *, swap_agent=None, reprompt=None, progress=None) -> ChainResult:
        """Retoma a última cadeia escalada do checkpoint (sem repetir DONE)."""
        if self._resume_ctx is None:
            raise RuntimeError("não há cadeia para retomar")
        team, intent, run_id = self._resume_ctx
        return await self.resume_run(
            team, intent, run_id, swap_agent=swap_agent, reprompt=reprompt, progress=progress
        )

    async def resume_run(
        self, team: Team, intent: str, run_id: str,
        *, swap_agent=None, reprompt=None, progress=None,
    ) -> ChainResult:
        """Retoma uma cadeia POR run_id (docs/29 §4.4): a retomada 1-clique das chains
        `escalated_budget` do diálogo Limites — funciona mesmo após reabrir o app (o
        checkpoint vive no store, não em `_resume_ctx`)."""
        self._active = {
            "task_id": run_id,
            "route": team.route,
            "current": "-",
            "state": "resume",
            "t0": time.monotonic(),
        }
        self._progress = progress
        try:
            res = await self._orch.resume_chain(
                team,
                intent,
                run_id,
                on_step=self._on_step,
                swap_agent=swap_agent,
                reprompt=reprompt,
            )
        except asyncio.CancelledError:
            self._last = {
                "task_id": run_id,
                "route": team.route,
                "state": "CANCELADO",
                "result": None,
            }
            self._active = None
            self._progress = None
            raise
        result = res.envelopes[-1].result if res.envelopes else None
        self._last = {
            "task_id": run_id,
            "route": team.route,
            "state": "DONE" if res.ok else "ESCALOU",
            "result": result,
            "reason": res.reason,
        }
        self._resume_ctx = (team, intent, run_id) if res.escalated else None
        self._active = None
        self._progress = None
        return res

    async def delegate(self, agent_id: str, task: str):
        return await self._orch.delegate(agent_id, task)
