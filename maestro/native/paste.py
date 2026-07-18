"""Paste/drag de imagem e arquivo pro nó — lógica PURA (docs/32 / ADR-29).

Gi-free (testável no .venv): nomes de arquivo, regra de injeção segura e decisão de
cópia. O canvas só orquestra (clipboard/texture/feed_child são fronteira gi).

Segurança (emenda E1 do Fable, modelo ADR-17): `shlex.quote` preserva control chars
(\\r/\\n/ESC) LITERAIS dentro das aspas, e o `feed_child` injeta bytes crus no stdin —
um nome de arquivo hostil (criado pelo AGENTE no workspace, arrastado pelo dono) viraria
auto-submit. Regra: caminho não-injetável NUNCA vai pro terminal — o arquivo é copiado
com nome seguro GERADO e a cópia é injetada.
"""

from __future__ import annotations

import re
import shlex
from datetime import datetime

# E4: cap anti imagem-bomba — clipboard é escrevível por qualquer processo X11; um PNG
# craftado de 10000² alocaria ~400MB descomprimidos (adeus CM4). Screenshot real do
# device é 1280×720.
MAX_DIM = 8192

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def injectable(path: str) -> bool:
    """False se o caminho tem QUALQUER control char (byte < 0x20 ou DEL) — E1: nunca
    injetar no PTY; o chamador copia com nome seguro e injeta a cópia."""
    return all(31 < ord(ch) != 127 for ch in path)


def quote_path(path: str) -> str:
    """Quoting de shell (espaço/aspas). PRÉ-CONDIÇÃO: `injectable(path)` (E1)."""
    return shlex.quote(path)


def safe_name(name: str, fallback: str = "arquivo") -> str:
    """Nome seguro pra cópia (padrão `_SAFE_NAME` do artifacts): só [A-Za-z0-9._-],
    sem esconder extensão, nunca vazio nem dotfile."""
    out = _SAFE.sub("_", name).strip("._") or fallback
    return out


def paste_filename(now: datetime, taken: frozenset[str] | set[str] = frozenset()) -> str:
    """Nome do PNG colado: `paste-YYYYmmdd-HHMMSS.png`, com sufixo `-N` se já existe
    (E6: timestamp puro colide no mesmo segundo — autorepeat do atalho)."""
    base = f"paste-{now.strftime('%Y%m%d-%H%M%S')}"
    name = f"{base}.png"
    n = 2
    while name in taken:
        name = f"{base}-{n}.png"
        n += 1
    return name


def copy_name(orig: str, now: datetime, taken: frozenset[str] | set[str] = frozenset()) -> str:
    """Nome da CÓPIA de um drop (E1/E3): `drop-YYYYmmdd-HHMMSS-<nome seguro>`, único
    (E6: não sobrescrever homônimo já copiado)."""
    base = f"drop-{now.strftime('%Y%m%d-%H%M%S')}"
    safe = safe_name(orig)
    name = f"{base}-{safe}"
    n = 2
    while name in taken:
        name = f"{base}-{n}-{safe}"
        n += 1
    return name


def needs_copy(path: str, prefixes: list[str]) -> bool:
    """True se o caminho está sob um prefixo INVISÍVEL dentro do sandbox do nó (E3 —
    `sandbox.invisible_prefixes()`): injetar o original daria ENOENT pro agente."""
    p = path.rstrip("/")
    for pref in prefixes:
        pref = pref.rstrip("/")
        if p == pref or p.startswith(pref + "/"):
            return True
    return False
