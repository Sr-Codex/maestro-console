"""Testes de temas de terminal (V11-S4) — paletas + persistência, sem GTK."""

from maestro.engine.state.store import Store
from maestro.native.state import CanvasModel
from maestro.native.themes import DEFAULT_THEME, THEMES, get_theme, theme_names


def test_temas_tem_estrutura_valida():
    for name, th in THEMES.items():
        assert {"fg", "bg", "palette"} <= set(th), name  # +flag opcional "dark"
        assert len(th["palette"]) == 16, name  # 16 cores ANSI
        for c in [th["fg"], th["bg"], *th["palette"]]:
            assert c.startswith("#") and len(c) == 7, (name, c)  # hex #rrggbb


def test_parse_ghostty_e_bundle():
    from maestro.native.themes import parse_ghostty, theme_is_dark
    t = parse_ghostty("palette = 0=#000000\nbackground = #ffffff\nforeground = #111111\n"
                      + "\n".join(f"palette = {i}=#0a0a0a" for i in range(1, 16)))
    assert t and t["bg"] == "#ffffff" and t["dark"] is False
    assert parse_ghostty("background = #fff") is None  # incompleto → None
    # bundle traz claros e escuros
    names = theme_names()
    assert any(not theme_is_dark(n) for n in names) and any(theme_is_dark(n) for n in names)


def test_theme_names_inclui_conhecidos():
    names = theme_names()
    assert "default" in names and "dracula" in names and "catppuccin" in names


def test_get_theme_fallback():
    assert get_theme("inexistente") is THEMES[DEFAULT_THEME]
    assert get_theme("dracula") is THEMES["dracula"]


def test_persistencia_tema(tmp_path):
    store = Store(tmp_path / "m.db")
    m = CanvasModel(store)
    assert m.terminal_theme() == "default"  # default
    m.set_terminal_theme("dracula")
    assert m.terminal_theme() == "dracula"
    store.close()
    # sobrevive a reabrir
    store2 = Store(tmp_path / "m.db")
    assert CanvasModel(store2).terminal_theme() == "dracula"
    store2.close()
