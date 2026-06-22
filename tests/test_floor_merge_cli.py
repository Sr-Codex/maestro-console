"""Testes do merge preview/integração + CLI maestro floor (V8-S4)."""

import subprocess
from pathlib import Path

import pytest

from maestro.cli_floor import floor_cli
from maestro.engine.floor_merge import merge_floor, merge_preview
from maestro.engine.floors import Floors
from maestro.engine.state.store import Store


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _make_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@t")
    _git(path, "config", "user.name", "t")
    (path / "f.txt").write_text("linha1\nlinha2\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "base")
    return path


def _floors(tmp_path):
    repo = _make_repo(tmp_path / "proj")
    store = Store(tmp_path / "m.db")
    return Floors(repo, tmp_path / "floors", store), repo, store


# -- preview / merge (engine) -----------------------------------------
def test_preview_limpo(tmp_path):
    fl, repo, store = _floors(tmp_path)
    f = fl.create("clean", "main")
    (tmp_path / "floors" / "clean" / "novo.txt").write_text("x\n")
    _git(tmp_path / "floors" / "clean", "add", "-A")
    _git(tmp_path / "floors" / "clean", "commit", "-qm", "add novo")
    pv = merge_preview(repo, f)
    assert pv.base == "main"
    assert "novo.txt" in pv.files and pv.insertions >= 1
    assert pv.clean and pv.conflicts == []
    store.close()


def test_preview_detecta_conflito(tmp_path):
    fl, repo, store = _floors(tmp_path)
    f = fl.create("conf", "main")
    wt = tmp_path / "floors" / "conf"
    (wt / "f.txt").write_text("linha1\nFLOOR\n")
    _git(wt, "commit", "-qam", "floor edit")
    # base muda a mesma linha -> conflito
    (repo / "f.txt").write_text("linha1\nBASE\n")
    _git(repo, "commit", "-qam", "base edit")
    pv = merge_preview(repo, f)
    assert not pv.clean and "f.txt" in pv.conflicts
    store.close()


def test_merge_limpo_integra(tmp_path):
    fl, repo, store = _floors(tmp_path)
    f = fl.create("ok", "main")
    wt = tmp_path / "floors" / "ok"
    (wt / "novo.txt").write_text("conteudo\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-qm", "add novo")
    r = merge_floor(repo, f)
    assert r.ok
    assert (repo / "novo.txt").exists()  # integrado na base
    store.close()


def test_merge_recusa_conflito(tmp_path):
    fl, repo, store = _floors(tmp_path)
    f = fl.create("c2", "main")
    wt = tmp_path / "floors" / "c2"
    (wt / "f.txt").write_text("linha1\nFLOOR\n")
    _git(wt, "commit", "-qam", "floor")
    (repo / "f.txt").write_text("linha1\nBASE\n")
    _git(repo, "commit", "-qam", "base")
    r = merge_floor(repo, f)
    assert not r.ok and "f.txt" in r.conflicts
    store.close()


# -- CLI ---------------------------------------------------------------
def test_cli_create_list_rm(tmp_path, capsys):
    repo = _make_repo(tmp_path / "proj")
    home = str(tmp_path / "home")
    assert floor_cli(["create", "exp", "--from", "main", "--project", str(repo)], home=home) == 0
    out = capsys.readouterr().out
    assert "criado" in out
    assert floor_cli(["list", "--project", str(repo)], home=home) == 0
    assert "exp" in capsys.readouterr().out
    assert floor_cli(["rm", "exp", "--project", str(repo)], home=home) == 0
    assert floor_cli(["list", "--project", str(repo)], home=home) == 0
    assert "(nenhum floor)" in capsys.readouterr().out


def test_cli_preview(tmp_path, capsys):
    repo = _make_repo(tmp_path / "proj")
    home = str(tmp_path / "home")
    floor_cli(["create", "p1", "--from", "main", "--project", str(repo)], home=home)
    capsys.readouterr()
    # acha o path do worktree via list
    floor_cli(["list", "--project", str(repo)], home=home)
    path = capsys.readouterr().out.split("\t")[2].strip()
    (Path(path) / "n.txt").write_text("x\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "n")
    assert floor_cli(["preview", "p1", "--project", str(repo)], home=home) == 0
    out = capsys.readouterr().out
    assert "n.txt" in out and "sem conflitos" in out


def test_cli_floor_inexistente(tmp_path, capsys):
    repo = _make_repo(tmp_path / "proj")
    home = str(tmp_path / "home")
    assert floor_cli(["preview", "nao-existe", "--project", str(repo)], home=home) == 1
    assert "não existe" in capsys.readouterr().out


def test_cli_sem_repo_retorna_2(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("MAESTRO_PROJECT", raising=False)
    home = str(tmp_path / "home")
    # --project aponta p/ diretório não-git
    nogit = tmp_path / "nogit"
    nogit.mkdir()
    assert floor_cli(["list", "--project", str(nogit)], home=home) == 2
    assert "erro" in capsys.readouterr().out


def test_cli_run_agente_desconhecido(tmp_path, capsys):
    repo = _make_repo(tmp_path / "proj")
    home = str(tmp_path / "home")
    floor_cli(["create", "r1", "--from", "main", "--project", str(repo)], home=home)
    capsys.readouterr()
    rc = floor_cli(
        ["run", "r1", "agente-zoado", "faça", "algo", "--project", str(repo)], home=home
    )
    assert rc == 1
    assert "não instalado" in capsys.readouterr().out


def test_cli_create_invalido_levanta_systemexit(tmp_path):
    repo = _make_repo(tmp_path / "proj")
    home = str(tmp_path / "home")
    with pytest.raises(SystemExit):  # argparse exige nome
        floor_cli(["create", "--project", str(repo)], home=home)
