"""Testes do histórico de handoffs (E4-S3)."""

from maestro.engine.history import format_history, recent
from maestro.engine.state.store import Store


def test_recent_ordem_e_limite(tmp_path):
    with Store(tmp_path / "m.db") as s:
        for i in range(5):
            s.log_envelope(
                message_id=f"m{i}",
                task_id=f"t{i}",
                sender="orchestrator",
                recipient="claude",
                state="DONE",
                payload=None,
            )
        rows = recent(s, limit=3)
        assert len(rows) == 3
        # mais recentes primeiro
        assert rows[0]["message_id"] == "m4"


def test_format_history(tmp_path):
    with Store(tmp_path / "m.db") as s:
        s.log_envelope(
            message_id="m1",
            task_id="t1",
            sender="claude",
            recipient="orchestrator",
            state="DONE",
            payload=None,
        )
        txt = format_history(recent(s))
        assert "claude -> orchestrator [DONE]" in txt


def test_format_history_vazio():
    assert format_history([]) == "(sem histórico)"
