"""Testes de notes core + ponte nota↔markdown (V9-S2)."""

from maestro.engine.notes import (
    Note,
    Notes,
    file_to_note,
    md_enter_continuation,
    md_line_prefix,
    md_spans,
    md_to_pango,
    md_wrap,
    md_wrap_toggle,
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


def test_size_default_e_persistencia(tmp_path):
    n, store = _notes(tmp_path)
    a = n.create("t", "b")
    assert a.width == 200.0 and a.height == 110.0  # defaults == tamanho atual do corpo
    a.width, a.height = 320.0, 240.0
    n.save(a)
    got = n.get(a.id)
    assert got.width == 320.0 and got.height == 240.0
    assert n.list()[0].height == 240.0
    store.close()


def test_cor_e_pin_default_e_persistencia(tmp_path):
    n, store = _notes(tmp_path)
    a = n.create("t", "b")
    assert a.color == "" and a.pinned is False and a.font == ""  # defaults
    assert a.width == 200.0 and a.height == 110.0
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
    assert got.width == 200.0 and got.height == 110.0


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


def test_md_wrap_toggle_adiciona_e_remove():
    # adiciona quando não há negrito
    new, cs, ce = md_wrap_toggle("ola mundo", 4, 9, "**", "**")
    assert new == "ola **mundo**" and new[cs:ce] == "mundo"
    # remove quando a seleção JÁ inclui os marcadores
    new2, cs2, ce2 = md_wrap_toggle("ola **mundo**", 4, 13, "**", "**")
    assert new2 == "ola mundo" and new2[cs2:ce2] == "mundo"
    # remove quando os marcadores estão FORA da seleção (só "mundo" selecionado)
    new3, cs3, ce3 = md_wrap_toggle("ola **mundo**", 6, 11, "**", "**")
    assert new3 == "ola mundo" and new3[cs3:ce3] == "mundo"


def test_md_spans_estilo_ao_vivo():
    spans = md_spans("a **bold** e *i* e `c`")
    estilos = {s for *_xy, s in spans}
    assert {"bold", "italic", "code"} <= estilos
    assert (4, 8, "bold") in spans  # interno de **bold**


def test_md_spans_headings_niveis():
    assert (0, 4, "h1") in md_spans("# oi")  # linha toda vira h1
    assert any(s == "h2" for *_x, s in md_spans("##sub"))
    assert any(s == "h3" for *_x, s in md_spans("### tres"))


def test_enter_continua_checkbox():
    text = "- [ ] tarefa"
    new, cur = md_enter_continuation(text, len(text))
    assert new == "- [ ] tarefa\n- [ ] " and cur == len(new)  # próximo checkbox desmarcado


def test_enter_checkbox_marcado_gera_desmarcado():
    new, _ = md_enter_continuation("- [x] feito", len("- [x] feito"))
    assert new.endswith("\n- [ ] ")  # novo item sempre desmarcado


def test_enter_continua_bullet():
    new, _ = md_enter_continuation("- item", len("- item"))
    assert new == "- item\n- "


def test_enter_item_vazio_sai_da_lista():
    new, cur = md_enter_continuation("- [ ] ", len("- [ ] "))
    assert new == "" and cur == 0  # marcador removido (sai da lista)


def test_enter_fora_de_lista_retorna_none():
    assert md_enter_continuation("texto normal", 5) is None


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


# -- render markdown -> Pango (Fase 3) --------------------------------
def test_md_to_pango_inline():
    assert md_to_pango("**oi**") == "<b>oi</b>"
    assert md_to_pango("*oi*") == "<i>oi</i>"
    assert md_to_pango("~~oi~~") == "<s>oi</s>"
    assert md_to_pango("`x`") == "<tt>x</tt>"


def test_md_to_pango_blocos():
    assert md_to_pango("- [ ] a") == "☐ a"
    assert md_to_pango("- [x] b") == "☑ b"
    assert md_to_pango("- item") == "• item"
    assert md_to_pango("* item") == "• item"


def test_md_to_pango_headings_h1_h2_h3():
    # H1/H2/H3 com tamanhos distintos (xx-large > x-large > large)
    assert md_to_pango("# T") == '<span size="xx-large" weight="bold">T</span>'
    assert md_to_pango("## T") == '<span size="x-large" weight="bold">T</span>'
    assert md_to_pango("### T") == '<span size="large" weight="bold">T</span>'


def test_md_to_pango_heading_sem_espaco_tipo_notion():
    # tolerante: '#T' (sem espaço) também vira título (como no Notion)
    assert md_to_pango("#T") == '<span size="xx-large" weight="bold">T</span>'
    assert md_to_pango("##T") == '<span size="x-large" weight="bold">T</span>'
    assert md_to_pango("####x") == "####x"  # 4+ # não é título (vira texto)


def test_md_to_pango_escapa_entidades():
    # <, &, > viram entidades ANTES de inserir tags (senão quebra o markup do Pango)
    assert md_to_pango("a < b & c > d") == "a &lt; b &amp; c &gt; d"
    assert md_to_pango("**a & b**") == "<b>a &amp; b</b>"


def test_md_to_pango_multilinha_e_combinado():
    assert md_to_pango("**a**\n- x") == "<b>a</b>\n• x"
    assert md_to_pango("# T\n`c` e *i*") == (
        '<span size="xx-large" weight="bold">T</span>\n<tt>c</tt> e <i>i</i>'
    )


def test_md_to_pango_vazio():
    assert md_to_pango("") == ""


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


def test_file_to_note_preserva_font_e_tamanho(tmp_path):
    # guarda o bug latente: o round-trip agent-to-note não pode descartar font/width/height
    note = Note("i", "T", "x", 0, 0, color="blue", pinned=True,
                font="Mono 13", width=333.0, height=222.0)
    note_to_file(note, tmp_path / "ws")
    upd = file_to_note(note, tmp_path / "ws")
    assert upd.font == "Mono 13" and upd.width == 333.0 and upd.height == 222.0
    assert upd.color == "blue" and upd.pinned is True


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
