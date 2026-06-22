"""Canvas nativo GTK3 + VTE (V6-S2): pan/zoom + nós-terminal arrastáveis.

Gtk.Layout = plano "infinito" (pan via arrastar o fundo); nós são molduras com
título (arraste por ele) + Vte.Terminal real; zoom via font_scale + tamanho.
Posições/zoom persistidos pelo CanvasModel (Store da engine). Headless/bwrap não
muda — VTE é a camada visual/interativa.
"""

from __future__ import annotations

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gdk, GLib, Gtk, Vte  # noqa: E402

from ..engine.state.store import Store  # noqa: E402
from ..engine.workspace import Workspace  # noqa: E402
from .agents import STATE_COLORS, agent_argv, installed_agents  # noqa: E402
from .orchestrate import run_edge_handoff_in_thread, run_team_in_thread  # noqa: E402
from .state import CanvasModel, EdgeModel, cable_segments  # noqa: E402

BASE_W, BASE_H = 420, 220
# estado do envelope (passo done) -> estado visual do nó
_ST_MAP = {"DONE": "done", "BLOCKED": "blocked", "FAILED": "failed", "NEEDS_INPUT": "blocked"}


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
    def __init__(self, model, nodes, controller=None, run_team_name="coder-reviewer", edges=None):
        self.model = model
        self.controller = controller
        self.run_team_name = run_team_name
        self.edges = edges  # EdgeModel | None — cabos criados pelo usuário (V7-S2)
        self.terms: list[Vte.Terminal] = []
        self.heads: dict[str, Gtk.EventBox] = {}
        self.frames: dict[str, Gtk.Widget] = {}
        self.order: list[str] = []
        self._connect_mode = False
        self._connect_src: str | None = None
        self._edge_state: dict[tuple[str, str], str] = {}  # cor do cabo por handoff (V7-S4)
        self._active_edge: tuple[str, str] | None = None
        self.win = Gtk.Window(title="maestro console 🎼 — canvas (nativo)")
        self.win.set_default_size(1000, 600)
        self.win.connect("destroy", Gtk.main_quit)
        self.win.connect("key-press-event", self._on_key)

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
        self.layout.connect("draw", self._draw_cables)
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
        if self.edges is not None:
            self._connect_btn = Gtk.ToggleButton(label="🔌 conectar")
            self._connect_btn.connect("toggled", self._toggle_connect)
            bar.pack_start(self._connect_btn, False, False, 0)
        if self.controller is not None:
            run_b = Gtk.Button(label=f"▶ rodar time ({self.run_team_name})")
            run_b.connect("clicked", lambda _b: self._run_team())
            bar.pack_end(run_b, False, False, 0)
        if self.controller is not None and self.edges is not None:
            hb = Gtk.Button(label="▶ disparar handoff")
            hb.connect("clicked", lambda _b: self._open_handoff_dialog())
            bar.pack_end(hb, False, False, 0)
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
        frame._nid = nid
        x, y = self.model.position(nid, default)
        self.layout.put(frame, int(x), int(y))
        self.frames[nid] = frame
        self.order.append(nid)

    # -- arrastar nó (por título) --
    def _drag_start(self, _w, e, frame):
        if self._connect_mode:
            self._connect_pick(frame._nid)
            return True
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

    # -- modo conexão: criar/remover cabos por clique (V7-S2) --
    def _toggle_connect(self, btn):
        self._connect_mode = btn.get_active()
        if not self._connect_mode:
            self._cancel_connect()

    def _connect_pick(self, nid: str) -> None:
        """1º clique escolhe a origem; 2º cria (ou remove, se já existe) o cabo."""
        if self.edges is None:
            return
        if self._connect_src is None:
            self._connect_src = nid
            self.set_node_state(nid, "busy")  # realça a origem pendente
            return
        src, dst = self._connect_src, nid
        self._connect_src = None
        self.set_node_state(src, "idle")
        if src == dst:
            return
        if (src, dst) in set(self.edges.list()):
            self.edges.remove(src, dst)  # toggle: clicar de novo remove
        else:
            self.edges.add(src, dst)
        self.layout.queue_draw()

    def _cancel_connect(self) -> None:
        if self._connect_src is not None:
            self.set_node_state(self._connect_src, "idle")
            self._connect_src = None

    def _on_key(self, _w, e):
        if e.keyval == Gdk.KEY_Escape and self._connect_mode:
            self._connect_btn.set_active(False)  # untoggle -> cancela
        return False

    # -- cabos (handoffs) --
    def _draw_cables(self, _layout, cr):
        z = self.model.zoom()
        w, h = BASE_W * z, BASE_H * z
        pos = [
            (
                self.layout.child_get_property(self.frames[n], "x"),
                self.layout.child_get_property(self.frames[n], "y"),
            )
            for n in self.order
            if n in self.frames
        ]
        cr.set_source_rgb(0.34, 0.38, 0.42)
        cr.set_line_width(2)
        for x1, y1, x2, y2 in cable_segments(pos, w, h):
            cr.move_to(x1, y1)
            cr.line_to(x2, y2)
            cr.stroke()
        # cabos do usuário (V7-S2): azul por padrão; cor do estado durante handoff (V7-S4)
        if self.edges is not None:
            cr.set_line_width(2.5)
            for src, dst in self.edges.list():
                a, b = self.frames.get(src), self.frames.get(dst)
                if a is None or b is None:
                    continue
                st = self._edge_state.get((src, dst))
                if st is not None:
                    c = _rgba(STATE_COLORS.get(st, STATE_COLORS["idle"]))
                    cr.set_source_rgb(c.red, c.green, c.blue)
                else:
                    cr.set_source_rgb(0.23, 0.51, 0.96)
                ax = self.layout.child_get_property(a, "x")
                ay = self.layout.child_get_property(a, "y")
                bx = self.layout.child_get_property(b, "x")
                by = self.layout.child_get_property(b, "y")
                cr.move_to(ax + w, ay + h / 2)
                cr.line_to(bx, by + h / 2)
                cr.stroke()
        return False

    # -- rodar time da engine (headless) refletindo nas cores --
    def _run_team(self):
        team = self.controller.get_team(self.run_team_name)
        if team is None:
            return
        run_team_in_thread(self.controller, team, "Responda apenas OK.", self._on_step_ts)

    def _on_step_ts(self, sp):
        # chamado na thread da engine -> marshalla p/ a UI com segurança
        state = "busy" if sp.phase == "start" else _ST_MAP.get(sp.state, "idle")
        GLib.idle_add(self.set_node_state, sp.agent, state)
        GLib.idle_add(self.layout.queue_draw)

    # -- disparar handoff mediado por um cabo (V7-S4) --
    def _open_handoff_dialog(self):
        if self.edges is None or self.controller is None:
            return
        edges = self.edges.list()
        if not edges:
            return  # nenhum cabo p/ disparar
        dlg = Gtk.Dialog(title="Disparar handoff", transient_for=self.win, modal=True)
        dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Disparar", Gtk.ResponseType.OK)
        box = dlg.get_content_area()
        combo = Gtk.ComboBoxText()
        for s, d in edges:
            combo.append_text(f"{s} → {d}")
        combo.set_active(0)
        entry = Gtk.Entry()
        entry.set_placeholder_text("intenção para a origem…")
        box.add(Gtk.Label(label="Cabo:"))
        box.add(combo)
        box.add(Gtk.Label(label="Intenção:"))
        box.add(entry)
        dlg.show_all()
        resp = dlg.run()
        idx = combo.get_active()
        intent = entry.get_text().strip() or "Responda apenas OK."
        dlg.destroy()
        if resp == Gtk.ResponseType.OK and 0 <= idx < len(edges):
            src, dst = edges[idx]
            self._run_handoff(src, dst, intent)

    def _run_handoff(self, src: str, dst: str, intent: str) -> None:
        self._active_edge = (src, dst)
        self._edge_state[(src, dst)] = "busy"
        self.layout.queue_draw()
        run_edge_handoff_in_thread(self.controller, src, dst, intent, self._on_handoff_step_ts)

    def _on_handoff_step_ts(self, sp):
        GLib.idle_add(self._apply_handoff_step, sp)

    def _apply_handoff_step(self, sp):
        # cor do nó
        node_state = "busy" if sp.phase == "start" else _ST_MAP.get(sp.state, "idle")
        self.set_node_state(sp.agent, node_state)
        # cor do cabo conforme o progresso do handoff
        if self._active_edge is not None:
            src, dst = self._active_edge
            if sp.phase == "done":
                if sp.state == "DONE":
                    if sp.agent == dst:  # B concluiu -> cabo "done"
                        self._edge_state[(src, dst)] = "done"
                else:  # A ou B escalou -> cabo reflete o estado
                    self._edge_state[(src, dst)] = _ST_MAP.get(sp.state, "blocked")
        self.layout.queue_draw()
        return False

    def show(self):
        self.win.show_all()


def run(store: Store | None = None) -> None:  # pragma: no cover - loop GTK
    from ..bootstrap import build_controller, default_home

    base = default_home()
    controller, store = build_controller()
    # um terminal de AGENTE interativo (sandbox bwrap) por CLI instalado
    ws = Workspace(f"{base}/workspaces")
    nodes = []
    for name, profile in installed_agents().items():
        nodes.append((name, name, agent_argv(profile, str(ws.create(name)))))
    if not nodes:  # nenhum agente instalado -> um shell de exemplo
        nodes = [("term1", "shell", ["/bin/bash"])]
    CanvasWindow(CanvasModel(store), nodes, controller=controller, edges=EdgeModel(store)).show()
    try:
        Gtk.main()
    finally:
        store.close()
