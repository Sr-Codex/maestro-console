"""Sandbox de SO via bwrap (bubblewrap) — confinamento estrito (E2-S2 / ADR-6).

Envelopa o comando do agente para garantir, no nível do SO:
- **workspace**: leitura/escrita;
- **/tmp**: privado por execução (tmpfs), NÃO o /tmp compartilhado do host;
- **resto do sistema**: somente leitura;
- **rede**: mantida (agentes dependem de API);
- diretórios de config/sessão do agente (rw_paths): leitura/escrita (auth/resume);
- **sem flags de bypass**.

Se o bwrap não existir, **falha de forma segura** (não roda sem sandbox).
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path


class SandboxUnavailable(RuntimeError):
    """bwrap ausente — recusamos executar sem sandbox (fail-safe)."""


def bwrap_available() -> bool:
    return shutil.which("bwrap") is not None


def wrap(
    inner_argv: Sequence[str],
    *,
    workspace: str | Path,
    rw_paths: Sequence[str] = (),
    shared_paths: Sequence[str] = (),
    setenv: Mapping[str, str] | None = None,
    allow_network: bool = True,
) -> list[str]:
    """Retorna o argv do agente envelopado em bwrap. Levanta se bwrap ausente.

    rw_paths: config/sessão do agente (ex.: ~/.claude).
    shared_paths: diretórios de artefatos compartilhados entre agentes (rw).
    setenv: variáveis de ambiente a injetar no sandbox (ex.: MAESTRO_NODE).
    """
    if not bwrap_available():
        raise SandboxUnavailable("bwrap não encontrado; recusando rodar sem sandbox")
    ws = str(Path(workspace).resolve())
    args: list[str] = [
        "bwrap",
        "--ro-bind",
        "/",
        "/",  # sistema inteiro: somente leitura
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--tmpfs",
        "/tmp",  # /tmp privado (tmpfs), some ao terminar
        "--bind",
        ws,
        ws,  # workspace: leitura/escrita
        "--chdir",
        ws,
        "--die-with-parent",  # mata filhos junto (timeout/encerramento)
    ]
    if not allow_network:
        args += ["--unshare-net"]
    for p in rw_paths:
        rp = str(Path(p).expanduser())
        if Path(rp).exists():
            args += ["--bind", rp, rp]  # config/sessão do agente: rw
    for p in shared_paths:
        sp = str(Path(p).resolve())
        if Path(sp).exists():
            args += ["--bind", sp, sp]  # artefatos compartilhados: rw
    for k, v in (setenv or {}).items():
        args += ["--setenv", str(k), str(v)]  # ex.: MAESTRO_NODE / MAESTRO_ASK_BUS
    args.append("--")
    args.extend(inner_argv)
    return args
