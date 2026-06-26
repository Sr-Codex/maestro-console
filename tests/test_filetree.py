"""Testes do helper de árvore de arquivos (Fase B) — sem GTK."""

from maestro.native.filetree import Entry, list_children


def test_pastas_primeiro_e_alfabetico(tmp_path):
    (tmp_path / "z_dir").mkdir()
    (tmp_path / "a_dir").mkdir()
    (tmp_path / "b.txt").write_text("x")
    (tmp_path / "a.txt").write_text("x")
    nomes = [e.name for e in list_children(tmp_path)]
    assert nomes == ["a_dir", "z_dir", "a.txt", "b.txt"]  # dirs (alfab.) antes dos arquivos


def test_oculto_filtrado_por_padrao(tmp_path):
    (tmp_path / ".secreto").write_text("x")
    (tmp_path / "visivel.txt").write_text("x")
    assert [e.name for e in list_children(tmp_path)] == ["visivel.txt"]
    nomes_h = [e.name for e in list_children(tmp_path, show_hidden=True)]
    assert ".secreto" in nomes_h and "visivel.txt" in nomes_h


def test_is_dir_e_path_corretos(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "f.py").write_text("x")
    by = {e.name: e for e in list_children(tmp_path)}
    assert by["sub"].is_dir is True and by["f.py"].is_dir is False
    assert by["f.py"].path == str(tmp_path / "f.py")
    assert isinstance(by["sub"], Entry)


def test_caminho_invalido_ou_arquivo_vira_lista_vazia(tmp_path):
    assert list_children(tmp_path / "nao_existe") == []
    f = tmp_path / "arq.txt"
    f.write_text("x")
    assert list_children(f) == []  # não é diretório
