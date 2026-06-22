"""maestro console — orquestrador de agentes de IA em terminal.

Pacote raiz. Os subpacotes seguem a arquitetura aprovada (architecture.md):
  - engine: núcleo de orquestração (runner, session, registry, bus, envelope,
            queue, detector, orchestrator, adapters, state, schema)
  - visibility: observabilidade via tmux (log da execução headless)
  - tui: interface de terminal (frontend plugável)
"""

__version__ = "0.8.0"
