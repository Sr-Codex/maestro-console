"""Testes de grupos/áreas (C2) — CRUD + persistência, sem GTK."""

from maestro.engine.groups import Group, Groups
from maestro.engine.state.store import Store


def _groups(tmp_path):
    store = Store(tmp_path / "m.db")
    return Groups(store), store


def test_create_default_e_get(tmp_path):
    g, store = _groups(tmp_path)
    a = g.create()
    assert a.title == "Grupo" and a.color == "blue"
    assert (a.w, a.h) == (600.0, 360.0)
    got = g.get(a.id)
    assert got is not None and got.id == a.id
    store.close()


def test_save_e_list(tmp_path):
    g, store = _groups(tmp_path)
    a = g.create(title="Backend", color="green", x=10, y=20, w=400, h=300)
    a.title = "Back"
    g.save(a)
    items = g.list()
    assert len(items) == 1 and items[0].title == "Back" and items[0].color == "green"
    store.close()


def test_set_rect_e_delete(tmp_path):
    g, store = _groups(tmp_path)
    a = g.create()
    g.set_rect(a.id, 50, 60, 220, 160)
    got = g.get(a.id)
    assert (got.x, got.y, got.w, got.h) == (50, 60, 220, 160)
    g.delete(a.id)
    assert g.get(a.id) is None and g.list() == []
    store.close()


def test_persiste_entre_aberturas(tmp_path):
    g, store = _groups(tmp_path)
    a = g.create(title="X")
    store.close()
    store2 = Store(tmp_path / "m.db")
    assert Groups(store2).get(a.id).title == "X"
    store2.close()


def test_backup_inclui_groups(tmp_path):
    g, store = _groups(tmp_path)
    g.create(title="Z")
    data = store.export_all()
    assert "groups" in data and len(data["groups"]) == 1
    store.close()


def test_roundtrip_dataclass():
    assert Group("i", "T", "blue", 1, 2, 3, 4).id == "i"
