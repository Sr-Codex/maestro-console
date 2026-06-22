"""Segurança do servidor web (V4-S1).

- token aleatório obrigatório fora de localhost (header, nunca query string);
- CORS fechado + validação de Origin;
- arquivo de token com permissões 0600.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

TOKEN_HEADER = "X-Maestro-Token"
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def is_local(host: str) -> bool:
    return host in LOCAL_HOSTS


def ensure_token(path: str | Path) -> str:
    """Lê o token (0600) ou gera um aleatório e persiste com 0600."""
    p = Path(path)
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    p.parent.mkdir(parents=True, exist_ok=True)
    tok = secrets.token_urlsafe(32)
    p.write_text(tok, encoding="utf-8")
    os.chmod(p, 0o600)
    return tok


def origin_allowed(origin: str | None, allowed: set[str]) -> bool:
    """Origin ausente (mesma origem / não-browser) é permitido; senão deve constar."""
    return origin is None or origin in allowed


def token_ok(provided: str | None, expected: str) -> bool:
    return bool(expected) and secrets.compare_digest(provided or "", expected)


def allowed_origins_for(host: str, port: int) -> set[str]:
    hosts = {host, "localhost", "127.0.0.1"}
    return {f"http://{h}:{port}" for h in hosts}
