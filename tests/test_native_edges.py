"""Testes da persistência de cabos (V7-S1) — Store.edges + EdgeModel, sem GTK."""

from maestro.engine.state.store import Store
from maestro.native.state import EdgeModel


def _store(tmp_path):
    return Store(tmp_path / "edges.db")


def test_add_e_list(tmp_path):
    s = _store(tmp_path)
    m = EdgeModel(s)
    assert m.add("a", "b") is True
    assert m.add("b", "c") is True
    assert m.list() == [("a", "b"), ("b", "c")]
    s.close()


def test_dedup(tmp_path):
    s = _store(tmp_path)
    m = EdgeModel(s)
    m.add("a", "b")
    m.add("a", "b")  # idempotente (PK composta + DO NOTHING)
    assert m.list() == [("a", "b")]
    s.close()


def test_self_loop_barrado(tmp_path):
    s = _store(tmp_path)
    m = EdgeModel(s)
    assert m.add("a", "a") is False
    assert m.list() == []
    s.close()


def test_remove(tmp_path):
    s = _store(tmp_path)
    m = EdgeModel(s)
    m.add("a", "b")
    m.add("b", "c")
    m.remove("a", "b")
    assert m.list() == [("b", "c")]
    s.close()


def test_persiste_entre_aberturas(tmp_path):
    db = tmp_path / "edges.db"
    s1 = Store(db)
    EdgeModel(s1).add("x", "y")
    s1.close()
    s2 = Store(db)
    assert EdgeModel(s2).list() == [("x", "y")]
    s2.close()


def test_cabo_nota_para_no(tmp_path):
    # Fase 4: a nota é endpoint de cabo (id string arbitrário) — sem migração de schema
    s = _store(tmp_path)
    m = EdgeModel(s)
    assert m.add("note-abc", "node-1") is True
    assert ("note-abc", "node-1") in m.list()
    m.remove("note-abc", "node-1")
    assert m.list() == []
    s.close()


def test_direcao_importa(tmp_path):
    s = _store(tmp_path)
    m = EdgeModel(s)
    m.add("a", "b")
    m.add("b", "a")  # cabo inverso é distinto
    assert set(m.list()) == {("a", "b"), ("b", "a")}
    s.close()
