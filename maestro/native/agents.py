"""Helpers de agentes p/ o canvas nativo (V6-S3), sem GTK (testável).

Monta o comando do agente INTERATIVO confinado por bwrap (você digita no
terminal real). Reusa adapters + sandbox da engine — mesmo confinamento (ADR-6),
nenhum bypass.
"""

from __future__ import annotations

import os
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


def agent_argv(
    profile: AgentProfile,
    workspace: str,
    *,
    node: str | None = None,
    ask_bus_dir: str | None = None,
) -> list[str]:
    """argv do agente INTERATIVO (binário sem -p) confinado por bwrap.

    A IA roda DENTRO de um shell: ao sair da IA (ex.: ``/exit``), o card vira um
    terminal normal (shell) no mesmo sandbox — comportamento do Maestri. Reabrir a
    IA é só digitar o comando dela de novo.

    Se ``node`` e ``ask_bus_dir`` forem dados, monta o mailbox (shared_paths) e
    injeta MAESTRO_NODE/MAESTRO_ASK_BUS — habilita o ``maestro-ask`` (cabos
    interativos, ADR-11) de dentro do sandbox.
    """
    shared = [ask_bus_dir] if ask_bus_dir else []
    setenv = {}
    if node and ask_bus_dir:
        base_path = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
        setenv = {
            "MAESTRO_NODE": node,
            "MAESTRO_ASK_BUS": str(ask_bus_dir),
            # mailbox no PATH -> o agente roda `maestro-ask <nó> "..."` direto
            "PATH": f"{ask_bus_dir}:{base_path}",
        }
    # roda a IA dentro de um shell e, ao sair dela, mantém um shell interativo
    agent_bin = profile.cmd[0]
    inner = ["/bin/bash", "-c", f"{agent_bin}; exec /bin/bash -i"]
    return sandbox_wrap(
        inner,
        workspace=workspace,
        rw_paths=profile.rw_paths,
        shared_paths=shared,
        setenv=setenv,
    )
