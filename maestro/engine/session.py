"""Session Manager — continuidade de contexto + mutex por sessão (E2-S3).

- Mantém um ``session_id`` por agente (índice no Store, FR13): 1º turno usa
  ``--session-id``; turnos seguintes usam ``--resume`` (resume = sessão já existe).
- **Mutex por sessão (ADR-8):** no máximo UMA tarefa ativa por ``agent_id`` (=
  sua sessão). Prompts concorrentes à mesma sessão são serializados (o 2º espera
  o lock), evitando corromper o contexto. Agentes distintos rodam em paralelo.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Sequence

from .adapters.base import AgentProfile
from .agent_run import run_agent
from .runner import RunResult
from .state.store import Store

# Assinatura de uma função que executa um agente (injetável para testes).
RunFn = Callable[..., Awaitable[RunResult]]


class SessionManager:
    def __init__(self, store: Store):
        self._store = store
        self._locks: dict[str, asyncio.Lock] = {}

    def _new_id(self) -> str:
        return str(uuid.uuid4())

    def get_or_create_session(self, agent_id: str) -> tuple[str, bool]:
        """Retorna (session_id, is_new). is_new=True só no primeiro uso."""
        sid = self._store.get_session(agent_id)
        if sid is not None:
            return sid, False
        sid = self._new_id()
        self._store.set_session(agent_id, sid)
        return sid, True

    def session_lock(self, agent_id: str) -> asyncio.Lock:
        lock = self._locks.get(agent_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[agent_id] = lock
        return lock

    async def run_in_session(
        self,
        profile: AgentProfile,
        agent_id: str,
        prompt: str,
        *,
        workspace: str,
        timeout: float,
        run_fn: RunFn = run_agent,
        on_output=None,
        shared_paths: Sequence[str] = (),
    ) -> RunResult:
        """Executa um turno na sessão do agente, serializado pelo mutex.

        Dois modos (do profile.session_assign):
        - "caller" (claude): nós geramos o id — 1ª usa --session-id, seguintes --resume.
        - "captured" (codex): o agente gera; 1ª roda sem id e CAPTURAMOS da saída
          (persistindo o id REAL), seguintes retomam exatamente essa sessão.
        Mutex por sessão preservado. ``on_output`` (opcional): stream ao vivo (V5).
        """
        # passa extras ao run_fn só quando presentes (mantém fakes de teste simples)
        extra: dict = {}
        if on_output is not None:
            extra["on_output"] = on_output
        if shared_paths:
            extra["shared_paths"] = tuple(shared_paths)
        async with self.session_lock(agent_id):
            assign = getattr(profile, "session_assign", "caller")
            if assign == "captured":
                return await self._run_captured(
                    profile, agent_id, prompt, workspace, timeout, run_fn, extra
                )
            sid, is_new = self.get_or_create_session(agent_id)
            return await run_fn(
                profile,
                prompt,
                workspace=workspace,
                session_id=sid,
                resume=not is_new,
                timeout=timeout,
                **extra,
            )

    async def _run_captured(self, profile, agent_id, prompt, workspace, timeout, run_fn, extra):
        sid = self._store.get_session(agent_id)
        if sid is None:
            # 1ª execução: sem id; o agente cria. Capturamos o id REAL da saída.
            res = await run_fn(
                profile,
                prompt,
                workspace=workspace,
                session_id=None,
                resume=False,
                timeout=timeout,
                **extra,
            )
            captured = profile.extract_session_id(f"{res.stdout}\n{res.stderr}")
            if captured:
                self._store.set_session(agent_id, captured)
            return res
        # seguintes: retoma exatamente a sessão capturada
        return await run_fn(
            profile,
            prompt,
            workspace=workspace,
            session_id=sid,
            resume=True,
            timeout=timeout,
            **extra,
        )
