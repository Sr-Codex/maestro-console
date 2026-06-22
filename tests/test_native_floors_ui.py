"""Testes dos helpers de floors do canvas (V8-S5) — sem GTK."""

import subprocess
import threading

from maestro.engine.floor_merge import MergePreview, MergeResult
from maestro.engine.floors import Floors
from maestro.engine.runner import RunResult, RunStatus
from maestro.engine.state.store import Store
from maestro.native.floors_ui import floor_rows, merge_text, preview_text, resolve_floors
from maestro.native.orchestrate import run_floor_agent_in_thread


def _git(repo, *a):
    subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True)


def _make_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@t")
    _git(path, "config", "user.name", "t")
    (path / "f.txt").write_text("a\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "base")
    return path


# -- resolve_floors ----------------------------------------------------
def test_resolve_floors_com_repo(tmp_path):
    repo = _make_repo(tmp_path / "proj")
    store = Store(tmp_path / "m.db")
    fl = resolve_floors(store, tmp_path / "floors", project_override=repo)
    assert isinstance(fl, Floors)
    store.close()


def test_resolve_floors_sem_repo_retorna_none(tmp_path, monkeypatch):
    monkeypatch.delenv("MAESTRO_PROJECT", raising=False)
    store = Store(tmp_path / "m.db")
    nogit = tmp_path / "nogit"
    nogit.mkdir()
    assert resolve_floors(store, tmp_path / "floors", project_override=nogit) is None
    store.close()


# -- formatação --------------------------------------------------------
def test_floor_rows(tmp_path):
    repo = _make_repo(tmp_path / "proj")
    store = Store(tmp_path / "m.db")
    fl = Floors(repo, tmp_path / "floors", store)
    fl.create("x")
    rows = floor_rows(fl)
    assert rows[0]["name"] == "x" and rows[0]["branch"] == "floor/x"
    store.close()


def test_preview_text_limpo():
    pv = MergePreview(base="main", files=["a.txt"], insertions=2, deletions=0, conflicts=[])
    t = preview_text(pv)
    assert "main" in t and "a.txt" in t and "sem conflitos" in t


def test_preview_text_conflito():
    pv = MergePreview(base="main", files=["a.txt"], insertions=1, deletions=1, conflicts=["a.txt"])
    t = preview_text(pv)
    assert "CONFLITOS (1)" in t and "! a.txt" in t


def test_merge_text():
    assert "sucesso" in merge_text(MergeResult(ok=True))
    bad = merge_text(MergeResult(ok=False, conflicts=["a.txt"], reason="conflitos"))
    assert "não realizado" in bad and "! a.txt" in bad


# -- run_floor_agent_in_thread ----------------------------------------
def test_run_floor_agent_in_thread(tmp_path):
    repo = _make_repo(tmp_path / "proj")
    store = Store(tmp_path / "m.db")
    fl = Floors(repo, tmp_path / "floors", store)
    f = fl.create("run1")
    from maestro.engine.session import SessionManager

    sm = SessionManager(store)

    async def fake_run_fn(profile, prompt, *, workspace, **kw):
        # simula o agente criando um arquivo no worktree
        (tmp_path / "floors" / "run1" / "feito.txt").write_text("ok\n")
        return RunResult(
            status=RunStatus.OK,
            returncode=0,
            stdout="",
            stderr="",
            duration_s=0.0,
            timed_out=False,
        )

    class _Prof:
        session_assign = "caller"
        rw_paths = ()

    done = threading.Event()
    box = {}

    def on_done(res, committed):
        box["res"], box["committed"] = res, committed
        done.set()

    run_floor_agent_in_thread(sm, _Prof(), "run1", "faça", f, repo, on_done, run_fn=fake_run_fn)
    assert done.wait(timeout=10.0)
    assert box["res"].status is RunStatus.OK
    assert box["committed"] is True  # houve mudança -> snapshot commitado
    store.close()
