"""Canvas nativo GTK3 + VTE (V6-S2): pan/zoom + nós-terminal arrastáveis.

Gtk.Layout = plano "infinito" (pan via arrastar o fundo); nós são molduras com
título (arraste por ele) + Vte.Terminal real; zoom via font_scale + tamanho.
Posições/zoom persistidos pelo CanvasModel (Store da engine). Headless/bwrap não
muda — VTE é a camada visual/interativa.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gdk, GLib, Gtk, Vte  # noqa: E402

from ..engine.state.store import Store  # noqa: E402
from ..engine.workspace import Workspace  # noqa: E402
from .agents import STATE_COLORS, agent_argv, installed_agents  # noqa: E402
from .state import CanvasModel  # noqa: E402

BASE_W, BASE_H = 420, 220


def _rgba(hex_color: str) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(hex_color)
    return c


def make_terminal(argv: list[str]) -> Vte.Terminal:
    term = Vte.Terminal()
    term.spawn_async(
        Vte.PtyFlags.DEFAULT,
        None,
        argv,
        None,
        GLib.SpawnFlags.DEFAULT,
        None,
        None,
        -1,
        None,
        None,
        None,
    )
    return term


class CanvasWindow:
    def __init__(self, model: CanvasModel, nodes: list[tuple[str, str, list[str]]]):
        self.model = model
        self.terms: list[Vte.Terminal] = []
        self.heads: dict[str, Gtk.EventBox] = {}
        self.win = Gtk.Window(title="maestro console 🎼 — canvas (nativo)")
        self.win.set_default_size(1000, 600)
        self.win.connect("destroy", Gtk.main_quit)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.pack_start(self._toolbar(), False, False, 0)
        self.scrolled = Gtk.ScrolledWindow()
        self.layout = Gtk.Layout()
        self.layout.set_size(5000, 4000)
        self.layout.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.layout.connect("button-press-event", self._pan_start)
        self.layout.connect("motion-notify-event", self._pan_move)
        self.layout.connect("button-release-event", self._pan_end)
        self.scrolled.add(self.layout)
        root.pack_start(self.scrolled, True, True, 0)
        self.win.add(root)

        for i, (nid, title, argv) in enumerate(nodes):
            self._add_node(nid, title, argv, default=(60 + i * 460, 60))
        self._apply_zoom()
        self._pan = None

    def _toolbar(self) -> Gtk.Widget:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for label, dz in (("−", -0.1), ("+", 0.1)):
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda _b, d=dz: self._zoom(d))
            bar.pack_start(b, False, False, 0)
        self.zlabel = Gtk.Label(label="zoom 100%")
        bar.pack_start(self.zlabel, False, False, 6)
        return bar

    def _add_node(self, nid, title, argv, default):
        frame = Gtk.Frame()
        head = Gtk.EventBox()
        head.add(Gtk.Label(label=f"  {title}  "))
        head.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        head.connect("button-press-event", self._drag_start, frame)
        head.connect("motion-notify-event", self._drag_move, frame)
        head.connect("button-release-event", self._drag_end, frame, nid)
        self.heads[nid] = head
        head.override_background_color(Gtk.StateFlags.NORMAL, _rgba(STATE_COLORS["idle"]))
        term = make_terminal(argv)
        self.terms.append(term)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.pack_start(head, False, False, 0)
        box.pack_start(term, True, True, 0)
        frame.add(box)
        x, y = self.model.position(nid, default)
        self.layout.put(frame, int(x), int(y))

    # -- arrastar nó (por título) --
    def _drag_start(self, _w, e, frame):
        frame._d = (
            e.x_root,
            e.y_root,
            self.layout.child_get_property(frame, "x"),
            self.layout.child_get_property(frame, "y"),
        )

    def _drag_move(self, _w, e, frame):
        d = getattr(frame, "_d", None)
        if not d:
            return
        self.layout.move(frame, int(d[2] + (e.x_root - d[0])), int(d[3] + (e.y_root - d[1])))

    def _drag_end(self, _w, _e, frame, nid):
        if getattr(frame, "_d", None):
            self.model.set_position(
                nid,
                self.layout.child_get_property(frame, "x"),
                self.layout.child_get_property(frame, "y"),
            )
            frame._d = None

    # -- pan (arrastar fundo) --
    def _pan_start(self, _w, e):
        if e.window == self.layout.get_bin_window():
            self._pan = (
                e.x_root,
                e.y_root,
                self.scrolled.get_hadjustment().get_value(),
                self.scrolled.get_vadjustment().get_value(),
            )

    def _pan_move(self, _w, e):
        if not self._pan:
            return
        self.scrolled.get_hadjustment().set_value(self._pan[2] - (e.x_root - self._pan[0]))
        self.scrolled.get_vadjustment().set_value(self._pan[3] - (e.y_root - self._pan[1]))

    def _pan_end(self, _w, _e):
        self._pan = None

    # -- zoom --
    def _zoom(self, dz):
        self.model.set_zoom(self.model.zoom() + dz)
        self._apply_zoom()

    def _apply_zoom(self):
        z = self.model.zoom()
        for t in self.terms:
            t.set_font_scale(z)
            t.set_size_request(int(BASE_W * z), int(BASE_H * z))
        self.zlabel.set_text(f"zoom {int(z * 100)}%")

    def set_node_state(self, nid: str, state: str) -> None:
        """Recolore o título do nó conforme o estado (idle/busy/blocked/failed/done)."""
        head = self.heads.get(nid)
        if head is not None:
            head.override_background_color(
                Gtk.StateFlags.NORMAL, _rgba(STATE_COLORS.get(state, STATE_COLORS["idle"]))
            )

    def show(self):
        self.win.show_all()


def run(store: Store | None = None) -> None:  # pragma: no cover - loop GTK
    from ..bootstrap import default_home

    owns = store is None
    base = default_home()
    if owns:
        store = Store(f"{base}/maestro.db")
    # um terminal de AGENTE interativo (sandbox bwrap) por CLI instalado
    ws = Workspace(f"{base}/workspaces")
    nodes = []
    for name, profile in installed_agents().items():
        nodes.append((name, name, agent_argv(profile, str(ws.create(name)))))
    if not nodes:  # nenhum agente instalado -> um shell de exemplo
        nodes = [("term1", "shell", ["/bin/bash"])]
    CanvasWindow(CanvasModel(store), nodes).show()
    try:
        Gtk.main()
    finally:
        if owns:
            store.close()
