"""Testes da observabilidade (E4-S1): logbook + comando/observer tmux."""

import time

from maestro.engine.logbook import Logbook
from maestro.visibility.tmux import TmuxObserver, tail_command, tmux_available


def test_logbook_append_e_lines(tmp_path):
    lb = Logbook(tmp_path / "logs" / "h.log")
    lb.append("agente claude -> DONE")
    lb.append("handoff -> codex")
    lines = lb.lines()
    assert len(lines) == 2
    assert "claude -> DONE" in lines[0]
    assert lines[0].startswith("[")  # timestamp


def test_tail_command():
    argv = tail_command("sess", "/tmp/x y.log")
    assert argv[:5] == ["tmux", "new-session", "-d", "-s", "sess"]
    assert "tail -f" in argv[-1]
    assert "'/tmp/x y.log'" in argv[-1]  # path com espaco e quotado


def test_observer_real_segue_log(tmp_path):
    if not tmux_available():
        return  # sem tmux, pula a parte de integração
    log = tmp_path / "h.log"
    obs = TmuxObserver(session="maestro-test-observe")
    try:
        obs.start(log)
        assert obs.is_running()
        Logbook(log).append("EVENTO-XYZ")
        time.sleep(0.6)
        cap = (
            __import__("subprocess")
            .run(
                ["tmux", "capture-pane", "-t", "maestro-test-observe", "-p"],
                capture_output=True,
                text=True,
            )
            .stdout
        )
        assert "EVENTO-XYZ" in cap
    finally:
        obs.stop()
        assert not obs.is_running()
