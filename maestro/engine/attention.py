"""Attention — "o que precisa de você" (V11-S1).

Um agente precisa de atenção quando seu envelope MAIS RECENTE está num estado
não-DONE acionável (BLOCKED/FAILED/NEEDS_INPUT). Se depois ele voltou a DONE,
some da lista. Inclui notificação de desktop opcional (notify-send; no-op se
ausente). gi-free e testável.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

ATTENTION_STATES = {"BLOCKED", "FAILED", "NEEDS_INPUT"}


@dataclass(frozen=True)
class AttentionItem:
    agent: str
    state: str
    ts: float
    task_id: str | None


def attention_items(store, *, scan: int = 200) -> list[AttentionItem]:
    """Itens que precisam de atenção: o estado MAIS RECENTE de cada agente, se acionável.

    Varre os últimos `scan` envelopes (mais recentes primeiro), pega o 1º de cada
    agente (= o mais recente) e inclui só quando esse estado está em ATTENTION_STATES.
    """
    items: list[AttentionItem] = []
    seen: set[str] = set()
    for row in store.list_envelopes(limit=scan):
        agent = row.get("sender")
        if not agent or agent in seen:
            continue
        seen.add(agent)
        state = row.get("state")
        if state in ATTENTION_STATES:
            items.append(
                AttentionItem(
                    agent=agent,
                    state=state,
                    ts=row.get("ts") or 0.0,
                    task_id=row.get("task_id"),
                )
            )
    items.sort(key=lambda i: i.ts, reverse=True)
    return items


def notify(summary: str, body: str = "") -> bool:
    """Notificação de desktop via notify-send. Retorna False (no-op) se ausente/falhar."""
    if shutil.which("notify-send") is None:
        return False
    try:
        subprocess.run(["notify-send", summary, body], check=False, timeout=5)
        return True
    except Exception:
        return False
