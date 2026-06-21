"""Testes do sandbox bwrap (E2-S2): composição do argv e fail-safe."""

import pytest

from maestro.engine import sandbox


def test_wrap_compoe_argv(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    argv = sandbox.wrap(["claude", "-p", "oi"], workspace=tmp_path)
    assert argv[0] == "bwrap"
    # sistema read-only, /tmp privado, workspace rw, die-with-parent
    assert "--ro-bind" in argv
    assert "--tmpfs" in argv and "/tmp" in argv
    assert "--bind" in argv and str(tmp_path.resolve()) in argv
    assert "--die-with-parent" in argv
    # comando do agente vem após "--"
    i = argv.index("--")
    assert argv[i + 1 :] == ["claude", "-p", "oi"]


def test_wrap_rw_paths_existentes(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    rw = tmp_path / "cfg"
    rw.mkdir()
    argv = sandbox.wrap(["x"], workspace=tmp_path, rw_paths=[str(rw), "/nao/existe"])
    # dir existente é bindado; inexistente é ignorado
    assert str(rw) in argv
    assert "/nao/existe" not in argv


def test_wrap_shared_paths_bind_rw(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    shared = tmp_path / "shared"
    shared.mkdir()
    argv = sandbox.wrap(["x"], workspace=tmp_path, shared_paths=[str(shared)])
    assert str(shared.resolve()) in argv  # diretório compartilhado montado


def test_wrap_unshare_net_opcional(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    com_rede = sandbox.wrap(["x"], workspace=tmp_path, allow_network=True)
    sem_rede = sandbox.wrap(["x"], workspace=tmp_path, allow_network=False)
    assert "--unshare-net" not in com_rede
    assert "--unshare-net" in sem_rede


def test_falha_segura_sem_bwrap(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: False)
    with pytest.raises(sandbox.SandboxUnavailable):
        sandbox.wrap(["x"], workspace=tmp_path)
