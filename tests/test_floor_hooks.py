"""Testes dos lifecycle hooks de floor (V8-S3)."""

import asyncio

from maestro.engine.floors import Floor
from maestro.engine.hooks import HookResult, floor_env, run_hooks
from maestro.engine.runner import RunResult, RunStatus
from maestro.engine.state.store import Store

_FLOOR = Floor(name="exp", branch="floor/exp", path="/wt/exp", base_branch="HEAD")


def _result(status):
    return RunResult(
        status=status, returncode=0 if status is RunStatus.OK else 1,
        stdout="", stderr="", duration_s=0.0, timed_out=False,
    )


def _recorder(fail_phases=()):
    """run_fn falso que registra (cmd,cwd,env) e falha nas fases pedidas."""
    calls = []

    async def run_fn(cmd, *, timeout, cwd, env, on_output=None):
        calls.append({"cmd": cmd, "cwd": cwd, "env": env})
        phase_cmd = cmd[-1]
        bad = any(p in phase_cmd for p in fail_phases)
        return _result(RunStatus.FAILED if bad else RunStatus.OK)

    return run_fn, calls


def test_floor_env_vars():
    env = floor_env(_FLOOR)
    assert env == {
        "MAESTRO_FLOOR_NAME": "exp",
        "MAESTRO_BRANCH_NAME": "floor/exp",
        "MAESTRO_FLOOR_PATH": "/wt/exp",
    }


def test_ordem_e_env_corretos():
    run_fn, calls = _recorder()
    hooks = {"setup": "echo setup", "run": "echo run", "teardown": "echo tear"}
    res = asyncio.run(run_hooks(_FLOOR, hooks, run_fn=run_fn, env_base={}))
    assert [r.phase for r in res] == ["setup", "run", "teardown"]
    assert all(r.status == "OK" for r in res)
    # cada chamada com cwd = worktree e env vars do floor
    for c in calls:
        assert c["cwd"] == "/wt/exp"
        assert c["env"]["MAESTRO_FLOOR_NAME"] == "exp"
        assert c["env"]["MAESTRO_BRANCH_NAME"] == "floor/exp"


def test_so_fases_configuradas_rodam():
    run_fn, calls = _recorder()
    res = asyncio.run(run_hooks(_FLOOR, {"run": "echo r"}, run_fn=run_fn, env_base={}))
    assert [r.phase for r in res] == ["run"]
    assert len(calls) == 1


def test_setup_falha_pula_run_mas_roda_teardown():
    run_fn, calls = _recorder(fail_phases=("setup",))
    hooks = {"setup": "do-setup", "run": "do-run", "teardown": "do-tear"}
    res = asyncio.run(run_hooks(_FLOOR, hooks, run_fn=run_fn, env_base={}))
    by = {r.phase: r for r in res}
    assert by["setup"].status == "FAILED"
    assert by["run"].status == "SKIPPED"
    assert by["teardown"].status == "OK"
    # run nunca foi executado de fato
    assert not any("do-run" in c["cmd"][-1] for c in calls)
    # teardown executou
    assert any("do-tear" in c["cmd"][-1] for c in calls)


def test_nunca_levanta_em_falha():
    run_fn, _ = _recorder(fail_phases=("boom",))
    res = asyncio.run(run_hooks(_FLOOR, {"run": "boom"}, run_fn=run_fn, env_base={}))
    assert res[0].status == "FAILED"  # reportado, não exceção


def test_hooks_vazio_nao_roda_nada():
    run_fn, calls = _recorder()
    assert asyncio.run(run_hooks(_FLOOR, None, run_fn=run_fn)) == []
    assert calls == []


def test_persistencia_hooks(tmp_path):
    store = Store(tmp_path / "m.db")
    store.set_floor_hooks("exp", setup="a", run="b", teardown=None)
    assert store.get_floor_hooks("exp") == {"setup": "a", "run": "b", "teardown": None}
    assert store.get_floor_hooks("nope") is None
    store.close()


def test_hookresult_dataclass():
    h = HookResult("run", "echo", "OK", 0)
    assert h.phase == "run" and h.status == "OK" and h.returncode == 0
