"""Testes dos helpers de agente do canvas nativo (V6-S3) — sem GTK."""

from maestro.engine.adapters.base import load_profiles
from maestro.native import agents
from maestro.native.agents import agent_argv, installed_agents


def test_installed_agents_filtra_por_binario(monkeypatch):
    # hermético (passa no CI sem os binários reais): mocka o PATH p/ só "claude" instalado
    # e verifica que o FILTRO por binário inclui o presente e exclui o ausente.
    claude_bin = load_profiles()["claude"].cmd[0]
    monkeypatch.setattr(
        agents.shutil, "which", lambda b: "/usr/bin/fake" if b == claude_bin else None
    )
    inst = installed_agents()
    assert "claude" in inst  # binário "presente" -> incluído
    assert "codex" not in inst  # binário ausente -> filtrado


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
    assert set(agents.STATE_COLORS) == {"idle", "busy", "waiting", "blocked", "failed", "done"}


def test_blocked_distinto_de_waiting():
    # PR "cor própria do blocked": bloqueado por dependência tem cor own (Mocha red),
    # distinta do âmbar de waiting ("é sua vez") — não podem colidir de novo.
    assert agents.STATE_COLORS["blocked"] == "#f38ba8"
    assert agents.STATE_COLORS["waiting"] == "#f59e0b"
    assert agents.STATE_COLORS["blocked"] != agents.STATE_COLORS["waiting"]
