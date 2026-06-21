"""Logbook — log textual de execução/handoffs para observabilidade (E4-S1/FR12).

Linhas legíveis por humano, append-only, que o pane tmux segue com `tail -f`.
Complementa o envelope_log estruturado (SQLite) com uma visão de fluxo.
"""

from __future__ import annotations

import time
from pathlib import Path


class Logbook:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, line: str) -> None:
        ts = time.strftime("%H:%M:%S", time.localtime())
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {line}\n")

    def lines(self) -> list[str]:
        if not self.path.exists():
            return []
        return self.path.read_text(encoding="utf-8").splitlines()
