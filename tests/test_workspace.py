"""Testes do Workspace isolado (E2-S2): criação, isolamento e segurança de id."""

import pytest

from maestro.engine.workspace import Workspace


def test_create_e_isolamento(tmp_path):
    ws = Workspace(tmp_path)
    a = ws.create("claude")
    b = ws.create("codex")
    assert a.is_dir() and b.is_dir()
    assert a != b
    # ambos sob o base
    assert tmp_path in a.parents
    assert tmp_path in b.parents


def test_exists_e_cleanup(tmp_path):
    ws = Workspace(tmp_path)
    assert ws.exists("a") is False
    ws.create("a")
    assert ws.exists("a") is True
    ws.cleanup("a")
    assert ws.exists("a") is False


@pytest.mark.parametrize("bad", ["../escape", "a/b", "..", "x y", ""])
def test_agent_id_invalido_bloqueia_traversal(tmp_path, bad):
    ws = Workspace(tmp_path)
    with pytest.raises(ValueError):
        ws.path(bad)
