"""Helpers gi-free p/ floors no canvas nativo (V8-S5) — lógica testável, sem GTK.

O GTK só fia: resolve os floors do projeto, formata linhas/preview/merge para a
janela. A regra de negócio mora na engine (Floors, merge_preview, merge_floor).
"""

from __future__ import annotations

from pathlib import Path

from ..engine.floor_merge import MergePreview, MergeResult
from ..engine.floors import Floors
from ..engine.project import ProjectError, resolve_project


def resolve_floors(store, base_dir: str | Path, project_override=None) -> Floors | None:
    """Constrói Floors p/ o repo do cwd (ou override); None se não houver repo git."""
    try:
        repo = resolve_project(override=project_override)
    except ProjectError:
        return None
    return Floors(repo, base_dir, store)


def floor_rows(floors: Floors) -> list[dict[str, str]]:
    """Linhas p/ a lista da UI."""
    return [{"name": f.name, "branch": f.branch, "path": f.path} for f in floors.list()]


def preview_text(pv: MergePreview) -> str:
    """Texto legível de um MergePreview (diff + conflitos)."""
    head = f"base: {pv.base} | {len(pv.files)} arquivo(s) +{pv.insertions}/-{pv.deletions}"
    files = "\n".join(f"  ~ {p}" for p in pv.files)
    if pv.conflicts:
        conf = "\n".join(f"  ! {c}" for c in pv.conflicts)
        tail = f"\nCONFLITOS ({len(pv.conflicts)}):\n{conf}"
    else:
        tail = "\nsem conflitos — merge limpo possível"
    return f"{head}\n{files}{tail}" if pv.files else f"{head}{tail}"


def merge_text(r: MergeResult) -> str:
    """Texto legível de um MergeResult."""
    if r.ok:
        return "integrado com sucesso"
    msg = f"merge não realizado: {r.reason}"
    if r.conflicts:
        msg += "\n" + "\n".join(f"  ! {c}" for c in r.conflicts)
    return msg
