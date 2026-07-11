"""Cápsula contextual de GRUPO (docs/28) — seleção cairo + pílula + apagar confirmado.

Teste gi (widgets Gtk reais → python do SISTEMA; o venv gi-free PULA). Prova as emendas do
Fable: (1) `_select` redesenha o plane quando a seleção antiga OU nova é grupo (outline é
cairo, não CSS); (3) `_close_group` limpa a seleção (pílula não fica órfã); (4) `_sel_gid`
guarda gid morto; (2) apagar passa pelo `_confirm_dialog`; (8) drag/resize não ressuscitam
grupo morto no meio do gesto.
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("gi")
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from canvas_harness import win as _win  # noqa: E402
from gi.repository import Gtk  # noqa: E402

from maestro.engine.state.store import Store  # noqa: E402


def _children(w):
    out, c = [], w.get_first_child()
    while c is not None:
        out.append(c)
        c = c.get_next_sibling()
    return out


def _mk(tmp_path, store):
    """CanvasWindow do harness + estado de grupo/seleção que os métodos sob teste leem."""
    w = _win(store, tmp_path, "n1")
    w.win = Gtk.Window()  # _dialog faz set_transient_for(self.win)
    w._selected = None
    w.note_frames = {}
    w._ft_frames = {}
    w._note_editing = None
    draws = {"n": 0}
    w.plane = SimpleNamespace(
        queue_draw=lambda: draws.__setitem__("n", draws["n"] + 1),
        set_cursor=lambda _c=None: None,
    )
    w._draws = draws
    w.groups = None  # _close_group tolera sem storage
    w._group_base = {"g1": (0.0, 0.0)}
    w._group_size = {"g1": (600.0, 360.0)}
    w._group_color = {"g1": "blue"}
    w._group_title = {"g1": "Equipe"}
    w._group_manual = {}
    w._group_user_sized = set()
    w._mm_refresh = lambda: None
    w._group_ctx_bar = Gtk.Box(visible=False)  # a pílula (visibilidade via _update_ctx)
    return w


# -- _sel_gid (guarda de gid morto — emenda 4) --

def test_sel_gid_guarda(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mk(tmp_path, store)
        assert w._sel_gid() is None  # nada selecionado
        w._selected = ("node", "n1")
        assert w._sel_gid() is None  # seleção não é grupo
        w._selected = ("group", "g1")
        assert w._sel_gid() == "g1"
        w._selected = ("group", "morto")
        assert w._sel_gid() is None  # gid que não existe mais → no-op seguro


# -- _select de grupo: queue_draw (emenda 1) + pílula alterna --

def test_select_grupo_redesenha_e_mostra_pilula(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mk(tmp_path, store)
        base = w._draws["n"]
        w._select(("group", "g1"))
        assert w._selected == ("group", "g1")
        assert w._draws["n"] == base + 1  # outline é CAIRO: selecionar TEM que redesenhar
        assert w._group_ctx_bar.get_visible() is True
        w._select(None)  # limpar também redesenha (o outline precisa SUMIR)
        assert w._draws["n"] == base + 2
        assert w._group_ctx_bar.get_visible() is False


def test_select_node_apos_grupo_esconde_e_redesenha(tmp_path):
    # caminho _on_frame_press: trocar grupo→nó não passa pelo _pan_begin; o redraw
    # tem que vir do próprio _select (senão o outline do grupo fica STALE pintado)
    with Store(tmp_path / "m.db") as store:
        w = _mk(tmp_path, store)
        w._select(("group", "g1"))
        base = w._draws["n"]
        w._select(("node", "n1"))
        assert w._draws["n"] == base + 1  # redesenhou pra apagar o outline do grupo
        assert w._group_ctx_bar.get_visible() is False


# -- _close_group limpa a seleção (emenda 3) --

def test_close_group_limpa_selecao(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mk(tmp_path, store)
        w._select(("group", "g1"))
        w._close_group("g1")
        assert w._selected is None  # pílula NÃO fica órfã apontando pra gid morto
        assert "g1" not in w._group_base
        assert w._group_ctx_bar.get_visible() is False


def test_close_group_de_outro_nao_mexe_na_selecao(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mk(tmp_path, store)
        w._group_base["g2"] = (100.0, 100.0)
        w._select(("group", "g1"))
        w._close_group("g2")
        assert w._selected == ("group", "g1")  # apagar OUTRO grupo não desmarca este


# -- apagar passa pelo _confirm_dialog (emenda 2) --

def test_confirm_close_group_primario_apaga(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mk(tmp_path, store)
        w._select(("group", "g1"))
        dlg = w._confirm_close_group("g1")
        btns = _children(_children(dlg.get_child())[-1])
        assert [b.get_label() for b in btns] == ["Cancelar", "Apagar"]
        assert btns[1].has_css_class("destructive-action")
        assert "g1" in w._group_base  # nada apagado antes do clique
        btns[1].emit("clicked")  # confirma
        assert "g1" not in w._group_base
        assert w._selected is None


# -- guards anti-ressurreição no meio do gesto (emenda 8) --

def test_pan_update_resize_de_grupo_morto_aborta(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mk(tmp_path, store)
        w._wake_cables = lambda: None
        w._item_resize = None
        w._drag = None
        w._group_resize = {"id": "morto", "size": (600.0, 360.0)}
        w._pan_update(None, 10.0, 10.0)
        assert w._group_resize is None  # gesto abortado
        assert "morto" not in w._group_size  # NÃO ressuscitou


def test_pan_update_drag_de_grupo_morto_aborta(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mk(tmp_path, store)
        w._wake_cables = lambda: None
        w._item_resize = None
        w._group_resize = None
        w._drag = {"kind": "group", "id": "morto", "base": (0.0, 0.0), "members": {}}
        w._pan_update(None, 10.0, 10.0)
        assert w._drag is None  # gesto abortado
        assert "morto" not in w._group_base  # NÃO ressuscitou
