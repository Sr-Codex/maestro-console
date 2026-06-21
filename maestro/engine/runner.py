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
from collections.abc import Mapping, Sequence
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
) -> RunResult:
    """Executa ``cmd`` headless e retorna um RunResult.

    - ``stdin`` é sempre fechado (DEVNULL) para evitar espera por entrada.
    - Em timeout, o processo é morto e o status é TIMEOUT.
    - ``returncode == 0`` => OK; qualquer outro => FAILED.

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

    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return RunResult(
            status=RunStatus.TIMEOUT,
            returncode=proc.returncode,
            stdout="",
            stderr="",
            duration_s=time.monotonic() - t0,
            timed_out=True,
        )
    except asyncio.CancelledError:
        # Cancelamento seguro: mata o subprocesso (bwrap --die-with-parent mata
        # os filhos) e propaga o cancelamento — sem deixar processo órfão.
        proc.kill()
        with contextlib.suppress(Exception):
            await proc.wait()
        raise

    rc = proc.returncode
    return RunResult(
        status=RunStatus.OK if rc == 0 else RunStatus.FAILED,
        returncode=rc,
        stdout=(out or b"").decode("utf-8", "replace"),
        stderr=(err or b"").decode("utf-8", "replace"),
        duration_s=time.monotonic() - t0,
        timed_out=False,
    )
