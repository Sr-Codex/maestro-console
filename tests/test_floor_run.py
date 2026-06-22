"""Testes de rodar agente num floor + snapshot (V8-S2)."""

import subprocess

from maestro.engine.floor_run import commit_floor, run_agent_in_floor
from maestro.engine.floors import Floors
from maestro.engine.runner import RunResult, RunStatus
from maestro.engine.session import SessionManager
from maestro.engine.state.store import Store


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _make_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "t@t")
    _git(path, "config", "user.name", "t")
    (path / "README.md").write_text("base\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "init")
    return path


class _FakeProfile:
    session_assign = "caller"
    rw_paths = ()


def _fake_run_fn(calls):
    async def run_fn(profile, prompt, **kw):
        calls.append(kw)
        return RunResult(
            status=RunStatus.OK,
            returncode=0,
            stdout="ok",
            stderr="",
            duration_s=0.0,
            timed_out=False,
        )

    return run_fn


async def _run(fl, repo, store, name, calls):
    f = fl.create(name)
    sm = SessionManager(store)
    res = await run_agent_in_floor(
        sm, _FakeProfile(), name, "faça X", f, repo, timeout=5, run_fn=_fake_run_fn(calls)
    )
    return f, res


def test_roda_com_cwd_no_floor_e_git_liberado(tmp_path):
    import asyncio

    repo = _make_repo(tmp_path / "proj")
    store = Store(tmp_path / "m.db")
    fl = Floors(repo, tmp_path / "floors", store)
    calls = []
    f, res = asyncio.run(_run(fl, repo, store, "exp", calls))
    assert res.status is RunStatus.OK
    kw = calls[0]
    assert kw["workspace"] == f.path  # cwd = worktree do floor
    # .git do repo liberado rw p/ git funcionar no worktree
    assert any(str(repo) in p and p.endswith(".git") for p in kw["shared_paths"])
    store.close()


def test_isolamento_dois_floors_cwd_distinto(tmp_path):
    import asyncio

    repo = _make_repo(tmp_path / "proj")
    store = Store(tmp_path / "m.db")
    fl = Floors(repo, tmp_path / "floors", store)
    ca, cb = [], []
    fa, _ = asyncio.run(_run(fl, repo, store, "a", ca))
    fb, _ = asyncio.run(_run(fl, repo, store, "b", cb))
    assert ca[0]["workspace"] != cb[0]["workspace"]
    assert ca[0]["workspace"] == fa.path and cb[0]["workspace"] == fb.path
    store.close()


def test_commit_floor_snapshot(tmp_path):
    repo = _make_repo(tmp_path / "proj")
    store = Store(tmp_path / "m.db")
    fl = Floors(repo, tmp_path / "floors", store)
    f = fl.create("snap")
    # sem mudanças -> não commita
    assert commit_floor(f, "vazio") is False
    # com mudança -> commita na branch do floor
    (tmp_path / "floors" / "snap" / "novo.txt").write_text("conteudo\n")
    assert commit_floor(f, "add novo") is True
    # a branch do floor tem o commit novo; a base não
    log = subprocess.run(
        ["git", "-C", str(repo), "log", "--oneline", f.branch],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "add novo" in log.stdout
    store.close()


def test_session_aceita_shared_paths_sem_quebrar_default(tmp_path):
    """run_in_session sem shared_paths não passa o kwarg (mantém fakes simples)."""
    import asyncio

    store = Store(tmp_path / "m.db")
    sm = SessionManager(store)
    calls = []
    asyncio.run(
        sm.run_in_session(
            _FakeProfile(), "ag", "p", workspace="/ws", timeout=5, run_fn=_fake_run_fn(calls)
        )
    )
    assert "shared_paths" not in calls[0]  # ausente quando não pedido
    store.close()
