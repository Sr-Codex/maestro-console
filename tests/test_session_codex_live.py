"""Continuidade REAL do Codex via id capturado (V3-S2) — opt-in.

MAESTRO_LIVE=1 .venv/bin/pytest tests/test_session_codex_live.py
"""

import asyncio
import os
import tempfile

import pytest

from maestro.engine.adapters.base import load_profiles
from maestro.engine.sandbox import bwrap_available
from maestro.engine.session import SessionManager
from maestro.engine.state.store import Store

pytestmark = pytest.mark.skipif(
    os.environ.get("MAESTRO_LIVE") != "1" or not bwrap_available(),
    reason="live: requer MAESTRO_LIVE=1 e bwrap",
)


def test_codex_lembra_via_id_capturado(tmp_path):
    prof = load_profiles()["codex"]

    async def main():
        with Store(tmp_path / "m.db") as s:
            sm = SessionManager(s)
            ws = tempfile.mkdtemp(prefix="ws_")
            await sm.run_in_session(
                prof,
                "codex",
                "Memorize o numero secreto 5151. Responda apenas OK.",
                workspace=ws,
                timeout=180,
            )
            captured = s.get_session("codex")
            assert captured, "session-id do codex nao foi capturado"
            r = await sm.run_in_session(
                prof,
                "codex",
                "Qual o numero secreto que memorizei? Responda so o numero.",
                workspace=ws,
                timeout=180,
            )
            return captured, r.stdout

    captured, out = asyncio.run(main())
    assert "5151" in out, f"codex nao lembrou (sessao {captured}): {out[-200:]}"
