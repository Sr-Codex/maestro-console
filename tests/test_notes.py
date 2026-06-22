"""Testes de notes core + ponte nota↔markdown (V9-S2)."""

from maestro.engine.notes import (
    Note,
    Notes,
    file_to_note,
    note_to_file,
    parse_markdown,
    render_markdown,
)
from maestro.engine.state.store import Store


def _notes(tmp_path):
    store = Store(tmp_path / "m.db")
    return Notes(store), store


# -- CRUD --------------------------------------------------------------
def test_create_get_list(tmp_path):
    n, store = _notes(tmp_path)
    a = n.create("Contexto", "linha 1", x=10, y=20)
    assert n.get(a.id).title == "Contexto"
    assert n.get(a.id).body == "linha 1"
    assert [x.id for x in n.list()] == [a.id]
    store.close()


def test_update_e_posicao(tmp_path):
    n, store = _notes(tmp_path)
    a = n.create("t", "b")
    a.body = "novo corpo"
    n.save(a)
    assert n.get(a.id).body == "novo corpo"
    n.set_position(a.id, 99, 88)
    g = n.get(a.id)
    assert (g.x, g.y) == (99, 88) and g.body == "novo corpo"  # posição não apaga corpo
    store.close()


def test_delete(tmp_path):
    n, store = _notes(tmp_path)
    a = n.create("x", "y")
    n.delete(a.id)
    assert n.get(a.id) is None and n.list() == []
    store.close()


def test_persiste_entre_aberturas(tmp_path):
    n, store = _notes(tmp_path)
    a = n.create("mantem", "corpo")
    store.close()
    store2 = Store(tmp_path / "m.db")
    assert Notes(store2).get(a.id).title == "mantem"
    store2.close()


# -- markdown round-trip ----------------------------------------------
def test_render_e_parse_roundtrip():
    title, body = "Título", "linha 1\nlinha 2"
    md = render_markdown(Note("i", title, body, 0, 0))
    assert md == "# Título\n\nlinha 1\nlinha 2\n"
    assert parse_markdown(md) == (title, body)


def test_parse_sem_h1():
    assert parse_markdown("só corpo\nsem titulo") == ("", "só corpo\nsem titulo")


def test_render_sem_titulo():
    assert render_markdown(Note("i", "", "apenas corpo", 0, 0)) == "apenas corpo\n"


# -- agent-to-note (ponte arquivo) ------------------------------------
def test_note_to_file_e_volta(tmp_path):
    note = Note("i", "Tarefa", "faça X", 0, 0)
    p = note_to_file(note, tmp_path / "ws")
    assert p.read_text() == "# Tarefa\n\nfaça X\n"
    # agente "edita" o arquivo
    p.write_text("# Tarefa\n\nfeito por mim\n")
    atualizada = file_to_note(note, tmp_path / "ws")
    assert atualizada.body == "feito por mim" and atualizada.title == "Tarefa"
    assert atualizada.id == "i"  # id/pos preservados
    store_check = (atualizada.x, atualizada.y)
    assert store_check == (0, 0)


def test_file_to_note_sem_arquivo_mantem(tmp_path):
    note = Note("i", "T", "original", 0, 0)
    same = file_to_note(note, tmp_path / "vazio")
    assert same.body == "original"


def test_file_to_note_sem_h1_preserva_titulo(tmp_path):
    note = Note("i", "TituloOriginal", "x", 0, 0)
    note_to_file(note, tmp_path / "ws")
    (tmp_path / "ws" / "nota.md").write_text("corpo cru sem titulo\n")
    upd = file_to_note(note, tmp_path / "ws")
    assert upd.title == "TituloOriginal" and upd.body == "corpo cru sem titulo"
