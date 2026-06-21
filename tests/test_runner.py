"""Testes do Headless Runner (E1-S2): sucesso, falha (returncode!=0) e timeout."""

import asyncio
import sys

from maestro.engine.runner import RunStatus, run_headless

PY = sys.executable


def _run(coro):
    return asyncio.run(coro)


def test_sucesso_returncode_zero():
    r = _run(run_headless([PY, "-c", "print('ola')"], timeout=10))
    assert r.status is RunStatus.OK
    assert r.ok is True
    assert r.returncode == 0
    assert "ola" in r.stdout
    assert r.timed_out is False
    assert r.duration_s >= 0


def test_falha_returncode_nao_zero():
    r = _run(run_headless([PY, "-c", "import sys; sys.exit(3)"], timeout=10))
    assert r.status is RunStatus.FAILED
    assert r.ok is False
    assert r.returncode == 3
    assert r.timed_out is False


def test_captura_stderr():
    r = _run(run_headless([PY, "-c", "import sys; sys.stderr.write('boom')"], timeout=10))
    assert r.status is RunStatus.OK
    assert "boom" in r.stderr


def test_timeout_mata_processo():
    r = _run(run_headless([PY, "-c", "import time; time.sleep(30)"], timeout=0.5))
    assert r.status is RunStatus.TIMEOUT
    assert r.timed_out is True
    assert r.ok is False
    # timeout deve retornar rápido, não esperar os 30s
    assert r.duration_s < 10


def test_cmd_vazio_levanta():
    import pytest

    with pytest.raises(ValueError):
        _run(run_headless([], timeout=1))


def test_cancelamento_mata_subprocesso():
    import os
    import signal

    async def main():
        # processo filho que grava o proprio PID e dorme bastante
        pidfile = f"/tmp/maestro_cancel_{os.getpid()}.pid"
        code = f"import os,time;open({pidfile!r},'w').write(str(os.getpid()));time.sleep(30)"
        task = asyncio.create_task(run_headless([PY, "-c", code], timeout=60))
        await asyncio.sleep(1.0)
        with open(pidfile) as f:
            child = int(f.read())
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(0.3)
        os.remove(pidfile)
        # o processo filho nao deve mais existir
        try:
            os.kill(child, 0)
            return "vivo"
        except (ProcessLookupError, PermissionError):
            return "morto"
        finally:
            try:
                os.kill(child, signal.SIGKILL)
            except ProcessLookupError:
                pass

    assert _run(main()) == "morto"
