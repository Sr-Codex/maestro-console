"""CLI `maestro backup <arquivo>` / `maestro restore <arquivo>` (V11-S3)."""

from __future__ import annotations

import argparse
from pathlib import Path

from .engine.backup import backup_to_file, count_records, restore_from_file
from .engine.state.store import Store


def backup_cli(argv: list[str], *, home: str | Path | None = None) -> int:
    p = argparse.ArgumentParser(prog="maestro")
    sub = p.add_subparsers(dest="action", required=True)
    for act, helptxt in (("backup", "exporta o estado p/ JSON"), ("restore", "importa de JSON")):
        s = sub.add_parser(act, help=helptxt)
        s.add_argument("file")
        s.add_argument("--home", default=home, help="MAESTRO_HOME (estado)")
    args = p.parse_args(argv)
    from .bootstrap import default_home

    base = Path(args.home) if args.home else default_home()
    store = Store(base / "maestro.db")
    try:
        if args.action == "backup":
            data = backup_to_file(store, args.file)
            n = count_records(data)
            print(f"backup salvo em {args.file} ({n} registros, {len(data)} tabelas)")
        else:
            if not Path(args.file).exists():
                print(f"erro: arquivo {args.file!r} não existe")
                return 1
            data = restore_from_file(store, args.file)
            print(f"estado restaurado de {args.file} ({count_records(data)} registros)")
        return 0
    finally:
        store.close()
