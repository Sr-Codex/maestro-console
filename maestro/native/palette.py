"""Command palette (Batuta) — busca fuzzy sobre entidades (V11-S2), sem GTK.

`fuzzy` faz match por subsequência (case-insensitive) com score (bônus p/ início
e contiguidade). `build_palette_items` monta a lista a partir das fontes do app.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaletteItem:
    kind: str  # action | agent | team | floor | note | routine
    label: str
    ref: str
    hint: str = ""  # atalho exibido à direita (ex.: "Ctrl+Shift+L"); só p/ ações


def fuzzy_score(query: str, text: str) -> int | None:
    """Score do match (maior = melhor) ou None se `query` não é subsequência de `text`."""
    q, t = query.lower(), text.lower()
    if not q:
        return 0
    score = 0
    ti = 0
    last = -1
    for ch in q:
        idx = t.find(ch, ti)
        if idx == -1:
            return None
        score += 1
        if idx == 0:
            score += 3  # bônus por casar no início
        if idx == last + 1:
            score += 2  # bônus por contiguidade
        last = idx
        ti = idx + 1
    return score


def fuzzy(query: str, items, key=lambda i: i.label):
    """Filtra+ordena items por score desc (empate: label asc). Query vazia = todos."""
    if not query.strip():
        return list(items)
    scored = []
    for it in items:
        s = fuzzy_score(query, key(it))
        if s is not None:
            scored.append((s, key(it), it))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [it for _, _, it in scored]


def build_action_items(actions=()) -> list[PaletteItem]:
    """Itens de AÇÃO (D1): cada `actions` é (label, ref, hint). hint = atalho exibido."""
    out: list[PaletteItem] = []
    for label, ref, hint in actions:
        out.append(PaletteItem("action", label, ref, hint))
    return out


# B2 — texto do rodapé que ENSINA atalhos (muda conforme o modo atual).
_HINTS_BASE = (
    "Ctrl+P paleta · Ctrl+Shift+L conectar · Ctrl+Shift+W fechar · "
    "Ctrl+Shift+A atenção · Ctrl+Shift+F enquadrar · Ctrl+Shift+1-9 focar"
)


def hintbar_text(*, connect: bool = False, picking: bool = False) -> str:
    """Dica contextual do rodapé (Zellij-like). connect/picking = modo conectar."""
    if connect:
        if picking:
            return "CONECTAR: clique no DESTINO · Esc cancela"
        return "CONECTAR: clique no nó de ORIGEM · Esc cancela"
    return _HINTS_BASE


def build_palette_items(
    *, agents=(), teams=(), floors=(), notes=(), routines=()
) -> list[PaletteItem]:
    """Monta os itens da palette a partir das fontes (tipos da engine)."""
    items: list[PaletteItem] = []
    for a in agents:
        items.append(PaletteItem("agent", f"⬡ {a}", a))
    for t in teams:
        items.append(PaletteItem("team", f"team · {t}", t))
    for f in floors:
        items.append(PaletteItem("floor", f"floor · {f.name}", f.name))
    for n in notes:
        items.append(PaletteItem("note", f"nota · {n.title or n.id[:6]}", n.id))
    for r in routines:
        items.append(PaletteItem("routine", f"routine · {r.name}", r.name))
    return items
