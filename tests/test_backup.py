"""Testes de backup & restore (V11-S3)."""

from maestro.cli_backup import backup_cli
from maestro.engine.backup import backup_to_file, count_records, restore_from_file
from maestro.engine.notes import Notes
from maestro.engine.routines import Routines
from maestro.engine.state.store import Store
from maestro.engine.teams import Role, Team, Teams


def _populate(store):
    Teams(store).save(Team("meu-time", [Role("coder", "claude", "impl", color="#123456")]))
    Notes(store).create("Contexto", "corpo da nota", x=5, y=7)
    Routines(store).create("ci", "claude", ["p1", "p2"], interval_s=120)
    store.add_edge("claude", "codex")
    store.set_node_position("claude", 10, 20)
    store.set_ui("native_zoom", 1.3)


def test_export_import_roundtrip(tmp_path):
    s1 = Store(tmp_path / "a.db")
    _populate(s1)
    data = s1.export_all()
    s1.close()

    s2 = Store(tmp_path / "b.db")
    s2.import_all(data)
    # estado igual nas tabelas-chave
    assert "meu-time" in Teams(s2).list()
    assert Teams(s2).get("meu-time").roles[0].color == "#123456"
    assert Notes(s2).list()[0].title == "Contexto"
    assert Routines(s2).list()[0].steps == ["p1", "p2"]
    assert s2.get_edges() == [("claude", "codex")]
    assert s2.get_node_positions()["claude"] == {"x": 10, "y": 20}
    assert s2.get_ui("native_zoom") == 1.3
    s2.close()


def test_import_replace_limpa_antes(tmp_path):
    s = Store(tmp_path / "a.db")
    Notes(s).create("antiga", "x")
    # importa um snapshot com OUTRA nota -> replace remove a antiga
    snap = {
        "notes": [{"id": "n1", "title": "nova", "body": "b", "x": 0, "y": 0, "updated_at": 1.0}]
    }
    s.import_all(snap)
    notes = Notes(s).list()
    assert len(notes) == 1 and notes[0].title == "nova"
    s.close()


def test_backup_restore_file(tmp_path):
    s1 = Store(tmp_path / "a.db")
    _populate(s1)
    f = tmp_path / "snap.json"
    data = backup_to_file(s1, f)
    s1.close()
    assert f.exists() and count_records(data) >= 4

    s2 = Store(tmp_path / "b.db")
    restore_from_file(s2, f)
    assert Notes(s2).list()[0].title == "Contexto"
    s2.close()


def test_cli_backup_e_restore(tmp_path, capsys):
    home_a = tmp_path / "a"
    home_b = tmp_path / "b"
    sa = Store(home_a / "maestro.db")
    _populate(sa)
    sa.close()
    f = str(tmp_path / "snap.json")

    assert backup_cli(["backup", f], home=str(home_a)) == 0
    assert "backup salvo" in capsys.readouterr().out
    assert backup_cli(["restore", f], home=str(home_b)) == 0
    assert "restaurado" in capsys.readouterr().out

    sb = Store(home_b / "maestro.db")
    assert Routines(sb).list()[0].name == "ci"
    sb.close()


def test_cli_restore_arquivo_inexistente(tmp_path, capsys):
    assert backup_cli(["restore", str(tmp_path / "nada.json")], home=str(tmp_path)) == 1
    assert "não existe" in capsys.readouterr().out


def test_floors_no_backup(tmp_path):
    # floors também entram no snapshot (registro; o worktree em si é do git)
    s = Store(tmp_path / "a.db")
    s.add_floor("exp", "floor/exp", "/wt/exp", "main")
    data = s.export_all()
    assert data["floors"][0]["name"] == "exp"
    s.close()
