"""Copiar/colar no terminal focado (Ctrl+Shift+V/C) — gi.

No GTK4 o VTE não traz esses atalhos embutidos; o app fia no capture global
(`_on_key`). Achado ao testar as contas (docs/31): sem colar, o código do /login
não entrava. Mocka só o widget (fronteira); o roteamento `_on_key` é real.
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("gi")  # canvas usa PyGObject; o .venv é gi-free → python do sistema
from gi.repository import Gdk  # noqa: E402

from maestro.native.canvas import CanvasWindow  # noqa: E402

CTRL_SHIFT = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK


def _w(term):
    w = CanvasWindow.__new__(CanvasWindow)
    w._focused_nid = "n1"
    w.frames = {"n1": SimpleNamespace(_term=term)}
    w._connect_btn = None
    return w


def _term(has_sel=True):
    calls = []
    t = SimpleNamespace(
        _destroyed=False, calls=calls,
        paste_clipboard=lambda: calls.append("paste"),
        get_has_selection=lambda: has_sel,
        copy_clipboard_format=lambda fmt: calls.append("copy"),
    )
    return t


def test_ctrl_shift_v_cola_no_terminal_focado():
    t = _term()
    w = _w(t)
    assert w._on_key(None, Gdk.KEY_V, 0, CTRL_SHIFT) is True
    assert t.calls == ["paste"]


def test_ctrl_shift_c_copia_so_com_selecao():
    t = _term(has_sel=True)
    w = _w(t)
    assert w._on_key(None, Gdk.KEY_C, 0, CTRL_SHIFT) is True
    assert t.calls == ["copy"]


def test_sem_foco_nao_trata_e_propaga():
    w = _w(_term())
    w._focused_nid = None
    w.frames = {}
    # sem terminal focado o atalho não é consumido (segue a cadeia normal)
    assert w._on_key(None, Gdk.KEY_V, 0, CTRL_SHIFT) is not True
