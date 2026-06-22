"""Testes do core de floors + resolução do repo (V8-S1) — repo git real temporário."""

import subprocess

import pytest

from maestro.engine.floors import Floor, FloorError, Floors
from maestro.engine.project import ProjectError, resolve_project
from maestro.engine.state.store import Store


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _make_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@t")
    _git(path, "config", "user.name", "t")
    (path / "README.md").write_text("base\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "init")
    return path


# -- project resolution ------------------------------------------------
def test_resolve_por_cwd(tmp_path):
    repo = _make_repo(tmp_path / "proj")
    assert resolve_project(cwd=repo).resolve() == repo.resolve()


def test_resolve_override_ganha_de_cwd(tmp_path, monkeypatch):
    repo_a = _make_repo(tmp_path / "a")
    repo_b = _make_repo(tmp_path / "b")
    # cwd aponta para A, override para B -> B ganha
    assert resolve_project(cwd=repo_a, override=repo_b).resolve() == repo_b.resolve()


def test_resolve_env_override(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path / "proj")
    monkeypatch.setenv("MAESTRO_PROJECT", str(repo))
    # cwd fora de repo, mas env aponta para o repo
    assert resolve_project(cwd=tmp_path).resolve() == repo.resolve()


def test_resolve_sem_repo_levanta(tmp_path, monkeypatch):
    monkeypatch.delenv("MAESTRO_PROJECT", raising=False)
    with pytest.raises(ProjectError):
        resolve_project(cwd=tmp_path)


def test_resolve_override_nao_git_levanta(tmp_path):
    with pytest.raises(ProjectError):
        resolve_project(override=tmp_path)


# -- floors core -------------------------------------------------------
def _floors(tmp_path):
    repo = _make_repo(tmp_path / "proj")
    store = Store(tmp_path / "m.db")
    return Floors(repo, tmp_path / "floors", store), repo, store


def test_create_lista_e_worktree_existe(tmp_path):
    fl, repo, store = _floors(tmp_path)
    f = fl.create("exp1")
    assert isinstance(f, Floor) and f.branch == "floor/exp1"
    assert (tmp_path / "floors" / "exp1").is_dir()
    assert (tmp_path / "floors" / "exp1" / "README.md").exists()  # worktree tem o conteúdo
    names = [x.name for x in fl.list()]
    assert names == ["exp1"]
    store.close()


def test_isolamento_entre_floors(tmp_path):
    fl, repo, store = _floors(tmp_path)
    fl.create("a")
    fl.create("b")
    # escreve em A; B não enxerga
    (tmp_path / "floors" / "a" / "novo.txt").write_text("x")
    assert not (tmp_path / "floors" / "b" / "novo.txt").exists()
    assert {x.name for x in fl.list()} == {"a", "b"}
    store.close()


def test_nome_invalido(tmp_path):
    fl, repo, store = _floors(tmp_path)
    with pytest.raises(FloorError):
        fl.create("inv/alido")
    store.close()


def test_create_duplicado_levanta(tmp_path):
    fl, repo, store = _floors(tmp_path)
    fl.create("dup")
    with pytest.raises(FloorError):
        fl.create("dup")
    store.close()


def test_remove_apaga_worktree_e_registro(tmp_path):
    fl, repo, store = _floors(tmp_path)
    fl.create("tmp1")
    fl.remove("tmp1")
    assert fl.get("tmp1") is None
    assert not (tmp_path / "floors" / "tmp1").exists()
    # branch removida
    out = subprocess.run(
        ["git", "-C", str(repo), "branch", "--list", "floor/tmp1"],
        capture_output=True,
        text=True,
    )
    assert out.stdout.strip() == ""
    store.close()


def test_remove_inexistente_levanta(tmp_path):
    fl, repo, store = _floors(tmp_path)
    with pytest.raises(FloorError):
        fl.remove("nope")
    store.close()


def test_nao_git_levanta(tmp_path):
    store = Store(tmp_path / "m.db")
    (tmp_path / "naogit").mkdir()
    with pytest.raises(FloorError):
        Floors(tmp_path / "naogit", tmp_path / "floors", store)
    store.close()


def test_persiste_entre_aberturas(tmp_path):
    fl, repo, store = _floors(tmp_path)
    fl.create("keep")
    store.close()
    store2 = Store(tmp_path / "m.db")
    fl2 = Floors(repo, tmp_path / "floors", store2)
    assert [x.name for x in fl2.list()] == ["keep"]
    store2.close()
