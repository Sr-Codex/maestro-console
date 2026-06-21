"""Histórico de handoffs — leitura legível do envelope_log (E4-S3 / FR12)."""

from __future__ import annotations

from typing import Any

from .state.store import Store


def recent(store: Store, limit: int = 20) -> list[dict[str, Any]]:
    return store.list_envelopes(limit=limit)


def format_line(row: dict[str, Any]) -> str:
    sender = row.get("sender") or "?"
    recipient = row.get("recipient") or "?"
    state = row.get("state") or "-"
    return f"{sender} -> {recipient} [{state}] task={row.get('task_id') or '-'}"


def format_history(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(sem histórico)"
    return "\n".join(format_line(r) for r in rows)
