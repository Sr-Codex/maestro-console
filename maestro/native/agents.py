"""Helpers de agentes p/ o canvas nativo (V6-S3), sem GTK (testável).

Monta o comando do agente INTERATIVO confinado por bwrap (você digita no
terminal real). Reusa adapters + sandbox da engine — mesmo confinamento (ADR-6),
nenhum bypass.
"""

from __future__ import annotations

import shutil

from ..engine.adapters.base import AgentProfile, load_profiles
from ..engine.sandbox import wrap as sandbox_wrap

# cores por estado (mesma paleta da Web)
STATE_COLORS = {
    "idle": "#6b7280",
    "busy": "#3b82f6",
    "blocked": "#f59e0b",
    "failed": "#ef4444",
    "done": "#22c55e",
}


def installed_agents() -> dict[str, AgentProfile]:
    """Perfis cujo CLI está instalado (binário no PATH)."""
    return {n: p for n, p in load_profiles().items() if shutil.which(p.cmd[0])}


def agent_argv(profile: AgentProfile, workspace: str) -> list[str]:
    """argv do agente INTERATIVO (binário sem -p) confinado por bwrap."""
    return sandbox_wrap([profile.cmd[0]], workspace=workspace, rw_paths=profile.rw_paths)
