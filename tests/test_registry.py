"""Testes do Agent Registry (E1-S4): registro, estado, sessão e persistência."""

from maestro.engine.registry import AgentRecord, AgentState, Registry
from maestro.engine.state.store import Store


def test_registra_e_consulta(tmp_path):
    with Store(tmp_path / "m.db") as s:
        reg = Registry(s)
        assert reg.get("claude") is None
        rec = reg.register("claude", "claude-code")
        assert isinstance(rec, AgentRecord)
        assert rec.id == "claude"
        assert rec.type == "claude-code"
        assert rec.state is AgentState.IDLE
        assert rec.session_id is None


def test_registra_com_sessao_e_estado(tmp_path):
    with Store(tmp_path / "m.db") as s:
        reg = Registry(s)
        rec = reg.register("codex", "codex", session_id="sid-9", state=AgentState.BUSY)
        assert rec.state is AgentState.BUSY
        assert rec.session_id == "sid-9"


def test_set_state_e_set_session(tmp_path):
    with Store(tmp_path / "m.db") as s:
        reg = Registry(s)
        reg.register("a", "claude-code")
        reg.set_state("a", AgentState.BUSY)
        assert reg.get("a").state is AgentState.BUSY
        reg.set_state("a", AgentState.ERROR)
        assert reg.get("a").state is AgentState.ERROR
        reg.set_session("a", "sid-1")
        assert reg.get("a").session_id == "sid-1"


def test_list_e_unregister(tmp_path):
    with Store(tmp_path / "m.db") as s:
        reg = Registry(s)
        reg.register("a", "claude-code")
        reg.register("b", "codex")
        ids = {r.id for r in reg.list()}
        assert ids == {"a", "b"}
        reg.unregister("a")
        assert reg.get("a") is None
        assert {r.id for r in reg.list()} == {"b"}


def test_persiste_entre_instancias(tmp_path):
    db = tmp_path / "m.db"
    with Store(db) as s:
        Registry(s).register("claude", "claude-code", state=AgentState.BUSY)
    # nova conexão/registry sobre o mesmo arquivo
    with Store(db) as s2:
        rec = Registry(s2).get("claude")
        assert rec is not None
        assert rec.state is AgentState.BUSY
