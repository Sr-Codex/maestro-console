"""Testes do Session Manager (E2-S3): continuidade de sessão e mutex."""

import asyncio

from maestro.engine.runner import RunResult, RunStatus
from maestro.engine.session import SessionManager
from maestro.engine.state.store import Store


def _ok() -> RunResult:
    return RunResult(RunStatus.OK, 0, "", "", 0.0, False)


def test_get_or_create_session(tmp_path):
    with Store(tmp_path / "m.db") as s:
        sm = SessionManager(s)
        sid1, new1 = sm.get_or_create_session("claude")
        assert new1 is True
        sid2, new2 = sm.get_or_create_session("claude")
        assert new2 is False
        assert sid2 == sid1  # mesma sessão persiste
        # persiste no store
        assert s.get_session("claude") == sid1


def test_primeiro_set_segundo_resume(tmp_path):
    """1ª execução usa session-id (resume=False); 2ª usa resume=True, mesmo id."""
    calls = []

    async def fake_run(profile, prompt, *, workspace, session_id, resume, timeout):
        calls.append((session_id, resume))
        return _ok()

    async def main():
        with Store(tmp_path / "m.db") as s:
            sm = SessionManager(s)
            await sm.run_in_session(
                None, "claude", "t1", workspace="/w", timeout=1, run_fn=fake_run
            )
            await sm.run_in_session(
                None, "claude", "t2", workspace="/w", timeout=1, run_fn=fake_run
            )

    asyncio.run(main())
    assert calls[0][1] is False  # 1ª: cria (resume=False)
    assert calls[1][1] is True  # 2ª: resume
    assert calls[0][0] == calls[1][0]  # mesmo session_id


def test_mutex_serializa_mesma_sessao(tmp_path):
    """Prompts concorrentes à MESMA sessão não se sobrepõem."""
    active = 0
    max_active = 0

    async def fake_run(profile, prompt, *, workspace, session_id, resume, timeout):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        active -= 1
        return _ok()

    async def main():
        with Store(tmp_path / "m.db") as s:
            sm = SessionManager(s)
            await asyncio.gather(
                *[
                    sm.run_in_session(
                        None, "claude", f"t{i}", workspace="/w", timeout=1, run_fn=fake_run
                    )
                    for i in range(5)
                ]
            )

    asyncio.run(main())
    assert max_active == 1  # nunca dois ativos na mesma sessão


def test_agentes_distintos_concorrem(tmp_path):
    """Agentes diferentes podem rodar em paralelo (mutex é por sessão)."""
    active = 0
    max_active = 0

    async def fake_run(profile, prompt, *, workspace, session_id, resume, timeout):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        active -= 1
        return _ok()

    async def main():
        with Store(tmp_path / "m.db") as s:
            sm = SessionManager(s)
            await asyncio.gather(
                *[
                    sm.run_in_session(
                        None, f"agent{i}", "t", workspace="/w", timeout=1, run_fn=fake_run
                    )
                    for i in range(4)
                ]
            )

    asyncio.run(main())
    assert max_active > 1  # agentes distintos rodam concorrentes
