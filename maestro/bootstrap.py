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
from .engine.logbook import Logbook
from .engine.orchestrator import Orchestrator, OutputBus, make_agent_ask
from .engine.registry import Registry
from .engine.session import SessionManager
from .engine.state.store import Store
from .engine.usage import UsageLedger
from .engine.workspace import Workspace
from .tui.controller import TUIController


def default_home() -> Path:
    env = os.environ.get("MAESTRO_HOME")
    return Path(env) if env else Path.home() / ".local" / "share" / "maestro-console"


def log_path(home: str | Path | None = None) -> Path:
    base = Path(home) if home is not None else default_home()
    return base / "logs" / "handoffs.log"


def build_controller(
    *, home: str | Path | None = None, timeout: float = 180.0, db_path: str | Path | None = None
):
    """Retorna (TUIController, Store). Lembre de fechar o Store ao sair.

    db_path: DB a usar (multi-workspace, Fase C). Default = ``<base>/maestro.db``.
    """
    base = Path(home) if home is not None else default_home()
    base.mkdir(parents=True, exist_ok=True)
    db = Path(db_path) if db_path else base / "maestro.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    store = Store(db)
    registry = Registry(store)
    sm = SessionManager(store)
    ws = Workspace(base / "workspaces")
    logbook = Logbook(log_path(base))

    profiles = load_profiles()
    agents = {n: p for n, p in profiles.items() if shutil.which(p.cmd[0])}
    for name in agents:
        registry.register(name, name)

    output_bus = OutputBus()  # stream ao vivo dos agentes (web liga o SSE)
    usage_ledger = UsageLedger(store)  # F1: acumula tokens/custo por agente (persiste no Store)
    usage_bus = OutputBus()  # reusa o bus de 1-assinante: (agent_id, total) → canvas atualiza o $

    def _on_usage(agent_id, u):  # u = TOTAL da sessão (do JSONL) → set, não add (evita duplicar)
        usage_bus.emit(agent_id, usage_ledger.set_total(agent_id, u))

    orch = Orchestrator(
        make_agent_ask(
            sm, agents, ws, timeout=timeout, on_output=output_bus.emit, on_usage=_on_usage
        ),
        store=store,
        logbook=logbook,
    )
    controller = TUIController(registry, store, orch)
    controller.output_bus = output_bus
    controller.usage_ledger = usage_ledger  # F1: canvas lê o total por nó
    controller.usage_bus = usage_bus  # F1: canvas assina p/ atualizar o $ ao vivo
    controller.agents = agents  # mesmo dict do make_agent_ask: permite instâncias em runtime
    return controller, store
