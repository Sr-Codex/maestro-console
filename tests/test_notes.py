"""Testes de notes core + ponte nota↔markdown (V9-S2)."""

from maestro.engine.notes import (
    Note,
    Notes,
    file_to_note,
    md_line_prefix,
    md_wrap,
    note_to_file,
    parse_markdown,
    render_markdown,
)
from maestro.engine.state.store import Store


def _notes(tmp_path):
    store = Store(tmp_path / "m.db")
    return Notes(store), store


# -- C4: cor e pin ------------------------------------------------------
def test_font_default_e_persistencia(tmp_path):
    n, store = _notes(tmp_path)
    a = n.create("t", "b")
    assert a.font == ""  # default: fonte do tema
    a.font = "DejaVu Sans Bold 14"
    n.save(a)
    assert n.get(a.id).font == "DejaVu Sans Bold 14"
    assert n.list()[0].font == "DejaVu Sans Bold 14"
    store.close()


def test_cor_e_pin_default_e_persistencia(tmp_path):
    n, store = _notes(tmp_path)
    a = n.create("t", "b")
    assert a.color == "" and a.pinned is False and a.font == ""  # defaults
    a.color = "green"
    a.pinned = True
    n.save(a)
    got = n.get(a.id)
    assert got.color == "green" and got.pinned is True
    assert n.list()[0].pinned is True  # também vem no list
    store.close()


def test_set_position_preserva_cor_pin(tmp_path):
    n, store = _notes(tmp_path)
    a = n.create("t", "b")
    a.color = "blue"
    a.pinned = True
    n.save(a)
    n.set_position(a.id, 99, 88)  # mover não pode perder cor/pin
    got = n.get(a.id)
    assert (got.x, got.y) == (99, 88)
    assert got.color == "blue" and got.pinned is True
    store.close()


def test_migracao_db_antigo_sem_colunas(tmp_path):
    # simula DB legado: cria tabela notes SEM color/pinned, depois abre com Store (migra)
    import sqlite3

    db = tmp_path / "legacy.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE notes (id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,"
        " x REAL NOT NULL, y REAL NOT NULL, updated_at REAL NOT NULL)"
    )
    con.execute("INSERT INTO notes VALUES('n1','t','b',1,2,0)")
    con.commit()
    con.close()
    n = Notes(Store(db))  # Store.__init__ roda _migrate (ALTER TABLE)
    got = n.get("n1")
    # migrou sem perder; colunas novas vêm com default
    assert got is not None and got.color == "" and got.pinned is False and got.font == ""


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


# -- barra de contexto: formatação markdown (Fase 1) ------------------
def test_md_wrap_com_selecao():
    # "ola mundo": envolve [4,9) ("mundo") com ** .. **
    new, cs, ce = md_wrap("ola mundo", 4, 9, "**", "**")
    assert new == "ola **mundo**"
    assert new[cs:ce] == "mundo"  # seleção continua sobre o texto, não os marcadores


def test_md_wrap_sem_selecao_cursor_entre_marcadores():
    new, cs, ce = md_wrap("ab", 1, 1, "`", "`")
    assert new == "a``b"
    assert cs == ce == 2  # cursor fica ENTRE os dois `


def test_md_line_prefix_no_inicio():
    new, ncur = md_line_prefix("titulo", 3, "# ")
    assert new == "# titulo" and ncur == 5


def test_md_line_prefix_linha_do_meio():
    # cursor na 2ª linha -> prefixa só ela
    text = "linha1\nlinha2"
    new, ncur = md_line_prefix(text, 9, "- [ ] ")
    assert new == "linha1\n- [ ] linha2"
    assert new[7:13] == "- [ ] "  # prefixo no início da 2ª linha
    assert ncur == 15  # cursor acompanha o deslocamento (+6)


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
