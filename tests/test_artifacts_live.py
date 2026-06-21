"""Handoff de artefato por caminho entre agentes REAIS (E2-S4) — opt-in.

    MAESTRO_LIVE=1 .venv/bin/pytest tests/test_artifacts_live.py
A (claude) escreve um artefato no diretório compartilhado; B (codex) lê pelo
caminho. Prova FR14 sob sandbox (dir compartilhado montado rw nos dois).
"""

import asyncio
import os
import tempfile

import pytest

from maestro.engine.adapters.base import load_profiles
from maestro.engine.agent_run import run_agent
from maestro.engine.artifacts import Artifacts
from maestro.engine.sandbox import bwrap_available

pytestmark = pytest.mark.skipif(
    os.environ.get("MAESTRO_LIVE") != "1" or not bwrap_available(),
    reason="live: requer MAESTRO_LIVE=1 e bwrap",
)


def test_handoff_artefato_por_caminho(tmp_path):
    profs = load_profiles()
    art = Artifacts(tmp_path / "shared")
    art.ensure()
    target = str(art.path("data.txt"))

    async def main():
        ws_a = tempfile.mkdtemp(prefix="ws_a_")
        ws_b = tempfile.mkdtemp(prefix="ws_b_")
        # A (claude) escreve o artefato no dir compartilhado
        await run_agent(
            profs["claude"],
            f"Crie o arquivo {target} com exatamente: TOKEN-XYZ-42. Responda OK.",
            workspace=ws_a,
            timeout=120,
            shared_paths=[str(art.base)],
        )
        assert art.exists("data.txt")  # escrito no canal compartilhado
        # B (codex) lê pelo caminho
        r = await run_agent(
            profs["codex"],
            f"Leia o arquivo {target} e responda APENAS o conteudo dele.",
            workspace=ws_b,
            timeout=150,
            shared_paths=[str(art.base)],
        )
        assert "TOKEN-XYZ-42" in r.stdout

    asyncio.run(main())
