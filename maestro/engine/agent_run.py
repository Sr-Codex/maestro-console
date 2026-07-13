"""Execução de um agente no seu workspace isolado (E2-S2).

Amarra AgentProfile (E2-S1) + Workspace (E2-S2) + Headless Runner (E1-S2):
monta o comando com a política de permissão e roda com cwd = workspace.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .accounts import Account, ensure_config_dir, mask_paths
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
    on_output=None,
    account: Account | None = None,
) -> RunResult:
    plan = plan_run(profile, prompt, workspace=workspace, session_id=session_id, resume=resume)
    # Confinamento estrito de SO (ADR-6): workspace rw, /tmp privado, resto ro.
    # shared_paths: diretórios de artefatos compartilhados (FR14). Falha-seguro
    # se bwrap ausente (SandboxUnavailable). on_output: stream ao vivo (V5).
    # account (docs/31/ADR-28): config-dir isolado SUBSTITUI os rw_paths de config
    # (E1) + var oficial via setenv; a raiz das contas é mascarada em TODO run (E5).
    rw = profile.rw_paths
    setenv = None
    if account is not None:
        rw = [ensure_config_dir(account)]
        setenv = account.sandbox_env()
    sandboxed = sandbox_wrap(
        plan.argv, workspace=plan.cwd, rw_paths=rw, shared_paths=shared_paths,
        setenv=setenv,
        mask_paths=mask_paths(account.root if account is not None else None),
    )
    return await run_headless(sandboxed, timeout=timeout, on_output=on_output)
