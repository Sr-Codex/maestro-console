"""Rodar um agente DENTRO de um floor (worktree) + snapshot do trabalho (V8-S2).

O agente roda com cwd = worktree do floor, confinado por bwrap (ADR-6). Para o
git funcionar no worktree (objects/refs vivem no `.git` do repo principal),
liberamos esse `.git` como caminho compartilhado rw.

Como o caminho de dados é mediado/headless, o console faz o **commit** das
mudanças do agente na branch do floor (snapshot) — assim o merge preview (V8-S4)
tem commits para comparar. O agente edita; o console versiona.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import budget
from .agent_run import run_agent
from .floors import Floor
from .runner import RunResult, RunStatus


async def run_agent_in_floor(
    session_manager,
    profile,
    agent_id: str,
    prompt: str,
    floor: Floor,
    repo: str | Path,
    *,
    timeout: float,
    on_output=None,
    run_fn=run_agent,
    store=None,
) -> RunResult:
    """Executa o agente com cwd = worktree do floor, sob sessão/mutex + bwrap.

    Libera o `.git` do repo (rw) p/ o git do worktree funcionar (commits/refs).

    Gate de budget (docs/29 §5.2): floor run gastava FORA do freio do delegate — mesmo
    invariante, todas as entradas. No hard: FAIL-FAST com texto de pausa (nunca "falhou"),
    SEM retenção — reter re-executaria fora do cwd do floor (emenda Fable E3).
    """
    if store is not None:
        try:
            paused = budget.is_paused(store)
        except Exception:
            paused = False  # freio best-effort (mesma postura do gate do delegate)
        if paused:
            return RunResult(
                status=RunStatus.FAILED, returncode=None, stdout="",
                stderr="pausado por budget — libere no Limites (💰) e rode de novo.",
                duration_s=0.0, timed_out=False,
            )
    git_dir = str(Path(repo) / ".git")
    return await session_manager.run_in_session(
        profile,
        agent_id,
        prompt,
        workspace=floor.path,
        timeout=timeout,
        run_fn=run_fn,
        on_output=on_output,
        shared_paths=[git_dir],
    )


def commit_floor(floor: Floor, message: str) -> bool:
    """Faz snapshot das mudanças do worktree na branch do floor.

    Retorna True se houve commit; False se não havia nada a commitar. Roda fora
    do sandbox (o console tem acesso pleno ao repo).
    """
    wt = floor.path
    subprocess.run(["git", "-C", wt, "add", "-A"], check=True, capture_output=True, text=True)
    status = subprocess.run(
        ["git", "-C", wt, "status", "--porcelain"], capture_output=True, text=True, check=True
    )
    if not status.stdout.strip():
        return False  # nada staged/alterado
    subprocess.run(
        ["git", "-C", wt, "commit", "-m", message], check=True, capture_output=True, text=True
    )
    return True
