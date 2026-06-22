"""Testes do streaming runner (V5-S1): on_output ao vivo + invariantes."""

import asyncio
import sys

from maestro.engine.runner import RunStatus, run_headless

PY = sys.executable


def _run(coro):
    return asyncio.run(coro)


def test_on_output_recebe_pedacos_ao_vivo():
    chunks = []
    # imprime 3 linhas com flush e pausas -> deve chegar em mais de 1 pedaço
    code = "import time,sys\n" + "".join(
        f"print('linha{i}', flush=True); time.sleep(0.1)\n" for i in range(3)
    )
    r = _run(run_headless([PY, "-u", "-c", code], timeout=10, on_output=chunks.append))
    assert r.status is RunStatus.OK
    saida = "".join(chunks)
    assert "linha0" in saida and "linha2" in saida
    assert "".join(chunks) == r.stdout  # stdout completo == soma dos pedaços
    assert len(chunks) >= 2  # chegou ao vivo, em pedaços


def test_streaming_falha_returncode():
    chunks = []
    r = _run(
        run_headless(
            [PY, "-c", "import sys;print('x');sys.exit(2)"], timeout=10, on_output=chunks.append
        )
    )
    assert r.status is RunStatus.FAILED and r.returncode == 2
    assert "x" in r.stdout


def test_streaming_timeout_mata():
    r = _run(
        run_headless(
            [PY, "-c", "import time;print('a',flush=True);time.sleep(30)"],
            timeout=0.5,
            on_output=lambda c: None,
        )
    )
    assert r.status is RunStatus.TIMEOUT and r.timed_out and r.duration_s < 10


def test_streaming_cancelavel():
    async def main():
        task = asyncio.create_task(
            run_headless(
                [PY, "-c", "import time;time.sleep(30)"], timeout=60, on_output=lambda c: None
            )
        )
        await asyncio.sleep(0.3)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return "cancelled"
        return "no"

    assert _run(main()) == "cancelled"
