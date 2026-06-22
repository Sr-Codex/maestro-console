"""Testes de attention — 'o que precisa de você' (V11-S1)."""

from maestro.engine.attention import ATTENTION_STATES, attention_items, notify
from maestro.engine.state.store import Store


def _log(store, agent, state, mid):
    store.log_envelope(
        message_id=mid, task_id="t", sender=agent, recipient="orchestrator", state=state, payload={}
    )


def test_lista_estados_acionaveis(tmp_path):
    s = Store(tmp_path / "m.db")
    _log(s, "claude", "BLOCKED", "1")
    _log(s, "codex", "FAILED", "2")
    items = attention_items(s)
    by = {i.agent: i.state for i in items}
    assert by == {"claude": "BLOCKED", "codex": "FAILED"}
    s.close()


def test_done_nao_aparece(tmp_path):
    s = Store(tmp_path / "m.db")
    _log(s, "claude", "DONE", "1")
    assert attention_items(s) == []
    s.close()


def test_estado_mais_recente_vence(tmp_path):
    s = Store(tmp_path / "m.db")
    _log(s, "claude", "BLOCKED", "1")  # antigo
    _log(s, "claude", "DONE", "2")  # resolveu depois -> NÃO precisa de atenção
    assert attention_items(s) == []
    s.close()


def test_voltou_a_precisar(tmp_path):
    s = Store(tmp_path / "m.db")
    _log(s, "claude", "DONE", "1")
    _log(s, "claude", "NEEDS_INPUT", "2")  # mais recente
    items = attention_items(s)
    assert len(items) == 1 and items[0].state == "NEEDS_INPUT"
    s.close()


def test_ordenado_por_ts_desc(tmp_path):
    s = Store(tmp_path / "m.db")
    _log(s, "a", "BLOCKED", "1")
    _log(s, "b", "FAILED", "2")  # mais recente
    items = attention_items(s)
    assert [i.agent for i in items] == ["b", "a"]
    s.close()


def test_attention_states():
    assert ATTENTION_STATES == {"BLOCKED", "FAILED", "NEEDS_INPUT"}


def test_notify_no_op_sem_binario(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _x: None)
    assert notify("oi", "corpo") is False
