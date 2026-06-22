"""Continuidade do Codex via session-id capturado (V3-S2)."""

import asyncio

from maestro.engine.adapters.base import AgentProfile
from maestro.engine.runner import RunResult, RunStatus
from maestro.engine.session import SessionManager
from maestro.engine.state.store import Store

CODEXLIKE = AgentProfile(
    name="cx",
    cmd=["codex"],
    session_mode="subcommand",
    session_resume_cmd=["codex", "resume", "{id}"],
    session_assign="captured",
    session_capture=r"session id: (\S+)",
)


def _rr(stdout):
    return RunResult(RunStatus.OK, 0, stdout, "", 0.0, False)


def test_captura_na_primeira_resume_na_segunda(tmp_path):
    calls = []

    async def fake(profile, prompt, *, workspace, session_id, resume, timeout):
        calls.append((session_id, resume))
        if session_id is None:
            return _rr("provider: openai\nsession id: SESS-XYZ\nOK")
        return _rr(f"resumed {session_id}")

    async def main():
        with Store(tmp_path / "m.db") as s:
            sm = SessionManager(s)
            await sm.run_in_session(
                CODEXLIKE, "codex", "t1", workspace="/w", timeout=1, run_fn=fake
            )
            assert s.get_session("codex") == "SESS-XYZ"  # id REAL capturado
            await sm.run_in_session(
                CODEXLIKE, "codex", "t2", workspace="/w", timeout=1, run_fn=fake
            )

    asyncio.run(main())
    assert calls[0] == (None, False)  # 1ª sem id (codex cria)
    assert calls[1] == ("SESS-XYZ", True)  # 2ª retoma o id capturado


def test_sem_mistura_de_contexto_entre_agentes(tmp_path):
    """Cada agente captura e retoma a SUA própria sessão (sem mistura)."""

    async def fake(profile, prompt, *, workspace, session_id, resume, timeout):
        if session_id is None:
            return _rr(f"session id: SESS-{prompt}")  # id distinto por agente
        return _rr(f"resumed {session_id}")

    resumed = {}

    async def fake2(profile, prompt, *, workspace, session_id, resume, timeout):
        if session_id is None:
            return _rr(f"session id: SESS-{prompt}")
        resumed[prompt[0]] = session_id  # registra qual id foi usado no resume
        return _rr("ok")

    async def main():
        with Store(tmp_path / "m.db") as s:
            sm = SessionManager(s)
            # 1ª execução de a e b -> capturam ids distintos
            await sm.run_in_session(CODEXLIKE, "a", "a", workspace="/w", timeout=1, run_fn=fake)
            await sm.run_in_session(CODEXLIKE, "b", "b", workspace="/w", timeout=1, run_fn=fake)
            assert s.get_session("a") == "SESS-a"
            assert s.get_session("b") == "SESS-b"
            # resume -> cada um usa o SEU id
            await sm.run_in_session(CODEXLIKE, "a", "a2", workspace="/w", timeout=1, run_fn=fake2)
            await sm.run_in_session(CODEXLIKE, "b", "b2", workspace="/w", timeout=1, run_fn=fake2)

    asyncio.run(main())
    assert resumed == {"a": "SESS-a", "b": "SESS-b"}  # sem cruzar contexto


def test_profile_codex_carrega_capture():
    from maestro.engine.adapters.base import load_profiles

    cx = load_profiles()["codex"]
    assert cx.session_assign == "captured"
    assert cx.extract_session_id("session id: 019eec9c-abc") == "019eec9c-abc"


def test_codex_resume_nao_inclui_flags_de_permissao():
    """resume do codex (subcommand) nao pode receber --sandbox/-C."""
    from maestro.engine.adapters.base import load_profiles

    cx = load_profiles()["codex"]
    argv = cx.build_command("oi", session_id="SID", resume=True, workspace="/ws")
    assert "resume" in argv and "SID" in argv
    assert "--sandbox" not in argv and "-C" not in argv  # senao o resume quebra
    assert argv[-1] == "oi"
    # mas na 1a execucao (sem resume) as permissoes SAO aplicadas
    first = cx.build_command("oi", workspace="/ws")
    assert "--sandbox" in first
