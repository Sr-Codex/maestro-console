"""Testes do registro de workspaces (Fase C) — sem GTK."""

import pytest

from maestro.engine.workspace_registry import DEFAULT, WorkspaceRegistry


def test_default_e_current(tmp_path):
    reg = WorkspaceRegistry(tmp_path)
    assert reg.current() == DEFAULT  # default mesmo sem arquivo
    reg.ensure_default("/proj")
    assert reg.get(DEFAULT).project_dir == "/proj"


def test_add_list_e_set_current(tmp_path):
    reg = WorkspaceRegistry(tmp_path)
    reg.ensure_default("/proj")
    reg.add("backend", "/code/backend")
    nomes = [w.name for w in reg.list()]
    assert "backend" in nomes and DEFAULT in nomes
    reg.set_current("backend")
    assert reg.current() == "backend"


def test_db_path_default_reusa_legado_e_outros_isolados(tmp_path):
    reg = WorkspaceRegistry(tmp_path)
    assert reg.db_path(DEFAULT) == tmp_path / "maestro.db"  # legado preservado
    assert reg.db_path("backend") == tmp_path / "ws" / "backend" / "maestro.db"


def test_set_current_desconhecido_recusa(tmp_path):
    reg = WorkspaceRegistry(tmp_path)
    with pytest.raises(ValueError):
        reg.set_current("inexistente")


def test_nome_invalido_recusa(tmp_path):
    reg = WorkspaceRegistry(tmp_path)
    for bad in ("", "a/b", "x" * 41, "nome\tinválido"):
        with pytest.raises(ValueError):
            reg.add(bad, "/x")


def test_persiste_entre_instancias(tmp_path):
    WorkspaceRegistry(tmp_path).add("api", "/srv/api")
    reg2 = WorkspaceRegistry(tmp_path)
    assert reg2.get("api").project_dir == "/srv/api"
