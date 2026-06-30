"""Attention — "o que precisa de você" (V11-S1).

Um agente precisa de atenção quando seu envelope MAIS RECENTE está num estado
não-DONE acionável (BLOCKED/FAILED/NEEDS_INPUT). Se depois ele voltou a DONE,
some da lista. Inclui notificação de desktop opcional (notify-send; no-op se
ausente). gi-free e testável.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

# som de alerta: 1º arquivo existente; tocado por paplay/pw-play (PipeWire/Pulse), fire-and-forget
_ALERT_SOUNDS = (
    "/usr/share/sounds/freedesktop/stereo/complete.oga",
    "/usr/share/sounds/freedesktop/stereo/message.oga",
    "/usr/share/sounds/freedesktop/stereo/bell.oga",
)


def play_alert_sound() -> bool:
    """Toca um som de alerta curto (não-bloqueante). False se não há player/arquivo."""
    path = next((p for p in _ALERT_SOUNDS if os.path.exists(p)), None)
    if path is None:
        return False
    for player in ("paplay", "pw-play"):
        if shutil.which(player) is not None:
            try:
                subprocess.Popen(  # fire-and-forget: não bloqueia a UI
                    [player, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except OSError:
                continue
    return False

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


def notify(summary: str, body: str = "", *, sound: bool = True) -> bool:
    """Notificação de desktop (notify-send) + SOM de alerta (sound=True). Retorna False se o
    notify-send está ausente/falha; o som é best-effort independente (não afeta o retorno)."""
    if sound:
        play_alert_sound()
    if shutil.which("notify-send") is None:
        return False
    try:
        subprocess.run(["notify-send", summary, body], check=False, timeout=5)
        return True
    except Exception:
        return False
