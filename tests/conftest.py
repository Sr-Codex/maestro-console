"""Fixtures globais dos testes.

ADR-31: o `sandbox.wrap()` prepara estado POR NÓ (cópia de credencial, ~/.claude.json,
dir de sessão em ~/.claude/projects) — sem isolar, um teste comum gravaria na config REAL
do dono. Por padrão todo teste roda com uma HOME falsa para a config dos CLIs e um
MAESTRO_HOME temporário. Os testes ao vivo (`MAESTRO_LIVE=1`) usam a config real de
propósito (precisam do login) e ficam de fora.
"""

import os

import pytest

from maestro.engine import agent_home, sandbox


@pytest.fixture(autouse=True)
def _isola_config_dos_clis(tmp_path_factory, monkeypatch):
    if os.environ.get("MAESTRO_LIVE") == "1":
        yield
        return
    fake = tmp_path_factory.mktemp("home-falsa")
    monkeypatch.setattr(agent_home, "user_home", lambda: fake)
    monkeypatch.setenv("MAESTRO_HOME", str(tmp_path_factory.mktemp("maestro-home")))
    # composição de argv não depende da versão real; quem EXECUTA bwrap checa a própria
    if sandbox.bwrap_version() < sandbox._OVERLAY_MIN:
        monkeypatch.setattr(sandbox, "bwrap_version", lambda: (99,))
    yield
