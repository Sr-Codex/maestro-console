"""Fase 1 (docs/26) — helpers de diálogo `_hint_label` / `_confirm_dialog`.

Testes gi: criam widgets Gtk REAIS, então precisam de `gi` + um DISPLAY (rodam no python
do SISTEMA; o `.venv` gi-free os PULA, como toda a suíte de canvas). A guarda CI-safe do
bug de largura — que roda no venv — é o `test_dialog_width_guard.py` (Fase 4).
"""

import pytest

pytest.importorskip("gi")
import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from canvas_harness import win as _win  # noqa: E402
from gi.repository import Gtk  # noqa: E402

from maestro.engine.state.store import Store  # noqa: E402
from maestro.native.canvas import CanvasWindow  # noqa: E402


def _children(widget):
    """Filhos de um container GTK4 (não há get_children; anda pela linked list)."""
    out, c = [], widget.get_first_child()
    while c is not None:
        out.append(c)
        c = c.get_next_sibling()
    return out


# -- _hint_label (a fábrica que mata o bug de largura) --

def test_hint_label_sempre_limita_largura():
    lbl = CanvasWindow._hint_label("mensagem bem longa " * 20)
    assert lbl.get_wrap() is True
    assert lbl.get_max_width_chars() == 44  # sem isto a Gtk.Window esticaria


def test_hint_label_preserva_quebras_manuais():
    lbl = CanvasWindow._hint_label("linha1\nlinha2")  # ex.: _unload_msg
    assert "\n" in lbl.get_label()  # soft-wrap POR CIMA do \n, sem strip


def test_hint_label_chars_customizavel():
    assert CanvasWindow._hint_label("x", 60).get_max_width_chars() == 60


# -- _confirm_dialog (colapsa os _confirm_* e já traz _hint_label) --

def _mkwin(tmp_path, store):
    w = _win(store, tmp_path, "n1")
    w.win = Gtk.Window()  # _dialog faz set_transient_for(self.win)
    return w


def test_confirm_dialog_estrutura_labels_css_e_callback(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mkwin(tmp_path, store)
        fired = {"n": 0}
        win = w._confirm_dialog("T", "msg", primary="Confirmar",
                                on_primary=lambda: fired.__setitem__("n", fired["n"] + 1))
        kids = _children(win.get_child())
        assert isinstance(kids[0], Gtk.Label)
        assert kids[0].get_max_width_chars() == 44  # mensagem via _hint_label → sem bug
        btns = _children(kids[-1])  # rodapé
        assert [b.get_label() for b in btns] == ["Cancelar", "Confirmar"]
        assert btns[1].has_css_class("suggested-action")
        btns[1].emit("clicked")  # primário → on_primary() e destrói
        assert fired["n"] == 1


def test_confirm_dialog_destructive_e_sem_cancel(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mkwin(tmp_path, store)
        win = w._confirm_dialog("T", "msg", primary="Parar tudo", on_primary=lambda: None,
                                destructive=True, cancel=False)
        btns = _children(_children(win.get_child())[-1])
        assert [b.get_label() for b in btns] == ["Parar tudo"]  # sem Cancelar (variante OK/info)
        assert btns[0].has_css_class("destructive-action")
        win.destroy()


def test_confirm_dialog_extra_entre_msg_e_rodape(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mkwin(tmp_path, store)
        entry = Gtk.Entry()
        win = w._confirm_dialog("T", "msg", primary="OK", on_primary=lambda: None, extra=entry)
        kids = _children(win.get_child())
        assert kids.index(entry) == 1  # logo após o hint, antes do rodapé
        win.destroy()


# -- _dialog_footer (N2 item 5: rodapé dos form-heavy + Enter→primário) --

def test_dialog_footer_estrutura_ordem_css_e_default(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mkwin(tmp_path, store)
        win, box = w._dialog("T")
        fired = {"n": 0}
        extra = Gtk.Button(label="Zerar")
        prim = w._dialog_footer(win, box, primary="Salvar",
                                on_primary=lambda: fired.__setitem__("n", fired["n"] + 1),
                                extra=extra)
        btns = _children(_children(box)[-1])  # rodapé é o último filho do box
        assert [b.get_label() for b in btns] == ["Cancelar", "Zerar", "Salvar"]
        assert btns[-1].has_css_class("suggested-action")
        assert win.get_default_widget() is prim  # Enter → primário (API canônica)
        btns[-1].emit("clicked")
        assert fired["n"] == 1


def test_dialog_footer_cancel_false_e_destructive(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mkwin(tmp_path, store)
        win, box = w._dialog("T")
        prim = w._dialog_footer(win, box, primary="Apagar", on_primary=lambda: None,
                                destructive=True, cancel=False)
        btns = _children(_children(box)[-1])
        assert [b.get_label() for b in btns] == ["Apagar"]  # sem Cancelar
        assert prim.has_css_class("destructive-action")
        win.destroy()


def test_dialog_footer_keep_open_nao_fecha(tmp_path):
    # diálogos que reabrem a si mesmos (workspaces/team): o footer NÃO pode destruir
    with Store(tmp_path / "m.db") as store:
        w = _mkwin(tmp_path, store)
        win, box = w._dialog("T")
        fired = {"n": 0}
        prim = w._dialog_footer(win, box, primary="Salvar", keep_open=True,
                                on_primary=lambda: fired.__setitem__("n", fired["n"] + 1))
        prim.emit("clicked")
        assert fired["n"] == 1
        assert win.get_child() is not None  # continua VIVA (não destruída)
        win.destroy()


def test_dialog_scroll_opt_in(tmp_path):
    # N2 item 6: scroll=True embrulha o box num ScrolledWindow; default NÃO
    with Store(tmp_path / "m.db") as store:
        w = _mkwin(tmp_path, store)
        win_plain, box_plain = w._dialog("T")
        assert win_plain.get_child() is box_plain  # sem scroll: box é filho direto
        win_sc, box_sc = w._dialog("T", scroll=True)
        sc = win_sc.get_child()
        assert isinstance(sc, Gtk.ScrolledWindow)
        # GTK4: o ScrolledWindow embrulha um box não-scrollável num Viewport automático
        vp = sc.get_child()
        inner = vp.get_child() if isinstance(vp, Gtk.Viewport) else vp
        assert inner is box_sc  # o box vive DENTRO do scroller (via viewport)
        assert sc.get_propagate_natural_height() is True  # cresce até max_h, aí rola
        win_plain.destroy()
        win_sc.destroy()


def test_dialog_footer_entries_ativam_default(tmp_path):
    # Enter numa Gtk.Entry do corpo aciona o primário (set_activates_default em toda entry)
    with Store(tmp_path / "m.db") as store:
        w = _mkwin(tmp_path, store)
        win, box = w._dialog("T")
        e_top = Gtk.Entry()
        box.append(e_top)
        nested = Gtk.Box()  # entry aninhada (numa row) também deve ser pega (recursivo)
        e_deep = Gtk.Entry()
        nested.append(e_deep)
        box.append(nested)
        w._dialog_footer(win, box, primary="OK", on_primary=lambda: None)
        assert e_top.get_activates_default() is True
        assert e_deep.get_activates_default() is True
        win.destroy()
