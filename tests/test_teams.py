"""Testes de Teams & Roles (V2-S1)."""

from maestro.engine.state.store import Store
from maestro.engine.teams import BUILTIN_TEAMS, Role, Team, Teams


def test_route_compacta():
    t = Team("x", [Role("coder", "claude", "i"), Role("reviewer", "codex", "i")])
    assert t.route == "coder(claude) → reviewer(codex)"


def test_builtins_existem():
    assert "coder-reviewer" in BUILTIN_TEAMS
    assert "planner-coder-reviewer" in BUILTIN_TEAMS
    assert [r.name for r in BUILTIN_TEAMS["planner-coder-reviewer"].roles] == [
        "planner",
        "coder",
        "reviewer",
    ]


def test_get_builtin_sem_salvar(tmp_path):
    with Store(tmp_path / "m.db") as s:
        teams = Teams(s)
        t = teams.get("coder-reviewer")
        assert t is not None and len(t.roles) == 2


def test_salvar_listar_obter_deletar(tmp_path):
    with Store(tmp_path / "m.db") as s:
        teams = Teams(s)
        custom = Team("meu-time", [Role("dev", "claude", "faça X")])
        teams.save(custom)
        assert "meu-time" in teams.list()
        # built-ins também aparecem
        assert "coder-reviewer" in teams.list()
        got = teams.get("meu-time")
        assert got.roles[0].agent == "claude" and got.roles[0].instruction == "faça X"
        teams.delete("meu-time")
        assert "meu-time" not in teams.list()


def test_persiste_entre_instancias(tmp_path):
    db = tmp_path / "m.db"
    with Store(db) as s:
        Teams(s).save(Team("t", [Role("a", "codex", "z")]))
    with Store(db) as s2:
        assert Teams(s2).get("t").roles[0].agent == "codex"


def test_salvar_sobrescreve_builtin(tmp_path):
    with Store(tmp_path / "m.db") as s:
        teams = Teams(s)
        teams.save(Team("coder-reviewer", [Role("solo", "claude", "i")]))
        # versão salva tem prioridade sobre o built-in
        assert [r.name for r in teams.get("coder-reviewer").roles] == ["solo"]
