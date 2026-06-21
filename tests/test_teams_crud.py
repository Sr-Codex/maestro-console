"""Testes do CRUD de teams (V3-S1): validação, duplicar, excluir, controller."""

import pytest

from maestro.engine.state.store import Store
from maestro.engine.teams import Role, Team, Teams, TeamValidationError, validate_team
from maestro.tui.controller import TUIController


class _FakeOrch:
    pass


def test_validate_team():
    validate_team(Team("t", [Role("coder", "claude", "faça")]))  # ok
    with pytest.raises(TeamValidationError):
        validate_team(Team("", [Role("c", "claude", "i")]))  # sem nome
    with pytest.raises(TeamValidationError):
        validate_team(Team("t", []))  # sem papéis
    with pytest.raises(TeamValidationError):
        validate_team(Team("t", [Role("c", "", "i")]))  # sem agente
    with pytest.raises(TeamValidationError):
        validate_team(Team("t", [Role("c", "claude", "")]))  # sem instrução


def test_save_valida(tmp_path):
    with Store(tmp_path / "m.db") as s:
        teams = Teams(s)
        with pytest.raises(TeamValidationError):
            teams.save(Team("t", []))


def test_duplicate(tmp_path):
    with Store(tmp_path / "m.db") as s:
        teams = Teams(s)
        dup = teams.duplicate("coder-reviewer", "meu-fluxo")  # duplica built-in
        assert dup.name == "meu-fluxo"
        assert teams.exists("meu-fluxo")
        assert [r.name for r in teams.get("meu-fluxo").roles] == ["coder", "reviewer"]
        with pytest.raises(TeamValidationError):
            teams.duplicate("meu-fluxo", "meu-fluxo")  # ja existe
        with pytest.raises(TeamValidationError):
            teams.duplicate("inexistente", "x")


def test_controller_crud(tmp_path):
    from maestro.engine.registry import Registry

    with Store(tmp_path / "m.db") as s:
        ctrl = TUIController(Registry(s), s, _FakeOrch())
        # criar
        t = ctrl.save_team(
            "api-flow", [("coder", "claude", "implemente"), ("reviewer", "codex", "revise")]
        )
        assert t.route == "coder(claude) → reviewer(codex)"
        assert ctrl.team_exists("api-flow")
        # ver detalhe
        assert "api-flow" in ctrl.team_detail_text("api-flow")
        # editar (sobrescreve)
        ctrl.save_team("api-flow", [("solo", "claude", "faça tudo")])
        assert [r.name for r in ctrl.get_team("api-flow").roles] == ["solo"]
        # duplicar
        ctrl.duplicate_team("api-flow", "api-flow-2")
        assert ctrl.team_exists("api-flow-2")
        # excluir
        ctrl.delete_team("api-flow")
        assert not ctrl.team_exists("api-flow")
        # criar inválido
        with pytest.raises(TeamValidationError):
            ctrl.save_team("ruim", [("c", "", "i")])
