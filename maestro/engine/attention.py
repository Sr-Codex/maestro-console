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


# Estados VISUAIS do nó que pedem atenção (setados no canvas, ex.: monitor de quietude →
# "waiting"), independentes do fluxo de envelopes. Ver `attention_nids`.
ATTENTION_VISUAL_STATES = {"waiting", "blocked", "failed"}


def attention_nids(envelope_items, node_states, present) -> list[str]:
    """União ORDENADA dos nós que precisam de você: (1) agentes cujo envelope mais recente é
    acionável (`envelope_items` = saída de `attention_items`) + (2) nós cujo ESTADO VISUAL atual
    (`node_states`: nid→estado) está em `ATTENTION_VISUAL_STATES` — ex.: o monitor de quietude
    marca "waiting" sem gerar envelope. Dedup preservando ordem (envelope primeiro); filtra por
    `present` (nids que existem no canvas). gi-free e testável.

    *Por quê:* o contador "⚠ N" e o "pular pro próximo" liam SÓ envelopes, então um agente que
    parou esperando input (detectado pelo monitor, não por envelope) não entrava na conta.
    """
    present = set(present)
    out: list[str] = []
    seen: set[str] = set()
    for it in envelope_items:
        agent = getattr(it, "agent", it)
        if agent in present and agent not in seen:
            seen.add(agent)
            out.append(agent)
    for nid, st in node_states.items():
        if nid in present and nid not in seen and st in ATTENTION_VISUAL_STATES:
            seen.add(nid)
            out.append(nid)
    return out


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
