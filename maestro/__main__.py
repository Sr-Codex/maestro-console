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
    if argv and argv[0] == "canvas":
        try:
            from .native.canvas import run
        except Exception as e:  # PyGObject/GTK/VTE ausentes ou sem ambiente gráfico
            print(
                "Canvas nativo requer ambiente gráfico + PyGObject/GTK3/VTE "
                "(apt: python3-gi gir1.2-gtk-3.0 gir1.2-vte-2.91).\n"
                "Rode com o Python do sistema (que tem o python3-gi) num desktop.\n"
                f"detalhe: {e}"
            )
            return 1
        run()
        return 0
    if argv and argv[0] == "web":
        import os

        from .web.server import serve

        host = os.environ.get("MAESTRO_WEB_HOST", "127.0.0.1")
        port = int(os.environ.get("MAESTRO_WEB_PORT", "8765"))
        serve(host=host, port=port)
        return 0
    if argv and argv[0] == "floor":
        from .cli_floor import floor_cli

        return floor_cli(argv[1:])
    if argv and argv[0] == "routine":
        from .cli_routine import routine_cli

        return routine_cli(argv[1:])
    if argv and argv[0] == "tui":
        from .bootstrap import build_controller, log_path
        from .tui.app import run
        from .visibility.tmux import TmuxObserver, tmux_available

        controller, store = build_controller()
        observer = TmuxObserver()
        if tmux_available():
            observer.start(log_path())  # log no tmux (não-TUI como dados)
            print("observabilidade: tmux attach -t maestro-observe")
        try:
            run(controller)
        finally:
            observer.stop()
            store.close()
        return 0
    print(
        f"maestro console {__version__}\n"
        "Uso:\n"
        "  maestro tui        inicia a interface de terminal\n"
        "  maestro web        inicia a Web UI (http://127.0.0.1:8765)\n"
        "  maestro canvas     app nativo (GTK+VTE) na tela do dispositivo\n"
        "  maestro floor ...  ambientes isolados (git worktree): create/list/preview/merge/rm/run\n"
        "  maestro routine .. prompts agendados: add/list/rm/run/enable/disable/serve\n"
        "  maestro --version  mostra a versão"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
