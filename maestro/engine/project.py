"""Resolução do repo de projeto alvo dos floors (V8-S1).

Precedência (decisão de foundation): `override` explícito (ex.: --project) >
`MAESTRO_PROJECT` (env) > detecção pelo cwd (`git rev-parse --show-toplevel`).
Sem repo git resolvido → erro claro (ProjectError), nunca um caminho inválido.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class ProjectError(RuntimeError):
    """Não foi possível resolver um repo git de projeto."""


def _toplevel(path: Path) -> Path | None:
    """Toplevel do repo git que contém `path`, ou None se não for um repo."""
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    top = out.stdout.strip()
    return Path(top) if top else None


def resolve_project(cwd: str | Path | None = None, override: str | Path | None = None) -> Path:
    """Resolve o repo de projeto. Levanta ProjectError se não houver repo git.

    Ordem: override > MAESTRO_PROJECT (env) > cwd (ou diretório atual).
    """
    candidate = override or os.environ.get("MAESTRO_PROJECT")
    if candidate:
        top = _toplevel(Path(candidate))
        if top is None:
            raise ProjectError(f"{candidate!r} não é um repositório git")
        return top
    base = Path(cwd) if cwd is not None else Path.cwd()
    top = _toplevel(base)
    if top is None:
        raise ProjectError(f"sem repo git em {base} — defina MAESTRO_PROJECT ou use --project")
    return top
