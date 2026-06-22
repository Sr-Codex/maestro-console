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

from ..engine.attention import attention_items, notify  # noqa: E402
from ..engine.floor_merge import merge_floor, merge_preview  # noqa: E402
from ..engine.state.store import Store  # noqa: E402
from ..engine.workspace import Workspace  # noqa: E402
from .agents import STATE_COLORS, agent_argv, installed_agents  # noqa: E402
from .floors_ui import floor_rows, merge_text, preview_text  # noqa: E402
from .notes_ui import note_title_display  # noqa: E402
from .orchestrate import (  # noqa: E402
    run_edge_handoff_in_thread,
    run_floor_agent_in_thread,
    run_note_to_agent_in_thread,
    run_one_routine_in_thread,
    run_routines_tick_in_thread,
    run_team_in_thread,
)
from .palette import build_palette_items, fuzzy  # noqa: E402
from .routines_ui import parse_steps, routine_rows  # noqa: E402
from .state import CanvasModel, EdgeModel, cable_segments  # noqa: E402
from .themes import get_theme, theme_names  # noqa: E402

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
    def __init__(
        self,
        model,
        nodes,
        controller=None,
        run_team_name="coder-reviewer",
        edges=None,
        floors=None,
        session_manager=None,
        repo=None,
        notes=None,
        badges=None,
        routines=None,
        store=None,
    ):
        self.model = model
        self.controller = controller
        self.run_team_name = run_team_name
        self.edges = edges  # EdgeModel | None — cabos criados pelo usuário (V7-S2)
        self.floors = floors  # Floors | None — ambientes isolados (V8-S5)
        self.session_manager = session_manager  # p/ rodar agente num floor
        self.repo = repo  # path do repo de projeto (floors)
        self.notes = notes  # Notes | None — notas no canvas (V9-S3)
        self.badges = badges or {}  # agente -> cor do badge de papel (V9-S3)
        self.note_frames: dict[str, Gtk.Widget] = {}
        self.routines = routines  # Routines | None — prompts agendados (V10-S4)
        self._store = store  # Store | None — p/ attention "precisa de você" (V11-S1)
        self._notified: set = set()  # (agente, ts) já notificados no desktop
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
        if self.notes is not None:  # restaura notas salvas (V9-S3)
            for note in self.notes.list():
                self._add_note_widget(note)
        self._apply_zoom()
        self._apply_theme(self.model.terminal_theme())  # tema persistido (V11-S4)
        self._pan = None

    def _toolbar(self) -> Gtk.Widget:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for label, dz in (("−", -0.1), ("+", 0.1)):
            b = Gtk.Button(label=label)
            b.connect("clicked", lambda _b, d=dz: self._zoom(d))
            bar.pack_start(b, False, False, 0)
        self.zlabel = Gtk.Label(label="zoom 100%")
        bar.pack_start(self.zlabel, False, False, 6)
        self._attn_label = Gtk.Label(label="")  # "⚠ N" quando algo precisa de você (V11-S1)
        bar.pack_start(self._attn_label, False, False, 6)
        # seletor de tema dos terminais (V11-S4)
        self._theme_combo = Gtk.ComboBoxText()
        for tn in theme_names():
            self._theme_combo.append_text(tn)
        cur = self.model.terminal_theme()
        names = theme_names()
        self._theme_combo.set_active(names.index(cur) if cur in names else 0)
        self._theme_combo.connect("changed", self._on_theme_changed)
        bar.pack_start(self._theme_combo, False, False, 0)
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
        if self.floors is not None:
            fb = Gtk.Button(label="🧱 floors")
            fb.connect("clicked", lambda _b: self._open_floors_dialog())
            bar.pack_end(fb, False, False, 0)
        if self.notes is not None:
            nb = Gtk.Button(label="📝 nota")
            nb.connect("clicked", lambda _b: self._create_note())
            bar.pack_start(nb, False, False, 0)
        if self.routines is not None and self.controller is not None:
            rtb = Gtk.Button(label="⏰ routines")
            rtb.connect("clicked", lambda _b: self._open_routines_dialog())
            bar.pack_end(rtb, False, False, 0)
        return bar

    def _add_node(self, nid, title, argv, default):
        frame = Gtk.Frame()
        head = Gtk.EventBox()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        badge = self.badges.get(nid)
        if badge:  # tira/coluna colorida = badge do papel (V9-S3)
            sq = Gtk.Box()
            sq.set_size_request(10, -1)
            sq.override_background_color(Gtk.StateFlags.NORMAL, _rgba(badge))
            hbox.pack_start(sq, False, False, 0)
        hbox.pack_start(Gtk.Label(label=f"  {title}  "), True, True, 0)
        head.add(hbox)
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

    # -- tema dos terminais (V11-S4) --
    def _apply_theme(self, name: str) -> None:
        th = get_theme(name)
        fg, bg = _rgba(th["fg"]), _rgba(th["bg"])
        palette = [_rgba(c) for c in th["palette"]]
        for t in self.terms:
            t.set_colors(fg, bg, palette)

    def _on_theme_changed(self, combo):
        name = combo.get_active_text()
        if name:
            self.model.set_terminal_theme(name)
            self._apply_theme(name)

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
        if e.keyval == Gdk.KEY_p and (e.state & Gdk.ModifierType.CONTROL_MASK):
            self._open_palette()  # Ctrl-P (V11-S2)
            return True
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

    # -- floors no canvas (V8-S5) --
    def _open_floors_dialog(self):
        if self.floors is None:
            return
        dlg = Gtk.Dialog(title="Floors (ambientes isolados)", transient_for=self.win, modal=True)
        dlg.add_button("Fechar", Gtk.ResponseType.CLOSE)
        box = dlg.get_content_area()
        box.set_spacing(6)

        combo = Gtk.ComboBoxText()
        out = Gtk.Label(label="")
        out.set_xalign(0)
        out.set_selectable(True)

        def refresh():
            combo.remove_all()
            rows = floor_rows(self.floors)
            for r in rows:
                combo.append_text(r["name"])
            if rows:
                combo.set_active(0)

        def selected():
            name = combo.get_active_text()
            return self.floors.get(name) if name else None

        refresh()
        box.add(Gtk.Label(label="Floor:"))
        box.add(combo)

        # criar
        crow = Gtk.Box(spacing=4)
        new_entry = Gtk.Entry()
        new_entry.set_placeholder_text("nome do novo floor")
        crow.pack_start(new_entry, True, True, 0)

        def do_create(_b):
            name = new_entry.get_text().strip()
            if not name:
                return
            try:
                self.floors.create(name)
                new_entry.set_text("")
                refresh()
                out.set_text(f"floor {name!r} criado")
            except Exception as e:  # FloorError etc.
                out.set_text(f"erro: {e}")

        cbtn = Gtk.Button(label="criar")
        cbtn.connect("clicked", do_create)
        crow.pack_start(cbtn, False, False, 0)
        box.add(crow)

        # preview / integrar / remover
        def do_preview(_b):
            f = selected()
            if f is not None:
                out.set_text(preview_text(merge_preview(self.repo, f)))

        def do_merge(_b):
            f = selected()
            if f is not None:
                out.set_text(merge_text(merge_floor(self.repo, f)))
                refresh()

        def do_rm(_b):
            f = selected()
            if f is not None:
                self.floors.remove(f.name)
                refresh()
                out.set_text(f"floor {f.name!r} removido")

        arow = Gtk.Box(spacing=4)
        for label, cb in (("preview", do_preview), ("integrar", do_merge), ("remover", do_rm)):
            b = Gtk.Button(label=label)
            b.connect("clicked", cb)
            arow.pack_start(b, False, False, 0)
        box.add(arow)

        # rodar agente num floor
        if self.session_manager is not None:
            agents = installed_agents()
            rrow = Gtk.Box(spacing=4)
            acombo = Gtk.ComboBoxText()
            for name in agents:
                acombo.append_text(name)
            if agents:
                acombo.set_active(0)
            pentry = Gtk.Entry()
            pentry.set_placeholder_text("prompt p/ o agente")

            def do_run(_b):
                f = selected()
                agent = acombo.get_active_text()
                if f is None or not agent:
                    return
                prompt = pentry.get_text().strip() or "Responda apenas OK."
                out.set_text(f"rodando {agent} no floor {f.name}…")

                def done(res, committed):
                    GLib.idle_add(
                        out.set_text,
                        f"{agent}: {res.status}; commit={'sim' if committed else '(nada)'}",
                    )

                run_floor_agent_in_thread(
                    self.session_manager, agents[agent], agent, prompt, f, self.repo, done
                )

            rrow.pack_start(acombo, False, False, 0)
            rrow.pack_start(pentry, True, True, 0)
            rb = Gtk.Button(label="rodar")
            rb.connect("clicked", do_run)
            rrow.pack_start(rb, False, False, 0)
            box.add(rrow)

        box.add(out)
        dlg.show_all()
        dlg.run()
        dlg.destroy()

    # -- sticky notes no canvas (V9-S3) --
    def _create_note(self):
        if self.notes is None:
            return
        n = len(self.note_frames)
        note = self.notes.create("Nota", "", x=120 + n * 40, y=320 + n * 40)
        self._add_note_widget(note)
        self.win.show_all()

    def _add_note_widget(self, note):
        frame = Gtk.Frame()
        frame._note_id = note.id
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # barra de título (arraste + edição do título)
        head = Gtk.EventBox()
        head.override_background_color(Gtk.StateFlags.NORMAL, _rgba("#fde68a"))  # amarelo nota
        title = Gtk.Entry()
        title.set_text(note_title_display(note) if note.title else "Nota")
        title.set_has_frame(False)
        head.add(title)
        head.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        head.connect("button-press-event", self._note_drag_start, frame)
        head.connect("motion-notify-event", self._note_drag_move, frame)
        head.connect("button-release-event", self._note_drag_end, frame)
        # corpo (markdown editável)
        body = Gtk.TextView()
        body.set_wrap_mode(Gtk.WrapMode.WORD)
        body.get_buffer().set_text(note.body)
        body.set_size_request(200, 110)
        # salvar ao perder foco
        title.connect("focus-out-event", lambda *_: self._save_note(frame))
        body.connect("focus-out-event", lambda *_: self._save_note(frame))
        frame._title_entry = title
        frame._body_view = body
        box.pack_start(head, False, False, 0)
        box.pack_start(body, True, True, 0)
        # agent-to-note: rodar um agente com a nota (V9-S4)
        if self.controller is not None:
            agents = installed_agents()
            rrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            acombo = Gtk.ComboBoxText()
            for name in agents:
                acombo.append_text(name)
            if agents:
                acombo.set_active(0)
            rb = Gtk.Button(label="▶ rodar")
            rb.connect("clicked", lambda _b, fr=frame, c=acombo: self._run_note(fr, c))
            rrow.pack_start(acombo, True, True, 0)
            rrow.pack_start(rb, False, False, 0)
            box.pack_start(rrow, False, False, 0)
        frame.add(box)
        self.layout.put(frame, int(note.x), int(note.y))
        self.note_frames[note.id] = frame

    def _save_note(self, frame):
        if self.notes is None:
            return
        note = self.notes.get(frame._note_id)
        if note is None:
            return
        buf = frame._body_view.get_buffer()
        note.title = frame._title_entry.get_text().strip()
        note.body = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        note.x = self.layout.child_get_property(frame, "x")
        note.y = self.layout.child_get_property(frame, "y")
        self.notes.save(note)
        return False

    def _note_drag_start(self, _w, e, frame):
        frame._nd = (
            e.x_root,
            e.y_root,
            self.layout.child_get_property(frame, "x"),
            self.layout.child_get_property(frame, "y"),
        )

    def _note_drag_move(self, _w, e, frame):
        d = getattr(frame, "_nd", None)
        if not d:
            return
        self.layout.move(frame, int(d[2] + (e.x_root - d[0])), int(d[3] + (e.y_root - d[1])))

    def _note_drag_end(self, _w, _e, frame):
        if getattr(frame, "_nd", None):
            frame._nd = None
            self._save_note(frame)  # persiste título/corpo/posição

    def _run_note(self, frame, acombo):
        """agent-to-note: roda o agente escolhido com a nota; resposta volta à nota."""
        if self.controller is None or self.notes is None:
            return
        agent = acombo.get_active_text()
        if not agent:
            return
        self._save_note(frame)  # garante que edições recentes entram no prompt
        note = self.notes.get(frame._note_id)
        if note is None:
            return
        frame._title_entry.set_text(f"{note_title_display(note)} · rodando {agent}…")

        def done(env, updated, updated_note):
            def apply():
                fresh = self.notes.get(frame._note_id)
                if fresh is not None:
                    frame._body_view.get_buffer().set_text(fresh.body)
                    frame._title_entry.set_text(note_title_display(fresh))
                return False

            GLib.idle_add(apply)

        run_note_to_agent_in_thread(self.controller, note, agent, self.notes, done)

    # -- routines no canvas (V10-S4) --
    def _routines_tick(self):
        """Tick in-app: dispara as routines vencidas (enquanto o canvas está aberto)."""
        if self.routines is not None and self.controller is not None:
            run_routines_tick_in_thread(self.controller, self.routines)
        return True  # repete

    def _open_routines_dialog(self):
        if self.routines is None or self.controller is None:
            return
        dlg = Gtk.Dialog(title="Routines (prompts agendados)", transient_for=self.win, modal=True)
        dlg.add_button("Fechar", Gtk.ResponseType.CLOSE)
        box = dlg.get_content_area()
        box.set_spacing(6)

        combo = Gtk.ComboBoxText()
        out = Gtk.Label(label="")
        out.set_xalign(0)
        out.set_selectable(True)

        def refresh():
            combo.remove_all()
            for row in routine_rows(self.routines):
                combo.append_text(row["label"])
            if self.routines.list():
                combo.set_active(0)

        def selected():
            i = combo.get_active()
            rs = self.routines.list()
            return rs[i] if 0 <= i < len(rs) else None

        refresh()
        box.add(Gtk.Label(label="Routine:"))
        box.add(combo)

        # criar
        agents = installed_agents()
        crow = Gtk.Box(spacing=4)
        name_e = Gtk.Entry()
        name_e.set_placeholder_text("nome")
        acombo = Gtk.ComboBoxText()
        for a in agents:
            acombo.append_text(a)
        if agents:
            acombo.set_active(0)
        prompt_e = Gtk.Entry()
        prompt_e.set_placeholder_text("prompt (use ' && ' p/ passos)")
        int_e = Gtk.Entry()
        int_e.set_text("600")
        int_e.set_width_chars(6)
        crow.pack_start(name_e, False, False, 0)
        crow.pack_start(acombo, False, False, 0)
        crow.pack_start(prompt_e, True, True, 0)
        crow.pack_start(int_e, False, False, 0)

        def do_create(_b):
            name = name_e.get_text().strip()
            agent = acombo.get_active_text()
            steps = parse_steps(prompt_e.get_text())
            if not name or not agent or not steps:
                out.set_text("preencha nome, agente e prompt")
                return
            try:
                interval = float(int_e.get_text())
            except ValueError:
                interval = 600.0
            self.routines.create(name, agent, steps, interval)
            name_e.set_text("")
            prompt_e.set_text("")
            refresh()
            out.set_text(f"routine {name!r} criada")

        cbtn = Gtk.Button(label="criar")
        cbtn.connect("clicked", do_create)
        crow.pack_start(cbtn, False, False, 0)
        box.add(crow)

        # ações
        def do_toggle(_b):
            r = selected()
            if r is not None:
                self.routines.set_enabled(r.id, not r.enabled)
                refresh()
                out.set_text(f"{r.name}: {'pausada' if r.enabled else 'habilitada'}")

        def do_run(_b):
            r = selected()
            if r is None:
                return
            out.set_text(f"rodando {r.name}…")

            def done(run):
                GLib.idle_add(refresh)
                status = "OK" if run.ok else f"parou no passo {run.stopped_at}"
                GLib.idle_add(out.set_text, f"{r.name}: {status}")

            run_one_routine_in_thread(self.controller, r, self.routines, done)

        def do_rm(_b):
            r = selected()
            if r is not None:
                self.routines.delete(r.id)
                refresh()
                out.set_text(f"{r.name}: removida")

        arow = Gtk.Box(spacing=4)
        for label, cb in (("on/off", do_toggle), ("▶ rodar agora", do_run), ("remover", do_rm)):
            b = Gtk.Button(label=label)
            b.connect("clicked", cb)
            arow.pack_start(b, False, False, 0)
        box.add(arow)
        box.add(out)
        dlg.show_all()
        dlg.run()
        dlg.destroy()

    # -- command palette (Ctrl-P) (V11-S2) --
    def _palette_items(self):
        agents = list(self.frames.keys())
        teams = self.controller.list_teams() if self.controller is not None else []
        floors = self.floors.list() if self.floors is not None else []
        notes = self.notes.list() if self.notes is not None else []
        routines = self.routines.list() if self.routines is not None else []
        return build_palette_items(
            agents=agents, teams=teams, floors=floors, notes=notes, routines=routines
        )

    def _center_on(self, frame):
        x = self.layout.child_get_property(frame, "x")
        y = self.layout.child_get_property(frame, "y")
        ha, va = self.scrolled.get_hadjustment(), self.scrolled.get_vadjustment()
        ha.set_value(max(0, x - ha.get_page_size() / 2))
        va.set_value(max(0, y - va.get_page_size() / 2))

    def _palette_act(self, item):
        if item.kind == "agent":
            fr = self.frames.get(item.ref)
            if fr is not None:
                self._center_on(fr)
        elif item.kind == "note":
            fr = self.note_frames.get(item.ref)
            if fr is not None:
                self._center_on(fr)
        elif item.kind == "floor":
            self._open_floors_dialog()
        elif item.kind == "routine":
            self._open_routines_dialog()
        # team: sem ação dedicada (informativo)

    def _open_palette(self):
        items = self._palette_items()
        dlg = Gtk.Dialog(title="Ir para… (Ctrl-P)", transient_for=self.win, modal=True)
        dlg.set_default_size(420, 320)
        box = dlg.get_content_area()
        entry = Gtk.Entry()
        entry.set_placeholder_text("buscar agente/team/floor/nota/routine…")
        box.add(entry)
        listbox = Gtk.ListBox()
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.add(listbox)
        box.add(scroller)

        rows: list = []  # PaletteItem por linha (índice = posição)

        def rebuild():
            for child in listbox.get_children():
                listbox.remove(child)
            rows.clear()
            for it in fuzzy(entry.get_text(), items):
                row = Gtk.ListBoxRow()
                row.add(Gtk.Label(label=it.label, xalign=0))
                listbox.add(row)
                rows.append(it)
            listbox.show_all()
            first = listbox.get_row_at_index(0)
            if first is not None:
                listbox.select_row(first)

        def activate():
            row = listbox.get_selected_row() or listbox.get_row_at_index(0)
            if row is not None and 0 <= row.get_index() < len(rows):
                item = rows[row.get_index()]
                dlg.destroy()
                self._palette_act(item)
                return True
            dlg.destroy()
            return False

        entry.connect("changed", lambda _e: rebuild())
        entry.connect("activate", lambda _e: activate())
        listbox.connect("row-activated", lambda _lb, _r: activate())
        rebuild()
        dlg.show_all()
        entry.grab_focus()
        dlg.run()

    # -- attention: "o que precisa de você" (V11-S1) --
    def _refresh_attention(self):
        if self._store is None:
            return True
        items = attention_items(self._store)
        current: set = set()
        for it in items:
            self.set_node_state(it.agent, _ST_MAP.get(it.state, "blocked"))  # realça o nó
            key = (it.agent, it.state)
            current.add(key)
            if key not in self._notified:  # notifica só o que é novo
                notify(f"maestro: {it.agent} precisa de você", it.state)
        self._notified = current  # poda p/ os atuais: sem leak; re-notifica se voltar
        self._attn_label.set_text(f"⚠ {len(items)}" if items else "")
        return True  # repete

    def show(self):
        self.win.show_all()


