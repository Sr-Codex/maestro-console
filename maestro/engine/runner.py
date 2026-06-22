"""Headless Runner — executa um agente CLI em modo headless (E1-S2).

Caminho de DADOS da orquestração (ADR-1): roda `claude -p` / `codex exec` (ou
qualquer comando) via asyncio, captura stdout/stderr, **verifica o returncode**
e aplica **timeout** (mata o processo se estourar). Sem TUI, sem PTY.

Não conhece adapters nem envelope — é a camada de execução de baixo nível.
A construção do comando (perfil do agente) vem do adapter (E2); a concorrência
entre agentes (semáforo/teto) vem da fila/orquestrador (E3).
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class RunStatus(StrEnum):
    """Resultado da execução headless (mapeado depois para estados de envelope)."""

    OK = "OK"  # processo terminou com returncode 0
    FAILED = "FAILED"  # processo terminou com returncode != 0
    TIMEOUT = "TIMEOUT"  # excedeu o timeout e foi morto


@dataclass(frozen=True)
class RunResult:
    status: RunStatus
    returncode: int | None
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool

    @property
    def ok(self) -> bool:
        return self.status is RunStatus.OK


async def run_headless(
    cmd: Sequence[str],
    *,
    timeout: float,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    on_output: Callable[[str], None] | None = None,
) -> RunResult:
    """Executa ``cmd`` headless e retorna um RunResult.

    - ``stdin`` é sempre fechado (DEVNULL) para evitar espera por entrada.
    - Em timeout, o processo é morto e o status é TIMEOUT.
    - ``returncode == 0`` => OK; qualquer outro => FAILED.
    - ``on_output``: se dado, recebe o stdout em pedaços AO VIVO (streaming, para
      terminais read-only no canvas). O RunResult ainda traz o stdout completo.

    Nunca levanta por falha do processo (a falha vira RunResult.FAILED);
    levanta apenas se o binário não puder ser iniciado (FileNotFoundError etc.).
    """
    if not cmd:
        raise ValueError("cmd vazio")

    t0 = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=dict(env) if env is not None else None,
    )

    def _result(out: str, err: str, status: RunStatus, timed_out: bool) -> RunResult:
        return RunResult(
            status=status,
            returncode=proc.returncode,
            stdout=out,
            stderr=err,
            duration_s=time.monotonic() - t0,
            timed_out=timed_out,
        )

    async def _kill():
        proc.kill()
        with contextlib.suppress(Exception):
            await proc.wait()

    if on_output is None:
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            await _kill()
            return _result("", "", RunStatus.TIMEOUT, True)
        except asyncio.CancelledError:
            await _kill()
            raise
        rc = proc.returncode
        return _result(
            (out or b"").decode("utf-8", "replace"),
            (err or b"").decode("utf-8", "replace"),
            RunStatus.OK if rc == 0 else RunStatus.FAILED,
            False,
        )

    # streaming: lê o stdout incrementalmente, emitindo cada pedaço ao vivo
    chunks: list[str] = []

    async def _pump() -> bytes:
        while True:
            data = await proc.stdout.read(4096)
            if not data:
                break
            text = data.decode("utf-8", "replace")
            chunks.append(text)
            with contextlib.suppress(Exception):
                on_output(text)
        return await proc.stderr.read()

    try:
        err_b = await asyncio.wait_for(_pump(), timeout=timeout)
        await proc.wait()
    except TimeoutError:
        await _kill()
        return _result("".join(chunks), "", RunStatus.TIMEOUT, True)
    except asyncio.CancelledError:
        await _kill()
        raise
    rc = proc.returncode
    return _result(
        "".join(chunks),
        err_b.decode("utf-8", "replace"),
        RunStatus.OK if rc == 0 else RunStatus.FAILED,
        False,
    )
