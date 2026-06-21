"""Testes do Config (E2-S5): teto de agentes configurável por env."""

import pytest

from maestro.config import DEFAULT_AGENT_CEILING, Config


def test_default():
    assert Config().agent_ceiling == DEFAULT_AGENT_CEILING
    assert Config.from_env().agent_ceiling == DEFAULT_AGENT_CEILING


def test_env_override(monkeypatch):
    monkeypatch.setenv("MAESTRO_AGENT_CEILING", "8")
    assert Config.from_env().agent_ceiling == 8


def test_env_invalido(monkeypatch):
    monkeypatch.setenv("MAESTRO_AGENT_CEILING", "abc")
    with pytest.raises(ValueError):
        Config.from_env()


def test_env_menor_que_um(monkeypatch):
    monkeypatch.setenv("MAESTRO_AGENT_CEILING", "0")
    with pytest.raises(ValueError):
        Config.from_env()
