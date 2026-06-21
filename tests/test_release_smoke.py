"""Smoke da release (E5-S2): pacote, CLI, adapters e schema prontos."""

import json
from pathlib import Path

import maestro
from maestro.engine.adapters.base import load_profiles


def test_pacote_versao():
    assert maestro.__version__


def test_cli_main(capsys):
    from maestro.__main__ import main

    assert main(["--version"]) == 0
    assert "maestro console" in capsys.readouterr().out


def test_adapters_bundled_carregam():
    profs = load_profiles()
    assert {"claude", "codex"} <= set(profs)


def test_schema_presente_e_valido():
    p = Path(maestro.__file__).parent / "engine" / "schema" / "envelope.schema.json"
    assert p.exists()
    data = json.loads(p.read_text())
    assert data["type"] == "object"
    assert "state" in data["properties"]


def test_doctor_script_existe():
    root = Path(maestro.__file__).parent.parent
    assert (root / "scripts" / "doctor.sh").exists()
    assert (root / "LICENSE").exists()
    assert (root / "README.md").exists()
