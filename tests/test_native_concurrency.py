"""Regressão do A1 (P1): orquestração nativa concorrente não trava (deadlock de
asyncio.Lock entre event loops). Antes do fix, 2 threads no MESMO agent_id
compartilhando um SessionManager travavam para sempre."""

import asyncio
import threading

from maestro.engine.runner import RunResult, RunStatus
from maestro.engine.session import SessionManager
from maestro.engine.state.store import Store
from maestro.native.orchestrate import _run_sync


class _Prof:
    session_assign = "caller"
    rw_paths = ()


async def _slow_run_fn(profile, prompt, *, workspace, **kw):
    await asyncio.sleep(0.15)  # segura o lock tempo suficiente p/ forçar contenção
    return RunResult(
        status=RunStatus.OK, returncode=0, stdout="ok", stderr="", duration_s=0.0, timed_out=False
    )


def test_mesmo_agente_concorrente_nao_trava(tmp_path):
    store = Store(tmp_path / "m.db")
    sm = SessionManager(store)  # MESMO SessionManager (= mesmos asyncio.Lock)
    results = []

    def worker():
        r = _run_sync(
            sm.run_in_session(
                _Prof(), "claude", "p", workspace="/ws", timeout=5, run_fn=_slow_run_fn
            )
        )
        results.append(r)

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=8)

    assert all(not t.is_alive() for t in threads)  # nenhuma travou (sem deadlock)
    assert len(results) == 3 and all(r.status is RunStatus.OK for r in results)
    store.close()


def test_loop_compartilhado_reutilizado():
    # _run_sync usa um único loop persistente (não cria um por chamada)
    from maestro.native.orchestrate import _shared_loop

    assert _shared_loop() is _shared_loop()
