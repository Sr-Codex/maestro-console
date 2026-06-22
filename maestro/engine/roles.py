"""Papéis ricos — role.json + CLAUDE.md/AGENTS.md por workspace (V9-S1).

Maestri-like: ao rodar um agente num papel, o console materializa a identidade do
papel no diretório de trabalho — um **role.json** portável (name, agent, color,
prompt) + **CLAUDE.md/AGENTS.md** com a instrução (claude lê CLAUDE.md; codex lê
AGENTS.md). Estende o Role existente (decisão de foundation: Opção A).
"""

from __future__ import annotations

import json
from pathlib import Path

from .teams import Role


def role_badge(role: Role) -> str:
    """Cor de badge efetiva do papel (atalho p/ a UI)."""
    return role.badge()


def agent_badges(team) -> dict[str, str]:
    """Mapa agente -> cor do badge, a partir dos papéis de um team.

    Se um agente tem mais de um papel no team, o PRIMEIRO papel vence (a ordem da
    rota). `team` pode ser None -> {}.
    """
    badges: dict[str, str] = {}
    if team is None:
        return badges
    for r in team.roles:
        badges.setdefault(r.agent, r.badge())
    return badges


def role_sidecar(role: Role) -> dict:
    """Conteúdo portável do role.json (name, agent, color, prompt)."""
    return {
        "name": role.name,
        "agent": role.agent,
        "color": role.badge(),
        "prompt": role.instruction,
    }


def _instruction_md(role: Role) -> str:
    return f"# Papel: {role.name}\n\nAgente: {role.agent}\n\n{role.instruction}\n"


def write_role_files(workspace: str | Path, role: Role) -> dict[str, str]:
    """Escreve role.json + CLAUDE.md + AGENTS.md no workspace. Retorna os caminhos."""
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    rj = ws / "role.json"
    rj.write_text(json.dumps(role_sidecar(role), ensure_ascii=False, indent=2) + "\n")
    paths["role.json"] = str(rj)

    md = _instruction_md(role)
    for fname in ("CLAUDE.md", "AGENTS.md"):
        p = ws / fname
        p.write_text(md)
        paths[fname] = str(p)
    return paths
