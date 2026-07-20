"""Escrita segura contra symlink em diretórios GRAVÁVEIS por agente (S2 do review docs/33).

O workspace de cada agente é RW pro próprio agente. O host (que NÃO roda em sandbox) carimba
brief/role/skill em `CLAUDE.md`/`AGENTS.md`/`role.json` nesse workspace a cada start. Sem cuidado,
um agente hostil troca o arquivo (ou um diretório-pai como `.maestri`) por um SYMLINK apontando
pra um alvo no host (`~/.bashrc`, `~/.ssh/authorized_keys`) e o write do host o SEGUE → escrita
arbitrária no host. Reintroduz a escrita-arbitrária que o ADR-17 eliminou. gi-free.

Defesa TOCTOU-safe (NÃO check-then-use): descemos de `within` (root host-controlado) componente a
componente com `O_NOFOLLOW` via `dir_fd` — um pai symlinkado é recusado NO open, não numa checagem
prévia de `realpath` que uma race poderia furar (revisão adversarial Fable: o `realpath` do pai era
vulnerável a swap concorrente entre a checagem e o open). O componente FINAL abre com `O_NOFOLLOW`;
se já for symlink, remove o LINK (relativo ao `dir_fd`, não segue o alvo) e recria regular.
"""

from __future__ import annotations

import errno
import os


class UnsafeStampPath(Exception):
    """O alvo do stamp escaparia do workspace (symlink de agente hostil) — recusado."""


def _rel_parts(path, within) -> tuple[list[str], str]:
    """Componentes relativos de `path` a partir de `within`: (dirs intermediários, nome).
    Recusa se o caminho escapa do `within` (`..`/absoluto)."""
    rel = os.path.relpath(os.fspath(path), os.fspath(within))
    if os.path.isabs(rel):
        raise UnsafeStampPath(f"stamp com caminho absoluto: {path}")
    parts = [p for p in rel.split(os.sep) if p not in ("", os.curdir)]
    if not parts or os.pardir in parts:
        raise UnsafeStampPath(f"stamp fora do workspace: {path}")
    return parts[:-1], parts[-1]


def _parent_fd(within, dirs: list[str], *, create: bool) -> int:
    """fd do diretório-pai, descendo de `within` com `O_NOFOLLOW` por componente (fecha o
    TOCTOU de pai). `create=True` cria dirs intermediários faltantes (0700). O chamador FECHA."""
    dflags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    dir_fd = os.open(os.fspath(within), dflags)  # within é host-controlado (confiável)
    try:
        for d in dirs:
            try:
                nxt = os.open(d, dflags, dir_fd=dir_fd)
            except OSError as e:
                if e.errno == errno.ENOENT and create:
                    os.mkdir(d, 0o700, dir_fd=dir_fd)
                    nxt = os.open(d, dflags, dir_fd=dir_fd)
                elif e.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise UnsafeStampPath(f"componente-pai é symlink/não-dir: {d}") from e
                else:
                    raise
            os.close(dir_fd)
            dir_fd = nxt
        return dir_fd
    except BaseException:
        os.close(dir_fd)
        raise


def safe_write_text(path, content: str, *, within, encoding: str = "utf-8") -> None:
    """Escreve `content` em `path` sem seguir symlink em NENHUM componente sob `within`
    (o root host-controlado). Cria dirs intermediários com segurança. Se o alvo já é symlink,
    remove o LINK e recria regular (relativo ao dir_fd → não segue o alvo)."""
    dirs, name = _rel_parts(path, within)
    if name == os.pardir:
        raise UnsafeStampPath(f"nome de arquivo inválido: {path}")
    data = content.encode(encoding)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
    dir_fd = _parent_fd(within, dirs, create=True)
    try:
        try:
            fd = os.open(name, flags, 0o644, dir_fd=dir_fd)
        except OSError as e:
            if e.errno != errno.ELOOP:
                raise
            # remove o SYMLINK (não o alvo); recria regular. Re-plant em TOCTOU → ELOOP no
            # retry, propaga sem escrever no host.
            os.unlink(name, dir_fd=dir_fd)
            fd = os.open(name, flags, 0o644, dir_fd=dir_fd)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
    finally:
        os.close(dir_fd)


def safe_read_text(path, *, within, encoding: str = "utf-8") -> str:
    """Lê `path` sem seguir symlink em nenhum componente sob `within`. Symlink/ausência → "".
    Evita puxar conteúdo do host pra dentro do arquivo re-carimbado."""
    try:
        dirs, name = _rel_parts(path, within)
    except UnsafeStampPath:
        return ""
    try:
        dir_fd = _parent_fd(within, dirs, create=False)
    except (OSError, UnsafeStampPath):
        return ""
    try:
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dir_fd)
        except OSError:
            return ""  # symlink (ELOOP), ausente (ENOENT), etc. → vazio
        with os.fdopen(fd, "r", encoding=encoding) as f:
            return f.read()
    finally:
        os.close(dir_fd)
