"""Captura da sessão interativa de um nó pelo seu workspace (unload — Bloco A′).

Estratégia decidida no `docs/21` (revisão adversarial do Fable): NÃO injetamos um
`--session-id` fixo (quebraria no 2º respawn — o argv é reusado em ~8 gatilhos — e
colidiria com o medidor F1). Em vez disso **capturamos** a sessão viva do nó lendo o
JSONL mais novo no diretório de projeto EXCLUSIVO do nó.

O `claude` grava a sessão em ``~/.claude/projects/<slug-do-cwd>/<session-id>.jsonl``,
onde ``<slug-do-cwd>`` é o caminho absoluto do cwd com todo caractere não-alfanumérico
trocado por ``-`` (regra do Claude Code — verificada ao vivo contra os dirs reais em
2026-07-03). O cwd de cada nó é o seu workspace (``--chdir ws`` no sandbox), então o dir
de projeto é exclusivo do nó → o JSONL mais recente ali é a sua sessão ativa.

Módulo sem GTK (espelha `usage.py`) → unit-testável no ``.venv`` gi-free.
"""

from __future__ import annotations

import re
from pathlib import Path

# Todo caractere fora de [A-Za-z0-9] vira '-' (inclui '/', '.', '_'). Reproduz EXATAMENTE
# o encoding do Claude Code — conferido contra dirs reais em ~/.claude/projects (2026-07-03).
_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")


def project_slug(ws_path: str | Path) -> str:
    """Slug do dir de projeto do Claude para um cwd (workspace do nó).

    Usa o caminho absoluto LITERAL (sem resolver symlinks — o Claude usa o cwd como
    passado ao ``--chdir``)."""
    return _NON_ALNUM.sub("-", str(ws_path))


def project_dir(ws_path: str | Path, *, home: Path | None = None) -> Path:
    """``~/.claude/projects/<slug>`` para o workspace do nó (``home`` injetável p/ teste)."""
    base = (home or Path.home()) / ".claude" / "projects"
    return base / project_slug(ws_path)


def newest_session_id(ws_path: str | Path, *, home: Path | None = None) -> str | None:
    """Session-id da sessão VIVA do nó: o stem do ``*.jsonl`` mais recente (por mtime) no
    dir de projeto exclusivo do nó. ``None`` se o nó ainda não gravou nenhuma sessão
    (dir inexistente ou vazio)."""
    pdir = project_dir(ws_path, home=home)
    if not pdir.is_dir():
        return None
    newest: Path | None = None
    newest_mtime = -1.0
    for f in pdir.glob("*.jsonl"):
        try:
            m = f.stat().st_mtime
        except OSError:
            continue
        if m > newest_mtime:
            newest_mtime, newest = m, f
    return newest.stem if newest is not None else None
