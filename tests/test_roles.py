"""Testes de papéis ricos (V9-S1): cor/badge + role.json + CLAUDE.md/AGENTS.md."""

import json

from maestro.engine.roles import role_badge, role_sidecar, write_role_files
from maestro.engine.state.store import Store
from maestro.engine.teams import Role, Team, Teams, default_color


def test_default_color_por_papel():
    assert default_color("coder") == "#3b82f6"
    assert default_color("Reviewer") == "#f59e0b"  # case-insensitive
    assert default_color("desconhecido") == "#6b7280"  # fallback


def test_badge_explicito_vence_default():
    assert Role("coder", "claude", "x").badge() == "#3b82f6"  # default
    assert Role("coder", "claude", "x", color="#ff0000").badge() == "#ff0000"  # explícito


def test_to_dict_inclui_color_e_roundtrip():
    r = Role("reviewer", "codex", "revise", color="#abcdef")
    d = r.to_dict()
    assert d["color"] == "#abcdef"
    assert Role.from_dict(d) == r


def test_from_dict_retrocompativel_sem_color():
    # teams antigos não têm "color" -> color="" e badge cai no default
    r = Role.from_dict({"name": "coder", "agent": "claude", "instruction": "impl"})
    assert r.color == ""
    assert r.badge() == "#3b82f6"


def test_role_sidecar():
    r = Role("coder", "claude", "implemente", color="#123456")
    s = role_sidecar(r)
    assert s == {"name": "coder", "agent": "claude", "color": "#123456", "prompt": "implemente"}


def test_role_badge_helper():
    assert role_badge(Role("tester", "claude", "teste")) == "#22c55e"


def test_write_role_files(tmp_path):
    r = Role("coder", "claude", "Implemente a tarefa.", color="#3b82f6")
    paths = write_role_files(tmp_path / "ws", r)
    rj = json.loads((tmp_path / "ws" / "role.json").read_text())
    assert rj["name"] == "coder" and rj["prompt"] == "Implemente a tarefa."
    claude = (tmp_path / "ws" / "CLAUDE.md").read_text()
    agents = (tmp_path / "ws" / "AGENTS.md").read_text()
    assert "coder" in claude and "Implemente a tarefa." in claude
    assert claude == agents  # mesmo conteúdo p/ claude e codex
    assert set(paths) == {"role.json", "CLAUDE.md", "AGENTS.md"}


def test_teams_crud_preserva_color(tmp_path):
    store = Store(tmp_path / "m.db")
    teams = Teams(store)
    t = Team("time-cor", [Role("coder", "claude", "impl", color="#0a0b0c")])
    teams.save(t)
    got = teams.get("time-cor")
    assert got.roles[0].color == "#0a0b0c"
    store.close()


def test_builtin_roles_tem_badge_default(tmp_path):
    store = Store(tmp_path / "m.db")
    teams = Teams(store)
    cr = teams.get("coder-reviewer")
    badges = {r.name: r.badge() for r in cr.roles}
    assert badges == {"coder": "#3b82f6", "reviewer": "#f59e0b"}
    store.close()
