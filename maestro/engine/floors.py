"""Floors — ambientes de desenvolvimento isolados via git worktree (V8-S1).

Equivalente Linux das Floors do Maestri: cada floor = um **git worktree** +
branch `floor/<name>` de um repo de projeto. O worktree compartilha o object
store do repo → criação quase instantânea, disco mínimo (ideal p/ uConsole).
Agentes podem trabalhar em branches isoladas, sem conflito.

A engine não muda: floors são opt-in. O Store é a fonte de verdade do registro;
o git é a fonte de verdade do worktree em si.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .state.store import Store

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


class FloorError(RuntimeError):
    """Erro ao criar/remover/consultar um floor."""


@dataclass(frozen=True)
class Floor:
    name: str
    branch: str
    path: str
    base_branch: str


def _check_name(name: str) -> str:
    if not _SAFE_NAME.match(name):
        raise FloorError(f"nome de floor inválido (apenas [A-Za-z0-9_-]): {name!r}")
    return name


def _git(repo: Path, *args: str) -> str:
    """Roda git no repo; levanta FloorError com stderr em caso de falha."""
    res = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise FloorError(f"git {' '.join(args)} falhou: {res.stderr.strip()}")
    return res.stdout.strip()


class Floors:
    """Gerencia floors (worktrees) de um repo de projeto, registrados no Store."""

    def __init__(self, repo_path: str | Path, base_dir: str | Path, store: Store):
        self.repo = Path(repo_path)
        self.base = Path(base_dir)
        self._store = store
        _git(self.repo, "rev-parse", "--git-dir")  # levanta FloorError se não for repo git

    def path(self, name: str) -> Path:
        return self.base / _check_name(name)

    def create(self, name: str, base_branch: str = "HEAD") -> Floor:
        _check_name(name)
        if self._store.get_floor(name) is not None:
            raise FloorError(f"floor {name!r} já existe")
        wt = self.path(name)
        branch = f"floor/{name}"
        self.base.mkdir(parents=True, exist_ok=True)
        # cria worktree + branch nova a partir de base_branch
        _git(self.repo, "worktree", "add", "-b", branch, str(wt), base_branch)
        self._store.add_floor(name, branch, str(wt), base_branch)
        return Floor(name=name, branch=branch, path=str(wt), base_branch=base_branch)

    def get(self, name: str) -> Floor | None:
        row = self._store.get_floor(name)
        if row is None:
            return None
        return Floor(
            name=row["name"],
            branch=row["branch"],
            path=row["path"],
            base_branch=row["base_branch"],
        )

    def list(self) -> list[Floor]:
        return [
            Floor(name=r["name"], branch=r["branch"], path=r["path"], base_branch=r["base_branch"])
            for r in self._store.list_floors()
        ]

    def remove(self, name: str, *, delete_branch: bool = True) -> None:
        floor = self.get(name)
        if floor is None:
            raise FloorError(f"floor {name!r} não existe")
        # remove o worktree (força: descarta mudanças não commitadas no worktree)
        _git(self.repo, "worktree", "remove", "--force", floor.path)
        _git(self.repo, "worktree", "prune")
        if delete_branch:
            # -D: remove mesmo sem merge (o registro é nosso, não do git)
            try:
                _git(self.repo, "branch", "-D", floor.branch)
            except FloorError:
                pass  # branch já some junto em alguns casos; não é fatal
        self._store.remove_floor(name)
