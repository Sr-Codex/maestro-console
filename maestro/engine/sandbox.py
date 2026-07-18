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

import os
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path


class SandboxUnavailable(RuntimeError):
    """bwrap ausente — recusamos executar sem sandbox (fail-safe)."""


def bwrap_available() -> bool:
    return shutil.which("bwrap") is not None


def invisible_prefixes() -> list[str]:
    """Prefixos do HOST que NÃO existem (ou são outros) dentro do sandbox de um nó —
    fonte única pro `needs_copy` do paste/drop (docs/32 E3): `--tmpfs /tmp` (privado),
    a máscara tmpfs da raiz das contas (ADR-28), `/dev`/`/proc` remontados e o
    runtime-dir do usuário (sockets/portais FUSE, acesso frágil no userns). Mudou um
    mount do `wrap()`? Atualize AQUI junto."""
    from .accounts import accounts_root  # import local: evita ciclo em import-time
    return ["/tmp", str(accounts_root()), "/dev", "/proc", f"/run/user/{os.getuid()}"]


def wrap(
    inner_argv: Sequence[str],
    *,
    workspace: str | Path,
    rw_paths: Sequence[str] = (),
    shared_paths: Sequence[str] = (),
    setenv: Mapping[str, str] | None = None,
    allow_network: bool = True,
    mask_paths: Sequence[str] = (),
) -> list[str]:
    """Retorna o argv do agente envelopado em bwrap. Levanta se bwrap ausente.

    rw_paths: config/sessão do agente (ex.: ~/.claude).
    shared_paths: diretórios de artefatos compartilhados entre agentes (rw).
    setenv: variáveis de ambiente a injetar no sandbox (ex.: MAESTRO_NODE).
    mask_paths: diretórios ESCONDIDOS do agente via tmpfs (docs/31 §5.3: a raiz das
    contas — credencial de outra conta some da vista). A ORDEM importa (bwrap monta
    em sequência): o tmpfs entra ANTES dos binds de rw_paths/shared_paths, pra um
    bind dentro da raiz mascarada (a PRÓPRIA conta do nó) reaparecer por cima.
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
        # --unshare-pid: bwrap vira PID 1 do namespace → SIGKILL nele colapsa TODA a árvore
        # interna (codex/bash). Sem isso, --die-with-parent sozinho VAZA netos (bubblewrap#529).
        "--unshare-pid",
        "--die-with-parent",  # rede de segurança: filhos morrem se o app morre
        # ADR-17: dropar TODAS as capabilities fecha o remount-rw (bubblewrap#287) — o
        # agente não consegue remontar o `--ro-bind /` nem o `bin/` para escrever.
        "--cap-drop",
        "ALL",
    ]
    if not allow_network:
        args += ["--unshare-net"]
    for p in mask_paths:  # ANTES dos binds rw (ordem de mount — ver docstring)
        mp = str(Path(p).expanduser())
        if Path(mp).exists():
            args += ["--tmpfs", mp]  # esconde (ex.: contas alheias); vazio e volátil
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
