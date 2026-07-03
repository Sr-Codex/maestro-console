"""Testes de attention — 'o que precisa de você' (V11-S1)."""

from maestro.engine.attention import (
    ATTENTION_STATES,
    ATTENTION_VISUAL_STATES,
    attention_items,
    attention_nids,
    notify,
)
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


def test_attention_visual_states():
    assert ATTENTION_VISUAL_STATES == {"waiting", "blocked", "failed"}


class _It:  # stub de AttentionItem (só precisa de .agent)
    def __init__(self, agent):
        self.agent = agent


def test_attention_nids_uniao_envelope_e_visual():
    # envelope: 'a' acionável; visual: 'c' está "waiting" (monitor de quietude, sem envelope)
    env = [_It("a")]
    node_states = {"a": "busy", "c": "waiting", "d": "idle", "e": "failed"}
    present = {"a", "c", "d", "e"}
    nids = attention_nids(env, node_states, present)
    assert nids == ["a", "c", "e"]  # envelope primeiro; 'd' (idle) fica de fora


def test_attention_nids_dedup_envelope_tem_prioridade():
    # 'a' está no envelope E com estado visual de atenção → aparece UMA vez, na posição do envelope
    env = [_It("a")]
    node_states = {"a": "waiting", "b": "blocked"}
    assert attention_nids(env, node_states, {"a", "b"}) == ["a", "b"]


def test_attention_nids_filtra_por_present():
    # nó que não existe mais no canvas não conta (evita apontar pra fantasma)
    env = [_It("sumido")]
    node_states = {"vivo": "waiting", "fantasma": "failed"}
    assert attention_nids(env, node_states, {"vivo"}) == ["vivo"]


def test_attention_nids_vazio_quando_nada_pede_atencao():
    assert attention_nids([], {"a": "busy", "b": "idle", "c": "done"}, {"a", "b", "c"}) == []


def test_notify_no_op_sem_binario(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _x: None)
    assert notify("oi", "corpo") is False
