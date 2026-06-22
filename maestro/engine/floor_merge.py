"""Merge preview + integração de um floor na base (V8-S4).

Preview SEM tocar a árvore: `git diff --numstat base...floor` (mudanças do floor
desde a divergência) + `git merge-tree --write-tree --name-only` (detecta
conflitos sem escrever nada no worktree). Integração: merge --no-ff da branch do
floor na base, recusando se houver conflito.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .floors import Floor, FloorError, _git


@dataclass
class MergePreview:
    base: str
    files: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    conflicts: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.conflicts


@dataclass
class MergeResult:
    ok: bool
    conflicts: list[str] = field(default_factory=list)
    reason: str | None = None


def _base_ref(repo: Path, floor: Floor) -> str:
    """Branch base do floor; resolve 'HEAD' p/ a branch atual do worktree principal."""
    b = floor.base_branch
    if b and b != "HEAD":
        return b
    out = subprocess.run(
        ["git", "-C", str(repo), "symbolic-ref", "--short", "HEAD"],
        capture_output=True,
        text=True,
    )
    return out.stdout.strip() or "HEAD"


def _current_branch(repo: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "symbolic-ref", "--short", "HEAD"],
        capture_output=True,
        text=True,
    )
    return out.stdout.strip()


def _conflicts(repo: Path, base: str, branch: str) -> list[str]:
    """Arquivos que conflitariam num merge — via merge-tree, sem escrever no worktree."""
    r = subprocess.run(
        ["git", "-C", str(repo), "merge-tree", "--write-tree", "--name-only", base, branch],
        capture_output=True,
        text=True,
    )
    if r.returncode == 0:
        return []  # sem conflito
    # saída: linha1 = OID da árvore; depois nomes em conflito até uma linha em branco
    lines = r.stdout.splitlines()
    conflicts = []
    for line in lines[1:]:
        if line == "":
            break
        conflicts.append(line)
    return conflicts


def merge_preview(repo: str | Path, floor: Floor) -> MergePreview:
    repo = Path(repo)
    base = _base_ref(repo, floor)
    pv = MergePreview(base=base)
    numstat = _git(repo, "diff", "--numstat", f"{base}...{floor.branch}")
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        add, dele, path = parts
        pv.files.append(path)
        pv.insertions += int(add) if add.isdigit() else 0  # "-" em binários
        pv.deletions += int(dele) if dele.isdigit() else 0
    pv.conflicts = _conflicts(repo, base, floor.branch)
    return pv


def merge_floor(repo: str | Path, floor: Floor, *, message: str | None = None) -> MergeResult:
    """Integra a branch do floor na base. Recusa (sem mexer) se houver conflito."""
    repo = Path(repo)
    base = _base_ref(repo, floor)
    cur = _current_branch(repo)
    if cur != base:
        return MergeResult(
            ok=False,
            reason=f"worktree principal está em {cur!r}, não em {base!r} — faça checkout de {base}",
        )
    pv = merge_preview(repo, floor)
    if pv.conflicts:
        return MergeResult(ok=False, conflicts=pv.conflicts, reason="conflitos impedem o merge")
    msg = message or f"merge floor {floor.name}"
    try:
        _git(repo, "merge", "--no-ff", "--no-edit", "-m", msg, floor.branch)
    except FloorError as e:
        return MergeResult(ok=False, reason=str(e))
    return MergeResult(ok=True)
