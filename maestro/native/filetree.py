"""Árvore de arquivos do projeto (Fase B) — helper gi-free e testável.

Lista o conteúdo de um diretório (pastas primeiro, ordenado alfabético, ocultos
filtráveis), de forma segura (erros de permissão/IO viram lista vazia). A parte
gráfica (nó na tela, expandir/colapsar) fica no canvas.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Entry:
    name: str
    is_dir: bool
    path: str


def list_children(path: str | Path, *, show_hidden: bool = False) -> list[Entry]:
    """Filhos diretos de ``path``: pastas primeiro, depois arquivos (alfabético)."""
    p = Path(path)
    try:
        raw = list(p.iterdir())
    except (OSError, PermissionError, NotADirectoryError):
        return []
    out: list[Entry] = []
    for e in raw:
        if not show_hidden and e.name.startswith("."):
            continue
        try:
            is_dir = e.is_dir()
        except OSError:
            is_dir = False
        out.append(Entry(name=e.name, is_dir=is_dir, path=str(e)))
    out.sort(key=lambda x: (not x.is_dir, x.name.lower()))  # dir primeiro, depois nome
    return out
