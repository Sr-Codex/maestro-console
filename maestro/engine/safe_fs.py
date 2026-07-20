"""Escrita segura contra symlink em diretórios GRAVÁVEIS por agente (S2 do review docs/33).

O workspace de cada agente é RW pro próprio agente. O host (que NÃO roda em sandbox) carimba
brief/role em `CLAUDE.md`/`AGENTS.md`/`role.json` nesse workspace a cada start. Sem cuidado, um
agente hostil troca o arquivo (ou um diretório-pai como `.maestri`) por um SYMLINK apontando pra
um alvo no host (`~/.bashrc`, `~/.ssh/authorized_keys`) e o write do host o SEGUE → escrita
arbitrária no host. Isso reintroduz a escrita-arbitrária que o ADR-17 eliminou ao trocar o
mailbox-de-arquivo por socket. gi-free.

Duas defesas combinadas:
- **`O_NOFOLLOW`** no componente FINAL: recusa abrir se o próprio arquivo virou symlink.
- **Contenção no `within`**: o realpath do diretório-pai tem de ficar DENTRO do workspace —
  fecha o caso do diretório-pai symlinkado (que o `O_NOFOLLOW` do arquivo não pega).
"""

from __future__ import annotations

import errno
import os
from pathlib import Path


class UnsafeStampPath(Exception):
    """O alvo do stamp escaparia do workspace (symlink de agente hostil) — recusado."""


def _assert_within(target: str, within: str | os.PathLike[str]) -> None:
    root = os.path.realpath(within)
    parent = os.path.realpath(os.path.dirname(target))  # pai (o arquivo pode não existir)
    if parent != root and not parent.startswith(root + os.sep):
        raise UnsafeStampPath(f"stamp fora do workspace (symlink?): {parent} ⊄ {root}")


def safe_write_text(path: str | os.PathLike[str], content: str,
                    *, within: str | os.PathLike[str], encoding: str = "utf-8") -> None:
    """Escreve `content` em `path` sem seguir symlink no componente final (`O_NOFOLLOW`) e
    exigindo que o pai realpath fique dentro de `within` (workspace). Se o alvo já for um
    symlink, remove o LINK (não o alvo) e recria como arquivo regular — neutraliza o ataque
    e mantém o stamp funcionando. `within` é o root host-controlado; nunca omita."""
    p = os.fspath(path)
    _assert_within(p, within)
    data = content.encode(encoding)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
    try:
        fd = os.open(p, flags, 0o644)
    except OSError as e:
        if e.errno != errno.ELOOP:
            raise
        os.unlink(p)  # remove o SYMLINK (não o alvo); recria regular. O_NOFOLLOW no retry
        fd = os.open(p, flags, 0o644)  # pega re-plant em TOCTOU (ELOOP → propaga, sem escrever)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def safe_read_text(path: str | os.PathLike[str], *, encoding: str = "utf-8") -> str:
    """Lê `path`, mas trata um SYMLINK (ou ausência) como "" — p/ não puxar conteúdo do host
    pra dentro do arquivo re-carimbado (o read seguiria o link). O write é o que escapa, mas
    ignorar o read do symlink evita vazar conteúdo do host pro workspace."""
    p = Path(path)
    if p.is_symlink() or not p.exists():
        return ""
    return p.read_text(encoding=encoding)
