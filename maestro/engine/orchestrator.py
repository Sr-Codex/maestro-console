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


class Orchestrator:
    def __init__(self, ask: Ask, *, store=None, max_retries: int = 2):
        self._ask = ask
        self._store = store
        self._max_retries = max_retries

    async def delegate(self, agent_id: str, task: str, *, task_id: str | None = None) -> Envelope:
        async def ask1(prompt: str) -> str:
            return await self._ask(agent_id, prompt)

        env = await request_envelope(
            ask1,
            task,
            agent_id=agent_id,
            message_id=str(uuid.uuid4()),
            task_id=task_id,
            max_retries=self._max_retries,
        )
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
        """Executa a cadeia de um Team com progresso por etapa e cancelável.

        Propaga CancelledError (o subprocesso é morto no runner) — cancelamento
        seguro: as etapas seguintes não rodam.
        """
        tid = task_id or str(uuid.uuid4())
        out = ChainResult()
        carry: str | None = None
        for i, role in enumerate(team.roles):
            if on_step:
                on_step(StepProgress(i, role.name, role.agent, tid, "start"))
            t0 = time.monotonic()
            env = await self.delegate(role.agent, self._role_task(role, intent, carry), task_id=tid)
            dt = time.monotonic() - t0
            out.envelopes.append(env)
            if on_step:
                state = str(env.state) if env.state else None
                on_step(StepProgress(i, role.name, role.agent, tid, "done", state, dt))
            if env.state is not EnvelopeState.DONE:
                out.escalated = True
                out.reason = f"{role.name}({role.agent}) -> {env.state}: {env.note or env.result}"
                return out
            carry = env.result
        return out


def make_agent_ask(
    session_manager: SessionManager,
    agents: dict[str, object],
    workspace: Workspace,
    *,
    timeout: float,
) -> Ask:
    """ask() real: roda o agente sob sessão (mutex/continuidade) + sandbox."""

    async def ask(agent_id: str, prompt: str) -> str:
        profile = agents[agent_id]
        ws = str(workspace.create(agent_id))
        res = await session_manager.run_in_session(
            profile, agent_id, prompt, workspace=ws, timeout=timeout
        )
        return res.stdout

    return ask
