"""Backup & Restore do estado (V11-S3).

Exporta/importa TODO o estado (todas as tabelas do Store) em JSON — inspecionável
e portável entre máquinas. restore = replace (limpa e reinsere). gi-free.
"""

from __future__ import annotations

import json
from pathlib import Path


def backup_to_file(store, path: str | Path) -> dict:
    """Escreve o snapshot JSON em `path`. Retorna os dados exportados."""
    data = store.export_all()
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return data


def restore_from_file(store, path: str | Path) -> dict:
    """Lê o snapshot JSON e restaura o estado (replace). Retorna os dados lidos."""
    data = json.loads(Path(path).read_text())
    store.import_all(data, replace=True)
    return data


def count_records(data: dict) -> int:
    return sum(len(rows) for rows in data.values())
