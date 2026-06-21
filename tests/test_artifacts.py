"""Testes do canal de artefatos (E2-S4): write/read/list, path por caminho, guarda."""

import pytest

from maestro.engine.artifacts import Artifacts


def test_write_read_list(tmp_path):
    art = Artifacts(tmp_path / "shared")
    art.ensure()
    p = art.write("data.txt", "TOKEN123")
    assert p.is_file()
    assert art.read("data.txt") == "TOKEN123"
    assert art.exists("data.txt")
    assert "data.txt" in art.list()


def test_subdir(tmp_path):
    art = Artifacts(tmp_path / "shared")
    art.write("sub/dir/x.txt", "Y")
    assert art.read("sub/dir/x.txt") == "Y"
    assert "sub/dir/x.txt" in art.list()


def test_path_referencia_por_caminho(tmp_path):
    art = Artifacts(tmp_path / "shared")
    p = art.path("out.bin")
    assert str(p).endswith("shared/out.bin")  # é um caminho, não conteúdo inline


@pytest.mark.parametrize("bad", ["../escape", "/abs", "a/../../b", "x;rm"])
def test_nome_invalido_bloqueia(tmp_path, bad):
    art = Artifacts(tmp_path / "shared")
    with pytest.raises(ValueError):
        art.path(bad)
