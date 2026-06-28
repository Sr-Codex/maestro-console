"""Notas colaborativas no canvas + ponte nota↔markdown (V9-S2).

Notas são markdown persistido (tabela `notes`). O "agent-to-note" (decisão de
foundation) é MEDIADO: a nota vira um arquivo `.md` no workspace do agente que
ele lê/escreve; depois relemos o arquivo de volta para a nota. Sem PTY.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from .state.store import Store

NOTE_FILENAME = "nota.md"


@dataclass
class Note:
    id: str
    title: str
    body: str
    x: float
    y: float
    color: str = ""  # cor da nota (C4); "" = padrão (amarelo)
    pinned: bool = False  # fixada: não arrasta (C4)
    font: str = ""  # fonte da nota (Pango desc, ex.: "Sans 12"); "" = padrão do tema
    width: float = 200.0  # tamanho do corpo (resize); persistido
    height: float = 110.0


def render_markdown(note: Note) -> str:
    """Nota -> markdown (# título + corpo). Round-trippable por parse_markdown."""
    return f"# {note.title}\n\n{note.body}\n" if note.title else f"{note.body}\n"


def parse_markdown(text: str) -> tuple[str, str]:
    """Markdown -> (título, corpo). H1 inicial vira título; resto = corpo."""
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        rest = lines[1:]
        # remove uma única linha em branco separadora
        if rest and rest[0] == "":
            rest = rest[1:]
        return title, "\n".join(rest).rstrip("\n")
    return "", text.rstrip("\n")


def md_wrap(text: str, sel_start: int, sel_end: int, left: str, right: str) -> tuple[str, int, int]:
    """Envolve [sel_start, sel_end) com `left`/`right` (ex.: ** .. **). Retorna
    (novo_texto, cursor_start, cursor_end). Seleção vazia → insere marcadores e
    posiciona o cursor ENTRE eles (cursor_start == cursor_end)."""
    middle = text[sel_start:sel_end]
    new = text[:sel_start] + left + middle + right + text[sel_end:]
    cur_start = sel_start + len(left)
    return new, cur_start, cur_start + len(middle)


def md_line_prefix(text: str, cursor: int, prefix: str) -> tuple[str, int]:
    """Insere `prefix` (ex.: '# ', '- [ ] ', '- ') no início da linha que contém
    `cursor`. Retorna (novo_texto, novo_cursor)."""
    line_start = text.rfind("\n", 0, cursor) + 1  # 0 se não houver \n antes
    new = text[:line_start] + prefix + text[line_start:]
    return new, cursor + len(prefix)


def _md_inline(s: str) -> str:
    """Inline markdown → Pango (em texto já escapado). Ordem evita colisão (código→negrito→
    tachado→itálico; negrito antes do itálico p/ não confundir ** com *)."""
    s = re.sub(r"`([^`]+)`", r"<tt>\1</tt>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"~~([^~]+)~~", r"<s>\1</s>", s)
    s = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", s)
    return s


def md_to_pango(text: str) -> str:
    """Markdown simples (o que a pílula insere) → markup do Pango, p/ exibir a nota formatada
    num Gtk.Label. Escapa &,<,> antes; cobre heading, lista, checkbox e inline. Não é um parser
    markdown completo — casos exóticos ficam como texto."""
    out = []
    for raw in text.split("\n"):
        line = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        stripped = line.lstrip(" ")
        indent = line[: len(line) - len(stripped)]
        heading = False
        if stripped.startswith("# "):
            line, heading = indent + stripped[2:], True
        elif stripped[:6] in ("- [ ] ", "- [x] ", "- [X] "):
            mark = "☐" if stripped[3] == " " else "☑"  # ☐ / ☑
            line = indent + mark + " " + stripped[6:]
        elif stripped[:2] in ("- ", "* "):
            line = indent + "• " + stripped[2:]  # •
        line = _md_inline(line)
        if heading:
            line = f'<span size="larger" weight="bold">{line}</span>'
        out.append(line)
    return "\n".join(out)


def note_to_file(note: Note, directory: str | Path, filename: str = NOTE_FILENAME) -> Path:
    """Materializa a nota como markdown no diretório do agente (agent-to-note)."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    p = d / filename
    p.write_text(render_markdown(note))
    return p


def file_to_note(note: Note, directory: str | Path, filename: str = NOTE_FILENAME) -> Note:
    """Relê o arquivo de volta para a nota (título/corpo atualizados). id/pos mantidos."""
    p = Path(directory) / filename
    if not p.exists():
        return note
    title, body = parse_markdown(p.read_text())
    # se o arquivo não tinha H1, preserva o título atual da nota
    return Note(
        id=note.id,
        title=title or note.title,
        body=body,
        x=note.x,
        y=note.y,
        color=note.color,
        pinned=note.pinned,
        font=note.font,  # preserva fonte/tamanho no round-trip do agent-to-note
        width=note.width,
        height=note.height,
    )


class Notes:
    """CRUD de notas sobre o Store."""

    def __init__(self, store: Store):
        self._store = store

    def create(self, title: str, body: str = "", x: float = 0.0, y: float = 0.0) -> Note:
        note = Note(id=str(uuid.uuid4()), title=title, body=body, x=x, y=y)
        self.save(note)
        return note

    @staticmethod
    def _row_to_note(row) -> Note:
        return Note(
            id=row["id"],
            title=row["title"],
            body=row["body"],
            x=row["x"],
            y=row["y"],
            color=row["color"] if "color" in row.keys() else "",
            pinned=bool(row["pinned"]) if "pinned" in row.keys() else False,
            font=row["font"] if "font" in row.keys() else "",
            width=row["width"] if "width" in row.keys() else 200.0,
            height=row["height"] if "height" in row.keys() else 110.0,
        )

    def get(self, note_id: str) -> Note | None:
        row = self._store.get_note(note_id)
        return self._row_to_note(row) if row is not None else None

    def list(self) -> list[Note]:
        return [self._row_to_note(r) for r in self._store.list_notes()]

    def save(self, note: Note) -> None:
        self._store.upsert_note(
            note.id, note.title, note.body, note.x, note.y, note.color, int(note.pinned),
            note.font, note.width, note.height
        )

    def set_position(self, note_id: str, x: float, y: float) -> None:
        n = self.get(note_id)
        if n is not None:
            n.x, n.y = x, y
            self.save(n)

    def delete(self, note_id: str) -> None:
        self._store.remove_note(note_id)
