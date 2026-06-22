"""Testes da command palette (V11-S2) — fuzzy + build, sem GTK."""

from types import SimpleNamespace

from maestro.native.palette import PaletteItem, build_palette_items, fuzzy, fuzzy_score


def test_fuzzy_score_subsequencia():
    assert fuzzy_score("cr", "coder-reviewer") is not None
    assert fuzzy_score("xyz", "coder") is None
    assert fuzzy_score("", "qualquer") == 0


def test_fuzzy_score_bonus_inicio_e_contiguidade():
    # "cod" casa no início e contíguo em "coder" -> score alto
    s_start = fuzzy_score("cod", "coder")
    s_mid = fuzzy_score("der", "coder")  # não no início
    assert s_start > s_mid


def test_fuzzy_filtra_e_ordena():
    items = [
        PaletteItem("agent", "claude", "claude"),  # 'co' não é subsequência
        PaletteItem("agent", "codex", "codex"),  # casa no início (contíguo)
        PaletteItem("team", "discot-co", "discot-co"),  # casa no meio
    ]
    out = fuzzy("co", items)
    labels = [i.label for i in out]
    assert "claude" not in labels
    assert set(labels) == {"codex", "discot-co"}
    assert labels[0] == "codex"  # início+contiguidade vence o match no meio


def test_fuzzy_query_vazia_retorna_todos():
    items = [PaletteItem("agent", "a", "a"), PaletteItem("agent", "b", "b")]
    assert fuzzy("  ", items) == items


def test_build_palette_items():
    floors = [SimpleNamespace(name="exp1")]
    notes = [SimpleNamespace(id="abcdef123", title="Contexto")]
    routines = [SimpleNamespace(name="ci")]
    items = build_palette_items(
        agents=["claude"], teams=["coder-reviewer"], floors=floors, notes=notes, routines=routines
    )
    kinds = {i.kind for i in items}
    assert kinds == {"agent", "team", "floor", "note", "routine"}
    note_item = next(i for i in items if i.kind == "note")
    assert note_item.ref == "abcdef123" and "Contexto" in note_item.label


def test_build_note_sem_titulo_usa_id():
    notes = [SimpleNamespace(id="abcdef123456", title="")]
    item = build_palette_items(notes=notes)[0]
    assert "abcdef" in item.label  # prefixo do id
