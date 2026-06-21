"""Artifacts — canal de artefatos por CAMINHO entre agentes (E2-S4 / FR14).

Workspaces são privados por agente; para um agente passar um artefato a outro,
usa-se um **diretório compartilhado** (montado rw nos sandboxes dos envolvidos).
Artefatos grandes trafegam por **caminho** (referência em ``Envelope.artifacts``),
nunca inline.
"""

from __future__ import annotations

import re
from pathlib import Path

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._/-]+$")


def _check(name: str) -> str:
    if not _SAFE_NAME.match(name) or ".." in Path(name).parts or name.startswith("/"):
        raise ValueError(f"nome de artefato inválido: {name!r}")
    return name


class Artifacts:
    """Diretório compartilhado de artefatos (por execução/orquestração)."""

    def __init__(self, base_dir: str | Path):
        self.base = Path(base_dir)

    def ensure(self) -> Path:
        self.base.mkdir(parents=True, exist_ok=True)
        return self.base

    def path(self, name: str) -> Path:
        return self.base / _check(name)

    def exists(self, name: str) -> bool:
        return self.path(name).is_file()

    def write(self, name: str, content: str) -> Path:
        p = self.path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return p

    def read(self, name: str) -> str:
        return self.path(name).read_text()

    def list(self) -> list[str]:
        if not self.base.is_dir():
            return []
        return sorted(str(p.relative_to(self.base)) for p in self.base.rglob("*") if p.is_file())
