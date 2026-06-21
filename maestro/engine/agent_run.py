"""Execução de um agente no seu workspace isolado (E2-S2).

Amarra AgentProfile (E2-S1) + Workspace (E2-S2) + Headless Runner (E1-S2):
monta o comando com a política de permissão e roda com cwd = workspace.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .adapters.base import AgentProfile
from .runner import RunResult, run_headless
from .sandbox import wrap as sandbox_wrap


@dataclass(frozen=True)
class RunPlan:
    argv: list[str]
    cwd: str


def plan_run(
    profile: AgentProfile,
    prompt: str,
    *,
    workspace: str | Path,
    session_id: str | None = None,
    resume: bool = False,
) -> RunPlan:
    """Plano de execução isolado: argv com permissões + cwd no workspace."""
    ws = str(workspace)
    argv = profile.build_command(prompt, session_id=session_id, resume=resume, workspace=ws)
    return RunPlan(argv=argv, cwd=ws)


async def run_agent(
    profile: AgentProfile,
    prompt: str,
    *,
    workspace: str | Path,
    timeout: float,
    session_id: str | None = None,
    resume: bool = False,
    shared_paths: Sequence[str] = (),
) -> RunResult:
    plan = plan_run(profile, prompt, workspace=workspace, session_id=session_id, resume=resume)
    # Confinamento estrito de SO (ADR-6): workspace rw, /tmp privado, resto ro.
    # shared_paths: diretórios de artefatos compartilhados (FR14). Falha-seguro
    # se bwrap ausente (SandboxUnavailable).
    sandboxed = sandbox_wrap(
        plan.argv, workspace=plan.cwd, rw_paths=profile.rw_paths, shared_paths=shared_paths
    )
    return await run_headless(sandboxed, timeout=timeout)
