"""Orchestrator — delega, extrai, encaminha e agrega (E3-S4 / FR5, FR10).

Fluxo orquestrador-mediado: recebe a intenção, delega ao agente A (pedindo um
envelope), extrai o resultado, **encaminha** ao agente B, e assim por diante,
agregando os envelopes. Em estado terminal não-DONE (BLOCKED/NEEDS_INPUT/FAILED)
**escala ao humano** parando a cadeia — nunca trava.

Depende de uma função ``ask(agent_id, prompt) -> stdout`` (injetável). A
implementação real (``make_agent_ask``) usa SessionManager (mutex/continuidade)
+ sandbox + workspace. Testes injetam um ask falso.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from .envelope import Envelope, EnvelopeState
from .session import SessionManager
from .teams import Team
from .usage import parse_run_usage
from .workspace import Workspace
from .wrapper import request_envelope

# ask(agent_id, prompt) -> stdout bruto do agente
Ask = Callable[[str, str], Awaitable[str]]

# Um passo da cadeia: agente + função que monta a tarefa a partir do resultado
# anterior (str | None). Para tarefa fixa, ignore o argumento.
TaskFn = Callable[[str | None], str]


@dataclass
class Step:
    agent_id: str
    task: TaskFn


@dataclass
class ChainResult:
    envelopes: list[Envelope] = field(default_factory=list)
    escalated: bool = False
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return not self.escalated


@dataclass(frozen=True)
class StepProgress:
    index: int
    role: str
    agent: str
    task_id: str
    phase: str  # "start" | "done"
    state: str | None = None
    duration_s: float = 0.0


# Callback de progresso por etapa (síncrono, só observabilidade)
ProgressFn = Callable[[StepProgress], None]


class OutputBus:
    """Ponte do stdout AO VIVO dos agentes (agent_id, chunk) -> assinante.

    A engine emite; o frontend (web) liga um callback. Sem assinante = no-op
    (ex.: TUI). Não é caminho de dados (só visualização — V5).
    """

    def __init__(self) -> None:
        self._cb = None

    def set(self, cb) -> None:
        self._cb = cb

    def clear(self) -> None:
        self._cb = None

    def emit(self, agent_id: str, chunk: str) -> None:
        if self._cb is not None:
            self._cb(agent_id, chunk)


class Orchestrator:
    def __init__(self, ask: Ask, *, store=None, logbook=None, max_retries: int = 2):
        self._ask = ask
        self._store = store
        self._logbook = logbook
        self._max_retries = max_retries

    async def delegate(self, agent_id: str, task: str, *, task_id: str | None = None) -> Envelope:
        async def ask1(prompt: str) -> str:
            return await self._ask(agent_id, prompt)

        t0 = time.monotonic()
        env = await request_envelope(
            ask1,
            task,
            agent_id=agent_id,
            message_id=str(uuid.uuid4()),
            task_id=task_id,
            max_retries=self._max_retries,
        )
        if self._logbook is not None:
            tid = (task_id or env.message_id)[:8]
            state = str(env.state) if env.state else "?"
            # observabilidade (escopo 5): task_id, agente, estado, duração
            self._logbook.append(f"{tid} {agent_id} -> {state} ({time.monotonic() - t0:.1f}s)")
        if self._store is not None:
            self._store.log_envelope(
                message_id=env.message_id,
                task_id=env.task_id,
                sender=env.sender,
                recipient=env.recipient,
                state=str(env.state) if env.state else None,
                payload={"result": env.result, "artifacts": env.artifacts},
            )
        return env

    async def run_chain(self, steps: list[Step], *, task_id: str | None = None) -> ChainResult:
        """Executa a cadeia, encaminhando o result de cada passo ao próximo."""
        out = ChainResult()
        carry: str | None = None
        for step in steps:
            env = await self.delegate(step.agent_id, step.task(carry), task_id=task_id)
            out.envelopes.append(env)
            if env.state is not EnvelopeState.DONE:
                out.escalated = True
                out.reason = f"{step.agent_id} retornou {env.state}: {env.note or env.result}"
                return out  # escala ao humano, não trava
            carry = env.result
        return out

    @staticmethod
    def _role_task(role, intent: str, carry: str | None) -> str:
        # compacto (escopo 4): instrução do papel + entrada (intenção ou result anterior)
        entrada = intent if carry is None else carry
        return f"[{role.name}] {role.instruction}\nentrada: {entrada}"

    async def run_team(
        self,
        team: Team,
        intent: str,
        *,
        task_id: str | None = None,
        on_step: ProgressFn | None = None,
    ) -> ChainResult:
        """Executa a cadeia de um Team, com checkpoint por etapa e cancelável.

        Propaga CancelledError (o subprocesso é morto no runner) — cancelamento
        seguro: as etapas seguintes não rodam.
        """
        tid = task_id or str(uuid.uuid4())
        if self._store is not None:
            self._store.start_chain(tid, team.name, intent)
        return await self._run_steps(
            team, intent, run_id=tid, start_idx=0, carry=None, on_step=on_step
        )

    async def resume_chain(
        self,
        team: Team,
        intent: str,
        run_id: str,
        *,
        on_step: ProgressFn | None = None,
        swap_agent: str | None = None,
        reprompt: str | None = None,
    ) -> ChainResult:
        """Retoma uma cadeia da última etapa NÃO concluída (checkpoint).

        Etapas já DONE são puladas (nunca repetidas). Opções para a etapa que
        falhou: trocar agente (swap_agent) e/ou reprompt. Sem store, não há o
        que retomar.
        """
        if self._store is None:
            raise RuntimeError("resume_chain requer store (checkpoints)")
        steps = self._store.get_steps(run_id)  # ordenado por idx
        # 1ª etapa NÃO concluída (robusto a buracos; não conta DONEs cegamente)
        start_idx = len(steps)
        for i, s in enumerate(steps):
            if s["state"] != "DONE":
                start_idx = i
                break
        carry = steps[start_idx - 1]["result"] if start_idx > 0 else None
        override = (
            {"agent": swap_agent, "reprompt": reprompt} if start_idx < len(team.roles) else {}
        )
        self._store.set_chain_status(run_id, "running")
        return await self._run_steps(
            team,
            intent,
            run_id=run_id,
            start_idx=start_idx,
            carry=carry,
            on_step=on_step,
            override_idx=start_idx,
            override=override,
        )

    async def _run_steps(
        self,
        team,
        intent,
        *,
        run_id,
        start_idx,
        carry,
        on_step,
        override_idx: int = -1,
        override: dict | None = None,
    ) -> ChainResult:
        out = ChainResult()
        for i in range(start_idx, len(team.roles)):
            role = team.roles[i]
            agent = role.agent
            extra = ""
            if i == override_idx and override:
                agent = override.get("agent") or agent
                extra = ("\n" + override["reprompt"]) if override.get("reprompt") else ""
            if on_step:
                on_step(StepProgress(i, role.name, agent, run_id, "start"))
            t0 = time.monotonic()
            env = await self.delegate(
                agent, self._role_task(role, intent, carry) + extra, task_id=run_id
            )
            dt = time.monotonic() - t0
            out.envelopes.append(env)
            state = str(env.state) if env.state else None
            if self._store is not None:
                self._store.save_step(run_id, i, role.name, agent, state, env.result)
            if on_step:
                on_step(StepProgress(i, role.name, agent, run_id, "done", state, dt))
            if env.state is not EnvelopeState.DONE:
                out.escalated = True
                out.reason = f"{role.name}({agent}) -> {env.state}: {env.note or env.result}"
                if self._store is not None:
                    self._store.set_chain_status(run_id, "escalated")
                return out
            carry = env.result
        if self._store is not None:
            self._store.set_chain_status(run_id, "done")
        return out


def make_agent_ask(
    session_manager: SessionManager,
    agents: dict[str, object],
    workspace: Workspace,
    *,
    timeout: float,
    on_output=None,
    on_usage=None,
) -> Ask:
    """ask() real: roda o agente sob sessão (mutex/continuidade) + sandbox.

    ``on_output(agent_id, chunk)``: se dado, recebe o stdout do agente AO VIVO
    (terminais read-only no canvas — V5). Caminho de dados segue headless.
    ``on_usage(agent_id, AgentUsage)``: se dado, recebe o uso de tokens/custo do turno
    (medidor F1) — best-effort; nunca derruba o run.
    """

    async def ask(agent_id: str, prompt: str) -> str:
        profile = agents[agent_id]
        ws = str(workspace.create(agent_id))
        sink = (lambda chunk: on_output(agent_id, chunk)) if on_output is not None else None
        res = await session_manager.run_in_session(
            profile, agent_id, prompt, workspace=ws, timeout=timeout, on_output=sink
        )
        if on_usage is not None:  # F1: mede tokens/custo do turno (best-effort)
            try:
                u = parse_run_usage(res.stdout, getattr(profile, "name", agent_id))
                if u is not None:
                    on_usage(agent_id, u)
            except Exception:  # medição nunca pode derrubar o caminho de dados
                pass
        return res.stdout

    return ask
