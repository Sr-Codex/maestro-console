"""Observabilidade via tmux (E4-S1).

Abre um pane tmux que segue (`tail -f`) o logbook da execução headless, para o
humano acompanhar/auditar (`tmux attach -t <session>`). NÃO roda o agente de
novo — é só observação do log (o agente roda uma única vez, headless).
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path


def tmux_available() -> bool:
    return shutil.which("tmux") is not None


def tail_command(session: str, log_path: str | Path) -> list[str]:
    """argv do tmux para abrir um pane seguindo o log (puro, testável)."""
    quoted = shlex.quote(str(log_path))
    return ["tmux", "new-session", "-d", "-s", session, f"tail -f {quoted}"]


class TmuxObserver:
    def __init__(self, session: str = "maestro-observe"):
        self.session = session

    def start(self, log_path: str | Path) -> None:
        if not tmux_available():
            raise RuntimeError("tmux não encontrado")
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(log_path).touch(exist_ok=True)
        subprocess.run(["tmux", "kill-session", "-t", self.session], capture_output=True)
        subprocess.run(tail_command(self.session, log_path), check=True)

    def is_running(self) -> bool:
        r = subprocess.run(["tmux", "has-session", "-t", self.session], capture_output=True)
        return r.returncode == 0

    def stop(self) -> None:
        subprocess.run(["tmux", "kill-session", "-t", self.session], capture_output=True)
