"""Smoke tests do scaffolding (E1-S1).

Verifica que o pacote importa, expõe versão e que os subpacotes da arquitetura
existem. Não exercita lógica de negócio (ainda não implementada).
"""

import importlib

import maestro


def test_version_exposed():
    assert isinstance(maestro.__version__, str)
    assert maestro.__version__


def test_subpackages_importam():
    for mod in (
        "maestro.engine",
        "maestro.engine.adapters",
        "maestro.engine.state",
        "maestro.visibility",
        "maestro.tui",
    ):
        assert importlib.import_module(mod) is not None


def test_cli_main_roda():
    from maestro.__main__ import main

    assert main(["--version"]) == 0
    assert main([]) == 0
