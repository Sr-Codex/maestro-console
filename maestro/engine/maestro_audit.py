"""Trilha de auditoria append-only do Maestro mode (ADR-17, fundação).

JSONL em ``<bus>/audit.jsonl``: cada linha = 1 evento (``ts``, ``event`` + campos).
Grava desde o 1º evento (recruit/dismiss/kill/cap-reject) — base para o post-mortem de
runaway e para a detecção de anomalia ATIVA da Etapa 4 (gatilho → kill-switch). Append
de 1 linha por evento; **nunca levanta** (auditoria não pode derrubar o fluxo). Stdlib puro.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

AUDIT_NAME = "audit.jsonl"


def audit_path(bus_dir: str | os.PathLike) -> str:
    return os.path.join(str(bus_dir), AUDIT_NAME)


def append_event(bus_dir: str | os.PathLike, event: str, *, now: float | None = None,
                 **fields) -> None:
    """Acrescenta 1 evento ao log. Engole erros de I/O (auditoria é best-effort)."""
    rec = {"ts": time.time() if now is None else now, "event": str(event)}
    rec.update(fields)
    try:
        Path(bus_dir).mkdir(parents=True, exist_ok=True)
        with open(audit_path(bus_dir), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_events(bus_dir: str | os.PathLike) -> list[dict]:
    """Lê os eventos (HUD/anomalia/testes). Ignora linhas corrompidas; [] se não existe."""
    out: list[dict] = []
    try:
        with open(audit_path(bus_dir), encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return out
