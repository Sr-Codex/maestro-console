"""Bootstrap — monta a engine com defaults sensatos (E5-S1).

Liga Store + Registry + SessionManager + Workspace + adapters + Orchestrator e
devolve um TUIController pronto. Registra só os agentes cujos CLIs estão de fato
instalados. Estado em MAESTRO_HOME (default ~/.local/share/maestro-console).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .engine.adapters.base import load_profiles
from .engine.orchestrator import Orchestrator, make_agent_ask
from .engine.registry import Registry
from .engine.session import SessionManager
from .engine.state.store import Store
from .engine.workspace import Workspace
from .tui.controller import TUIController


def default_home() -> Path:
    env = os.environ.get("MAESTRO_HOME")
    return Path(env) if env else Path.home() / ".local" / "share" / "maestro-console"


def build_controller(*, home: str | Path | None = None, timeout: float = 180.0):
    """Retorna (TUIController, Store). Lembre de fechar o Store ao sair."""
    base = Path(home) if home is not None else default_home()
    base.mkdir(parents=True, exist_ok=True)
    store = Store(base / "maestro.db")
    registry = Registry(store)
    sm = SessionManager(store)
    ws = Workspace(base / "workspaces")

    profiles = load_profiles()
    agents = {n: p for n, p in profiles.items() if shutil.which(p.cmd[0])}
    for name in agents:
        registry.register(name, name)

    orch = Orchestrator(make_agent_ask(sm, agents, ws, timeout=timeout), store=store)
    return TUIController(registry, store, orch), store
