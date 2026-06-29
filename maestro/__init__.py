"""maestro console — orquestrador de agentes de IA em terminal.

Pacote raiz. Os subpacotes seguem a arquitetura aprovada (architecture.md):
  - engine: núcleo de orquestração (runner, session, registry, bus, envelope,
            queue, detector, orchestrator, adapters, state, schema)
  - visibility: observabilidade via tmux (log da execução headless)
  - tui: interface de terminal (frontend plugável)
"""

# Versão ÚNICA: vem do pacote instalado ou, rodando do código-fonte, do pyproject.toml.
# Evita o drift (antes era hardcoded e ficou preso em 0.18.0 enquanto o pyproject ia a 0.37+).
def _resolve_version() -> str:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _v

    try:
        return _v("maestro-console")
    except PackageNotFoundError:  # rodando via PYTHONPATH (sem pip install) → lê o pyproject
        import pathlib
        import re

        pp = pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml"
        try:
            m = re.search(r'^version\s*=\s*"([^"]+)"', pp.read_text(encoding="utf-8"), re.M)
            return m.group(1) if m else "0.0.0"
        except OSError:
            return "0.0.0"


__version__ = _resolve_version()