def run(store: Store | None = None) -> None:  # pragma: no cover - loop GTK
    from ..bootstrap import build_controller, default_home
    from ..engine.notes import Notes
    from ..engine.roles import agent_badges
    from ..engine.routines import Routines
    from ..engine.session import SessionManager
    from .floors_ui import resolve_floors

    base = default_home()
    controller, store = build_controller()
    # um terminal de AGENTE interativo (sandbox bwrap) por CLI instalado
    ws = Workspace(f"{base}/workspaces")
    nodes = []
    for name, profile in installed_agents().items():
        nodes.append((name, name, agent_argv(profile, str(ws.create(name)))))
    if not nodes:  # nenhum agente instalado -> um shell de exemplo
        nodes = [("term1", "shell", ["/bin/bash"])]
    # floors: só se o cwd (ou MAESTRO_PROJECT) for um repo git
    floors = resolve_floors(store, f"{base}/floors")
    # badges de papel a partir do team default
    badges = agent_badges(controller.get_team("coder-reviewer"))
    win = CanvasWindow(
        CanvasModel(store),
        nodes,
        controller=controller,
        edges=EdgeModel(store),
        floors=floors,
        session_manager=SessionManager(store) if floors is not None else None,
        repo=str(floors.repo) if floors is not None else None,
        notes=Notes(store),
        badges=badges,
        routines=Routines(store),
        store=store,
    )
    win.show()
    # tick in-app do scheduler: dispara as routines vencidas enquanto aberto (V10-S4)
    GLib.timeout_add_seconds(30, win._routines_tick)
    # attention: realça/notifica o que precisa de você (V11-S1)
    GLib.timeout_add_seconds(10, win._refresh_attention)
    win._refresh_attention()
    try:
        Gtk.main()
    finally:
        store.close()
