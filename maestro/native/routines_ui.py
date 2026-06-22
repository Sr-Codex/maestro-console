"""Helpers gi-free p/ routines no canvas (V10-S4) — lógica testável, sem GTK."""

from __future__ import annotations


def routine_rows(routines) -> list[dict]:
    """Linhas p/ a lista da UI (nome, agente, intervalo, on/off, run_count)."""
    rows = []
    for r in routines.list():
        rows.append(
            {
                "id": r.id,
                "name": r.name,
                "agent": r.agent,
                "interval_s": r.interval_s,
                "enabled": r.enabled,
                "run_count": r.run_count,
                "label": f"{r.name} · {r.agent} · {r.interval_s:.0f}s · "
                f"{'on' if r.enabled else 'off'} · runs={r.run_count}",
            }
        )
    return rows


def parse_steps(prompt: str) -> list[str]:
    """Quebra o prompt em passos por ' && ' (multi-step)."""
    return [s.strip() for s in prompt.split(" && ") if s.strip()]
