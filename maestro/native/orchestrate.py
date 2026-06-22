"""Rodar um time da engine a partir do app nativo, em thread (V6-S4), sem GTK.

A orquestração é async (engine headless/bwrap); rodamos num thread daemon e
entregamos cada StepProgress via callback. O app GTK embrulha o callback com
GLib.idle_add para atualizar a UI com segurança (thread-safe).
"""

from __future__ import annotations

import asyncio
import threading


def run_team_in_thread(controller, team, intent: str, on_step) -> threading.Thread:
    """Executa controller.run_team(...) num thread; chama on_step(StepProgress)."""

    def worker():
        asyncio.run(controller.run_team(team, intent, progress=on_step))

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t
