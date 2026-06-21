"""Continuidade de sessão REAL via SessionManager (E2-S3) — opt-in.

    MAESTRO_LIVE=1 .venv/bin/pytest tests/test_session_live.py
Requer bwrap + claude. claude aceita --session-id do chamador (validado),
então a continuidade é determinística para ele.
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


def test_claude_lembra_entre_turnos(tmp_path):
    prof = load_profiles()["claude"]

    async def main():
        with Store(tmp_path / "m.db") as s:
            sm = SessionManager(s)
            ws = tempfile.mkdtemp(prefix="maestro_ws_")
            await sm.run_in_session(
                prof,
                "claude",
                "Memorize o numero secreto 7391. Responda apenas OK.",
                workspace=ws,
                timeout=120,
            )
            r = await sm.run_in_session(
                prof,
                "claude",
                "Qual o numero secreto que memorizei? Responda APENAS o numero.",
                workspace=ws,
                timeout=120,
            )
            assert "7391" in r.stdout

    asyncio.run(main())
