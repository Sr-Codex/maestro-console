"""Testes dos helpers de agente do canvas nativo (V6-S3) — sem GTK."""

from maestro.engine.adapters.base import load_profiles
from maestro.native import agents
from maestro.native.agents import agent_argv, installed_agents


def test_installed_agents_filtra_por_binario():
    # claude e codex estão instalados neste ambiente
    inst = installed_agents()
    assert "claude" in inst and "codex" in inst


def test_agent_argv_interativo_sob_bwrap(monkeypatch):
    monkeypatch.setattr("maestro.engine.sandbox.bwrap_available", lambda: True)
    claude = load_profiles()["claude"]
    argv = agent_argv(claude, "/ws")
    assert argv[0] == "bwrap"  # confinado (ADR-6)
    i = argv.index("--")
    inner = argv[i + 1 :]
    # a IA roda DENTRO de um shell: ao sair dela, cai num terminal normal
    assert inner[0] == "/bin/bash" and inner[1] == "-c"
    assert "claude" in inner[2] and "exec /bin/bash" in inner[2]  # IA -> shell ao sair
    assert "-p" not in inner[2]  # NÃO é headless (é interativo)


def test_state_colors_tem_todos():
    assert set(agents.STATE_COLORS) == {"idle", "busy", "blocked", "failed", "done"}
