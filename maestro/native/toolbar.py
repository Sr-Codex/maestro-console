"""Composição do menu de ações da toolbar (P3) — gi-free, testável.

Os comandos do canvas (rodar time, handoff, nota, floors, routines) vão para um
menu "☰ ações" para descongestionar a toolbar. Esta função decide quais itens
aparecem (conforme os recursos disponíveis) e devolve (label, key); o canvas
mapeia key -> callback.
"""

from __future__ import annotations


def action_menu_items(
    *,
    has_controller: bool,
    has_edges: bool,
    has_notes: bool,
    has_floors: bool,
    has_routines: bool,
    team_name: str = "coder-reviewer",
    has_groups: bool = False,
) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = [
        ("➕ novo terminal", "newterm"),
        ("📁 árvore de arquivos", "filetree"),
        ("🗂️ workspaces", "workspaces"),
        ("👤 contas de agente", "accounts"),  # docs/31/ADR-28: multi-conta por nó
    ]
    if has_controller:
        items.append((f"▶ rodar time ({team_name})", "run_team"))
    if has_controller and has_edges:
        items.append(("▶ disparar handoff", "handoff"))
    if has_notes:
        items.append(("📝 nova nota", "note"))
    if has_groups:
        items.append(("⬚ novo grupo", "group"))
    if has_controller and has_groups:
        items.append(("🧩 montar equipe", "team"))
    if has_floors:
        items.append(("🧱 floors…", "floors"))
    if has_routines and has_controller:
        items.append(("⏰ routines…", "routines"))
    return items
