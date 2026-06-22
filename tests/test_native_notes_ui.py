"""Testes dos helpers de notas/badges do canvas (V9-S3) — sem GTK."""

from maestro.engine.notes import Note
from maestro.engine.roles import agent_badges
from maestro.engine.teams import Role, Team
from maestro.native.notes_ui import note_preview, note_title_display


def test_agent_badges_de_team():
    t = Team("x", [Role("coder", "claude", "i"), Role("reviewer", "codex", "i")])
    assert agent_badges(t) == {"claude": "#3b82f6", "codex": "#f59e0b"}


def test_agent_badges_primeiro_papel_vence():
    t = Team("x", [Role("coder", "claude", "i"), Role("planner", "claude", "i")])
    assert agent_badges(t) == {"claude": "#3b82f6"}  # coder (1º) vence


def test_agent_badges_none():
    assert agent_badges(None) == {}


def test_note_preview_curto():
    assert note_preview(Note("i", "t", "linha 1\nlinha 2", 0, 0)) == "linha 1"


def test_note_preview_trunca():
    n = Note("i", "t", "x" * 200, 0, 0)
    p = note_preview(n, maxlen=10)
    assert len(p) == 10 and p.endswith("…")


def test_note_preview_vazio():
    assert note_preview(Note("i", "t", "", 0, 0)) == ""


def test_note_title_display_fallback():
    assert note_title_display(Note("i", "", "b", 0, 0)) == "(sem título)"
    assert note_title_display(Note("i", "Tarefa", "b", 0, 0)) == "Tarefa"
