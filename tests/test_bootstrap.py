"""Testes do bootstrap (E5-S1) e do entrypoint CLI."""

from maestro.bootstrap import build_controller, default_home
from maestro.tui.controller import TUIController


def test_build_controller(tmp_path):
    controller, store = build_controller(home=tmp_path, timeout=30)
    try:
        assert isinstance(controller, TUIController)
        assert (tmp_path / "maestro.db").exists()
        assert isinstance(controller.list_agents(), list)
        # agents_text e history_text não quebram
        assert isinstance(controller.agents_text(), str)
        assert isinstance(controller.history_text(), str)
    finally:
        store.close()


def test_default_home_respeita_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MAESTRO_HOME", str(tmp_path / "h"))
    assert default_home() == tmp_path / "h"


def test_cli_version(capsys):
    from maestro.__main__ import main

    assert main(["--version"]) == 0
    assert "maestro console" in capsys.readouterr().out


def test_cli_help(capsys):
    from maestro.__main__ import main

    assert main([]) == 0
    assert "maestro tui" in capsys.readouterr().out
