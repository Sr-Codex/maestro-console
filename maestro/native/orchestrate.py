"""Rodar orquestração da engine a partir do app nativo, em thread (V6-S4/V7-S3).

A orquestração é async (engine headless/bwrap); rodamos num thread daemon e
entregamos cada StepProgress via callback. O app GTK embrulha o callback com
GLib.idle_add para atualizar a UI com segurança (thread-safe).

V7-S3: handoff MEDIADO por cabo (A -> B). O cabo é o gesto; o motor é o
`controller.delegate` que já existe (envelope JSON + bwrap + log). A roda com a
intenção; se DONE, B roda com o `result` de A. Se A ou B não retornarem DONE,
escala (para) — nunca trava (mesma filosofia do orchestrator).
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass

from ..engine.envelope import Envelope, EnvelopeState
from ..engine.floor_run import commit_floor, run_agent_in_floor
from ..engine.orchestrator import StepProgress


def run_team_in_thread(controller, team, intent: str, on_step) -> threading.Thread:
    """Executa controller.run_team(...) num thread; chama on_step(StepProgress)."""

    def worker():
        asyncio.run(controller.run_team(team, intent, progress=on_step))

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t


@dataclass
class EdgeHandoffResult:
    """Resultado de um handoff por cabo A -> B."""

    src: Envelope
    dst: Envelope | None
    escalated: bool
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return not self.escalated


async def run_edge_handoff(
    controller, src: str, dst: str, intent: str, on_step=None
) -> EdgeHandoffResult:
    """Handoff mediado A -> B: A roda `intent`; se DONE, B roda com o result de A.

    Emite StepProgress (start/done) por nó se `on_step` for dado. Escala (para
    antes de B) se A não retornar DONE; marca escalated se B não retornar DONE.
    """
    task_id = str(uuid.uuid4())

    def emit(i: int, agent: str, phase: str, state: str | None = None) -> None:
        if on_step is not None:
            on_step(StepProgress(i, agent, agent, task_id, phase, state))

    emit(0, src, "start")
    env_a = await controller.delegate(src, intent)
    emit(0, src, "done", str(env_a.state) if env_a.state else None)
    if env_a.state is not EnvelopeState.DONE:
        return EdgeHandoffResult(
            src=env_a,
            dst=None,
            escalated=True,
            reason=f"{src} retornou {env_a.state}: {env_a.note or env_a.result}",
        )

    carry = env_a.result or ""
    emit(1, dst, "start")
    env_b = await controller.delegate(dst, carry)
    emit(1, dst, "done", str(env_b.state) if env_b.state else None)
    escalated = env_b.state is not EnvelopeState.DONE
    reason = f"{dst} retornou {env_b.state}: {env_b.note or env_b.result}" if escalated else None
    return EdgeHandoffResult(src=env_a, dst=env_b, escalated=escalated, reason=reason)


def run_edge_handoff_in_thread(controller, src, dst, intent: str, on_step) -> threading.Thread:
    """Executa run_edge_handoff(...) num thread daemon; chama on_step(StepProgress)."""

    def worker():
        asyncio.run(run_edge_handoff(controller, src, dst, intent, on_step))

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t


def run_floor_agent_in_thread(
    session_manager,
    profile,
    agent_id: str,
    prompt: str,
    floor,
    repo,
    on_done,
    *,
    run_fn=None,
) -> threading.Thread:
    """Roda um agente NUM floor (V8-S5) em thread; snapshot do trabalho na branch.

    on_done(res, committed): res = RunResult do agente; committed = bool (houve
    commit na branch do floor). `run_fn` injetável (testes).
    """

    def worker():
        kw = {"run_fn": run_fn} if run_fn is not None else {}
        res = asyncio.run(
            run_agent_in_floor(
                session_manager, profile, agent_id, prompt, floor, repo, timeout=180, **kw
            )
        )
        committed = commit_floor(floor, f"floor {floor.name}: {prompt[:50]}")
        on_done(res, committed)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t
