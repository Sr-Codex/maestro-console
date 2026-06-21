"""Ponto de entrada da CLI `maestro` (placeholder do scaffolding).

A orquestração real é implementada nos épicos seguintes; por ora apenas
expõe versão/ajuda para validar a instalação.
"""

from __future__ import annotations

import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in {"-v", "--version"}:
        print(f"maestro console {__version__}")
        return 0
    print(
        "maestro console "
        f"{__version__} — fundação (Épico 1). Orquestração ainda não implementada.\n"
        "Uso: maestro --version"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
