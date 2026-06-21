"""Workspace isolado por agente (E2-S2 / ADR-6).

Cada agente roda com cwd dedicado sob um diretório base. O ``agent_id`` é
validado para impedir path traversal (isolamento é requisito de segurança).
A *negação de escrita fora* do workspace é garantida pela política de permissão
do próprio CLI (claude --permission-mode/--add-dir; codex --sandbox
workspace-write), que o adapter aplica — nunca por bypass.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _check(agent_id: str) -> str:
    if not _SAFE_ID.match(agent_id):
        raise ValueError(f"agent_id inválido (apenas [A-Za-z0-9_-]): {agent_id!r}")
    return agent_id


class Workspace:
    """Gerencia diretórios de trabalho isolados por agente."""

    def __init__(self, base_dir: str | Path):
        self.base = Path(base_dir)

    def path(self, agent_id: str) -> Path:
        return self.base / _check(agent_id)

    def create(self, agent_id: str) -> Path:
        p = self.path(agent_id)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def exists(self, agent_id: str) -> bool:
        return self.path(agent_id).is_dir()

    def cleanup(self, agent_id: str) -> None:
        p = self.path(agent_id)
        if p.is_dir():
            shutil.rmtree(p)
