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
import time
import uuid
from dataclasses import dataclass

from ..engine.envelope import Envelope, EnvelopeState
from ..engine.floor_run import commit_floor, run_agent_in_floor
from ..engine.orchestrator import StepProgress
from ..engine.scheduler import tick_once

# -- loop compartilhado (P1) -------------------------------------------
# Um ÚNICO event loop para toda a orquestração nativa. Antes, cada worker fazia
# asyncio.run() (= loop novo por thread), e o mutex por sessão (asyncio.Lock,
# cacheado por agent_id) ficava preso ao 1º loop → 2ª thread no MESMO agent_id
# travava (deadlock cross-loop). Rodando tudo num loop só, o asyncio.Lock
# serializa corretamente, sem deadlock.
_LOOP: asyncio.AbstractEventLoop | None = None
_LOOP_LOCK = threading.Lock()


def _shared_loop() -> asyncio.AbstractEventLoop:
    global _LOOP
    with _LOOP_LOCK:
        if _LOOP is None or _LOOP.is_closed():
            _LOOP = asyncio.new_event_loop()
            threading.Thread(target=_LOOP.run_forever, daemon=True).start()
    loop = _LOOP
    while not loop.is_running():  # espera o loop começar (race de partida)
        time.sleep(0.001)
    return loop


def _run_sync(coro):
    """Roda a coroutine no loop compartilhado e bloqueia a thread chamadora."""
    return asyncio.run_coroutine_threadsafe(coro, _shared_loop()).result()


def _report_thread_error(where: str, exc: BaseException) -> None:
    """Não engole erro de thread daemon: reporta no stderr (visível no terminal)."""
    import sys
    import traceback

    print(f"[maestro] erro em {where}:", file=sys.stderr)
    traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)


def run_team_in_thread(controller, team, intent: str, on_step) -> threading.Thread:
    """Executa controller.run_team(...) num thread; chama on_step(StepProgress)."""

    def worker():
        try:
            _run_sync(controller.run_team(team, intent, progress=on_step))
        except Exception as exc:
            _report_thread_error("run_team", exc)

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
        try:
            _run_sync(run_edge_handoff(controller, src, dst, intent, on_step))
        except Exception as exc:
            _report_thread_error("edge_handoff", exc)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t


async def run_note_to_agent(controller, note, agent_id: str, notes):
    """agent-to-note (V9-S4): a nota alimenta o prompt; a resposta volta p/ a nota.

    Mediado: delegate(agent_id, conteúdo da nota). Se DONE, ANEXA a resposta ao
    corpo da nota (colaborativo, não destrutivo) e persiste. Retorna (env, updated).
    """
    prompt = note.body.strip() or note.title
    env = await controller.delegate(agent_id, prompt)
    state = str(env.state) if env.state else None
    updated = False
    if state == "DONE" and env.result:
        suffix = f"\n\n## resposta de {agent_id}\n{env.result}"
        note.body = (note.body + suffix).strip()
        notes.save(note)
        updated = True
    return env, updated


def run_note_to_agent_in_thread(
    controller, note, agent_id: str, notes, on_done
) -> threading.Thread:
    """Executa run_note_to_agent num thread daemon; on_done(env, updated, note)."""

    def worker():
        try:
            env, updated = _run_sync(run_note_to_agent(controller, note, agent_id, notes))
            on_done(env, updated, note)
        except Exception as exc:
            _report_thread_error("note_to_agent", exc)

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
        try:
            kw = {"run_fn": run_fn} if run_fn is not None else {}
            res = _run_sync(
                run_agent_in_floor(
                    session_manager, profile, agent_id, prompt, floor, repo, timeout=180, **kw
                )
            )
            committed = commit_floor(floor, f"floor {floor.name}: {prompt[:50]}")
            on_done(res, committed)
        except Exception as exc:
            _report_thread_error("floor_agent", exc)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t


def run_routines_tick_in_thread(controller, routines, on_done=None) -> threading.Thread:
    """Roda um tick do scheduler (dispara as routines vencidas) em thread (V10-S4).

    on_done(fired: list[str]) com os ids disparados. Usa o relógio real.
    """

    def worker():
        try:
            fired = _run_sync(tick_once(controller, routines, now=time.time()))
            if on_done is not None:
                on_done(fired)
        except Exception as exc:
            _report_thread_error("routines_tick", exc)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t


def run_one_routine_in_thread(controller, routine, routines, on_done=None) -> threading.Thread:
    """Roda UMA routine imediatamente (V10-S4), em thread. on_done(RoutineRun)."""
    from ..engine.routines import run_routine_once

    def worker():
        try:
            run = _run_sync(run_routine_once(controller, routine, routines))
            if on_done is not None:
                on_done(run)
        except Exception as exc:
            _report_thread_error("routine_run", exc)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t
