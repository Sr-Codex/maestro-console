"""Lifecycle hooks de um floor: Setup / Run / Teardown (V8-S3).

Cada hook é um comando shell que o USUÁRIO define para o floor (ex.: instalar
deps, subir dev server, rodar testes, limpar). Rodam com cwd = worktree do floor
e recebem as env vars MAESTRO_FLOOR_NAME / MAESTRO_BRANCH_NAME / MAESTRO_FLOOR_PATH.

São comandos de infraestrutura do próprio usuário (como um Makefile do projeto),
não código gerado por agente — por isso NÃO passam por bwrap (precisam de rede,
caches globais, dev servers). O agente, esse sim, continua confinado (V8-S2).

Robustez: `run_hooks` nunca levanta. Ordem Setup→Run→Teardown; se Setup falha,
Run é pulado mas Teardown ainda roda (limpeza sempre acontece).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .floors import Floor
from .runner import run_headless

PHASES = ("setup", "run", "teardown")


@dataclass(frozen=True)
class HookResult:
    phase: str
    command: str
    status: str  # "OK" | "FAILED" | "TIMEOUT" | "SKIPPED"
    returncode: int | None


def floor_env(floor: Floor) -> dict[str, str]:
    """Env vars expostas aos hooks (mesmos nomes do Maestri)."""
    return {
        "MAESTRO_FLOOR_NAME": floor.name,
        "MAESTRO_BRANCH_NAME": floor.branch,
        "MAESTRO_FLOOR_PATH": floor.path,
    }


async def run_hooks(
    floor: Floor,
    hooks: dict | None,
    *,
    timeout: float = 600.0,
    phases=PHASES,
    run_fn=run_headless,
    env_base: dict | None = None,
) -> list[HookResult]:
    """Roda os hooks configurados na ordem. Nunca levanta (falha = status no result)."""
    base_env = dict(os.environ if env_base is None else env_base)
    base_env.update(floor_env(floor))
    hooks = hooks or {}
    results: list[HookResult] = []
    setup_failed = False
    for phase in phases:
        cmd = hooks.get(phase)
        if not cmd:
            continue
        if phase == "run" and setup_failed:
            results.append(HookResult(phase, cmd, "SKIPPED", None))
            continue
        res = await run_fn(["bash", "-lc", cmd], timeout=timeout, cwd=floor.path, env=base_env)
        results.append(HookResult(phase, cmd, str(res.status), res.returncode))
        if phase == "setup" and str(res.status) != "OK":
            setup_failed = True
    return results
