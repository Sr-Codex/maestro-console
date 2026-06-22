"""Helpers gi-free p/ notas no canvas (V9-S3) — lógica testável, sem GTK."""

from __future__ import annotations

from ..engine.notes import Note


def note_preview(note: Note, maxlen: int = 120) -> str:
    """Prévia curta do corpo (1 linha) p/ exibir no nó da nota."""
    first = note.body.strip().splitlines()[0] if note.body.strip() else ""
    return first if len(first) <= maxlen else first[: maxlen - 1] + "…"


def note_title_display(note: Note) -> str:
    """Título p/ a barra da nota (fallback se vazio)."""
    return note.title.strip() or "(sem título)"
