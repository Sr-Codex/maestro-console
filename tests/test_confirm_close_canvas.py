"""Fase A / A2 (docs/26 → plano UI): ✕ fecha o nó COM confirmação (_confirm_close_node).

Teste gi (widgets Gtk reais → device/system-python; venv gi-free PULA). Prova: confirma sempre,
mensagem graduada (heavy = agente/sessão/órfão/unloaded vs shell simples), e o primário fecha.
"""

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
    w = _win(store, tmp_path, "n1", term_=object())
    w.win = Gtk.Window()          # _dialog faz set_transient_for(self.win)
    w._agent_nids = set()
    w._select = lambda _x: None
    w._closed = []
    w._close_node = lambda nid: w._closed.append(nid)
    return w


def _footer_btns(win):
    return _children(_children(win.get_child())[-1])


def test_shell_simples_confirma_msg_leve(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mk(tmp_path, store)
        captured = {}
        orig = type(w)._confirm_dialog
        w._confirm_dialog = lambda t, m, **k: captured.update(
            m=m, k=k, win=orig(w, t, m, **k)) or captured["win"]
        w._confirm_close_node("n1")
        assert "DE VEZ" in captured["m"] and "DESCARTA" not in captured["m"]
        assert captured["k"]["destructive"] is True


def test_agente_confirma_msg_reforcada_e_fecha(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mk(tmp_path, store)
        w._agent_nids = {"n1"}
        w._confirm_close_node("n1")
        # o diálogo real foi montado; pega o win pelo transient? mais simples: re-monta com captura
        captured = {}
        orig = type(w)._confirm_dialog

        def _spy(t, m, **k):
            captured["win"] = orig(w, t, m, **k)
            return captured["win"]

        w._confirm_dialog = _spy
        w._confirm_close_node("n1")
        btns = _footer_btns(captured["win"])
        assert [b.get_label() for b in btns] == ["Cancelar", "✕ Fechar"]
        btns[1].emit("clicked")
        assert w._closed == ["n1"]


def test_sessao_capturada_conta_como_heavy(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mk(tmp_path, store)
        w.model.set_node_cfg("n1", "session", "sid-1")
        captured = {}
        orig = type(w)._confirm_dialog
        w._confirm_dialog = lambda t, m, **k: captured.update(m=m) or orig(w, t, m, **k)
        w._confirm_close_node("n1")
        assert "DESCARTA a" in captured["m"]


def test_nid_inexistente_noop(tmp_path):
    with Store(tmp_path / "m.db") as store:
        w = _mk(tmp_path, store)
        called = []
        w._confirm_dialog = lambda *a, **k: called.append(1)
        w._confirm_close_node("ghost")
        assert called == [] and w._closed == []
