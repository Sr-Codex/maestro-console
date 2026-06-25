"""Canvas nativo GTK4 + VTE-3.91: plano infinito com zoom REAL (transform).

Diferença-chave vs o antigo GTK3: o zoom é uma *transform de escala* no plano
(`Gtk.Fixed.set_child_transform`), não `set_font_scale`/`set_size_request`. Assim
os terminais escalam **visualmente** junto com o canvas SEM mexer na alocação do
widget — ou seja, o grid (colunas×linhas) e o PTY do agente ficam intactos. Só a
"tela infinita" zooma; o terminal em si não é afetado.

Posições/zoom persistidos pelo CanvasModel (Store da engine). Coordenadas-base são
independentes do zoom: display = base * zoom (helpers `to_display`/`to_base`).
"""

from __future__ import annotations

import logging

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
from gi.repository import Gdk, Gio, GLib, Graphene, Gsk, Gtk, Vte  # noqa: E402

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
from .state import CanvasModel, EdgeModel, cable_segments, to_display  # noqa: E402
from .themes import get_theme, theme_names  # noqa: E402
from .toolbar import action_menu_items  # noqa: E402

BASE_W, BASE_H = 420, 220
# estado do envelope (passo done) -> estado visual do nó
_ST_MAP = {"DONE": "done", "BLOCKED": "blocked", "FAILED": "failed", "NEEDS_INPUT": "blocked"}
_log = logging.getLogger(__name__)


def _rgba(hex_color: str) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(hex_color)
    return c


def _plane_xform(px: float, py: float, z: float) -> Gsk.Transform:
    """Transform ÚNICO do plano: posiciona em (px,py) e escala por z.

    Em Gtk.Fixed a posição (put/move) e o set_child_transform compartilham o
    MESMO slot de transform do filho — a posição é só uma translação. Se a gente
    setar um scale puro depois do put/move, a translação é apagada e o nó volta
    pra origem (0,0). Por isso posição e zoom têm que vir juntos no mesmo transform.
    """
    return Gsk.Transform().translate(Graphene.Point().init(px, py)).scale(z, z)


def _on_spawn_done(terminal, pid, error, argv):
    """Vte.TerminalSpawnAsyncCallback (VTE 3.91): loga/sinaliza falha de spawn.

    Sem isto (callback=None), um spawn que falha — agente fora do PATH, bwrap
    ausente, argv inválido — deixava o nó em branco e mudo. Aqui registra no log e
    escreve um aviso visível no próprio terminal.
    """
    if error is not None or pid == -1:
        msg = error.message if error is not None else "spawn falhou (pid=-1)"
        _log.error("falha ao iniciar terminal do nó (argv=%r): %s", argv, msg)
        if terminal is not None:
            terminal.feed(f"\r\n[maestro] falha ao iniciar agente: {msg}\r\n".encode())


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
        _on_spawn_done,
        argv,
    )
    return term


class _Plane(Gtk.Fixed):
    """Gtk.Fixed que desenha os cabos (handoffs) atrás dos nós, no snapshot."""

    __gtype_name__ = "MaestroPlane"

    def __init__(self):
        super().__init__()
        self._owner: CanvasWindow | None = None

    def do_snapshot(self, snapshot):  # pragma: no cover - precisa de GTK
        o = self._owner
        if o is not None:
            w, h = self.get_width(), self.get_height()
            if w > 0 and h > 0:
                cr = snapshot.append_cairo(Graphene.Rect().init(0, 0, w, h))
                o._draw_cables_cr(cr)
        Gtk.Fixed.do_snapshot(self, snapshot)


class CanvasWindow:
    def __init__(
        self,
        app,
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
        # coords-base independentes do zoom; display = base * zoom (P5)
        self._base_pos: dict[str, tuple[float, float]] = {}
        self._note_base: dict[str, tuple[float, float]] = {}
        self.routines = routines  # Routines | None — prompts agendados (V10-S4)
        self._store = store  # Store | None — p/ attention "precisa de você" (V11-S1)
        self._notified: set = set()  # (agente, ts) já notificados no desktop
        self.terms: list[Vte.Terminal] = []
        self.heads: dict[str, Gtk.Widget] = {}
        self.frames: dict[str, Gtk.Widget] = {}
        self.order: list[str] = []
        self._connect_mode = False
        self._connect_src: str | None = None
        self._edge_state: dict[tuple[str, str], str] = {}  # cor do cabo por handoff (V7-S4)
        self._active_edge: tuple[str, str] | None = None
        self._pan: tuple[float, float] | None = None

        self._install_css()
        self.win = Gtk.ApplicationWindow(application=app)
        self.win.set_title("maestro console 🎼 — canvas (GTK4)")
        self.win.set_default_size(1000, 600)
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key)
        self.win.add_controller(key)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.append(self._toolbar())
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_hexpand(True)
        self.scrolled.set_vexpand(True)
        self.plane = _Plane()
        self.plane._owner = self
        self._plane_size = (5000, 4000)  # cresce dinamicamente (_resize_plane)
        self.plane.set_size_request(*self._plane_size)
        # pan: arrastar o fundo do plano (ignora se cair sobre um nó/nota)
        pan = Gtk.GestureDrag()
        pan.connect("drag-begin", self._pan_begin)
        pan.connect("drag-update", self._pan_update)
        self.plane.add_controller(pan)
        self.scrolled.set_child(self.plane)
        root.append(self.scrolled)
        self.win.set_child(root)

        for i, (nid, title, argv) in enumerate(nodes):
            self._add_node(nid, title, argv, default=(60 + i * 460, 60))
        if self.notes is not None:  # restaura notas salvas (V9-S3)
            for note in self.notes.list():
                self._add_note_widget(note)
        self._apply_zoom()
        self._apply_theme(self.model.terminal_theme())  # tema persistido (V11-S4)

    # -- CSS: cores de estado (substitui override_background_color do GTK3) --
    def _install_css(self) -> None:
        rules = [".nodehead { padding: 1px 6px; }", ".notehead { background-color: #fde68a; }"]
        for st, hexc in STATE_COLORS.items():
            rules.append(f".st-{st} {{ background-color: {hexc}; }}")
        provider = Gtk.CssProvider()
        data = "\n".join(rules)
        if hasattr(provider, "load_from_string"):
            provider.load_from_string(data)
        else:  # GTK4 < 4.12
            provider.load_from_data(data.encode())
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def _toolbar(self) -> Gtk.Widget:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar.set_margin_top(2)
        bar.set_margin_bottom(2)
        bar.set_margin_start(4)
        bar.set_margin_end(4)
        # -- controles de vista (esquerda) --
        for label, dz, tip in (("−", -0.1, "diminuir zoom"), ("+", 0.1, "aumentar zoom")):
            b = Gtk.Button(label=label)
            b.set_tooltip_text(tip)
            b.connect("clicked", lambda _b, d=dz: self._zoom(d))
            bar.append(b)
        self.zlabel = Gtk.Label(label="zoom 100%")
        bar.append(self.zlabel)
        self._attn_label = Gtk.Label(label="")  # "⚠ N" quando algo precisa de você (V11-S1)
        self._attn_label.set_tooltip_text("itens que precisam de você")
        bar.append(self._attn_label)
        self._theme_combo = Gtk.ComboBoxText()  # tema dos terminais (V11-S4)
        self._theme_combo.set_tooltip_text("tema dos terminais")
        for tn in theme_names():
            self._theme_combo.append_text(tn)
        cur = self.model.terminal_theme()
        names = theme_names()
        self._theme_combo.set_active(names.index(cur) if cur in names else 0)
        self._theme_combo.connect("changed", self._on_theme_changed)
        bar.append(self._theme_combo)
        if self.edges is not None:  # modo conexão (persistente) direto na barra
            self._connect_btn = Gtk.ToggleButton(label="🔌 conectar")
            self._connect_btn.set_tooltip_text("ligar agentes por cabo (clique A, depois B)")
            self._connect_btn.connect("toggled", self._toggle_connect)
            bar.append(self._connect_btn)
        # espaçador empurra o resto p/ a direita
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        bar.append(spacer)
        # dica: Ctrl-P abre a busca rápida (palette)
        hint = Gtk.Label(label="Ctrl-P: ir para…")
        hint.set_tooltip_text("busca rápida de agentes/teams/floors/notas/routines")
        bar.append(hint)
        # -- comandos agrupados num menu (popover): descongestiona a barra (P3) --
        spec = action_menu_items(
            has_controller=self.controller is not None,
            has_edges=self.edges is not None,
            has_notes=self.notes is not None,
            has_floors=self.floors is not None,
            has_routines=self.routines is not None,
            team_name=self.run_team_name,
        )
        cbmap = {
            "run_team": self._run_team,
            "handoff": self._open_handoff_dialog,
            "note": self._create_note,
            "floors": self._open_floors_dialog,
            "routines": self._open_routines_dialog,
        }
        if spec:
            mb = Gtk.MenuButton(label="☰ ações")
            pop = Gtk.Popover()
            vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            for label, key in spec:
                b = Gtk.Button(label=label)
                b.set_has_frame(False)
                b.connect("clicked", lambda _b, k=key, p=pop: (p.popdown(), cbmap[k]()))
                vb.append(b)
            pop.set_child(vb)
            mb.set_popover(pop)
            bar.append(mb)
        return bar

    def _add_node(self, nid, title, argv, default):
        frame = Gtk.Frame()
        frame._nid = nid
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        head.add_css_class("nodehead")
        head.add_css_class("st-idle")
        badge = self.badges.get(nid)
        if badge:  # tira colorida = badge do papel (V9-S3) — DrawingArea c/ cor arbitrária
            sq = Gtk.DrawingArea()
            sq.set_content_width(10)
            col = _rgba(badge)

            def _draw_badge(_area, cr, _w, _h, c=col):
                cr.set_source_rgba(c.red, c.green, c.blue, 1.0)
                cr.paint()

            sq.set_draw_func(_draw_badge)
            head.append(sq)
        lbl = Gtk.Label(label=f"  {title}  ")
        lbl.set_hexpand(True)
        head.append(lbl)
        # arrastar o nó pelo título (ou, em modo conexão, escolher origem/destino)
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._node_drag_begin, frame)
        drag.connect("drag-update", self._node_drag_update, frame)
        drag.connect("drag-end", self._node_drag_end, frame, nid)
        head.add_controller(drag)
        self.heads[nid] = head
        term = make_terminal(argv)
        term.set_hexpand(True)
        term.set_vexpand(True)
        term.set_size_request(BASE_W, BASE_H)  # tamanho NATURAL; o zoom é por transform
        self.terms.append(term)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(head)
        box.append(term)
        frame.set_child(box)
        bx, by = self.model.position(nid, default)
        self._base_pos[nid] = (bx, by)
        self.plane.put(frame, 0, 0)  # posição real vem no transform (_place)
        self._place(frame, (bx, by), self.model.zoom())
        self.frames[nid] = frame
        self.order.append(nid)

    def _place(self, child, base, z) -> None:
        """Posiciona+escala o child com UM transform único (ver _plane_xform)."""
        px, py = to_display(base, z)
        self.plane.set_child_transform(child, _plane_xform(px, py, z))

    # -- arrastar nó (por título) via GestureDrag --
    def _node_drag_begin(self, _g, _x, _y, frame):
        if self._connect_mode:
            frame._connecting = True
            self._connect_pick(frame._nid)
            return
        frame._connecting = False
        frame._origin_base = self._base_pos.get(frame._nid, (0.0, 0.0))

    def _node_drag_update(self, _g, off_x, off_y, frame):
        if getattr(frame, "_connecting", False):
            return
        o = getattr(frame, "_origin_base", None)
        if o is None:
            return
        # offset vem em coords do nó (escaladas por z); base-delta = (off*z)/z = off
        nb = (o[0] + off_x, o[1] + off_y)
        self._base_pos[frame._nid] = nb
        self._place(frame, nb, self.model.zoom())
        self._resize_plane()
        self.plane.queue_draw()

    def _node_drag_end(self, _g, _ox, _oy, frame, nid):
        if getattr(frame, "_connecting", False):
            frame._connecting = False
            return
        if getattr(frame, "_origin_base", None) is None:
            return
        frame._origin_base = None
        bx, by = self._base_pos.get(nid, (0.0, 0.0))
        self.model.set_position(nid, bx, by)  # persiste em coords-base
        self.plane.queue_draw()

    # -- pan (arrastar fundo) --
    def _pan_begin(self, gesture, x, y):
        picked = self.plane.pick(x, y, Gtk.PickFlags.DEFAULT)
        w = picked
        while w is not None and w is not self.plane:  # caiu sobre um nó/nota? não faz pan
            if getattr(w, "_nid", None) or getattr(w, "_note_id", None):
                self._pan = None
                gesture.set_state(Gtk.EventSequenceState.DENIED)
                return
            w = w.get_parent()
        self._pan = (
            self.scrolled.get_hadjustment().get_value(),
            self.scrolled.get_vadjustment().get_value(),
        )

    def _pan_update(self, _g, off_x, off_y):
        if self._pan is None:
            return
        self.scrolled.get_hadjustment().set_value(self._pan[0] - off_x)
        self.scrolled.get_vadjustment().set_value(self._pan[1] - off_y)

    # -- zoom: escala o PLANO (posição + transform); terminal mantém alocação/PTY --
    def _zoom(self, dz):
        self.model.set_zoom(self.model.zoom() + dz)
        self._apply_zoom()

    def _resize_plane(self) -> None:
        """Cresce o plano p/ caber todos os nós/notas no zoom atual.

        Com extensão fixa, arrastar um nó pra longe e dar zoom o jogava pra fora da
        área rolável (inalcançável). Só cresce; nunca encolhe abaixo do piso inicial.
        Compara com o tamanho atual p/ evitar relayout à toa durante o arrasto.
        """
        z = self.model.zoom()
        bases = list(self._base_pos.values()) + list(self._note_base.values())
        max_bx = max((b[0] for b in bases), default=0.0)
        max_by = max((b[1] for b in bases), default=0.0)
        need_w = max(5000, int(max_bx * z + BASE_W * z + 400))
        need_h = max(4000, int(max_by * z + BASE_H * z + 400))
        if (need_w, need_h) != self._plane_size:
            self._plane_size = (need_w, need_h)
            self.plane.set_size_request(need_w, need_h)

    def _apply_zoom(self):
        z = self.model.zoom()
        self._resize_plane()
        for nid, frame in self.frames.items():
            self._place(frame, self._base_pos.get(nid, (0.0, 0.0)), z)
        for note_id, frame in self.note_frames.items():
            self._place(frame, self._note_base.get(note_id, (0.0, 0.0)), z)
        self.zlabel.set_text(f"zoom {int(z * 100)}%")
        self.plane.queue_draw()

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
        if head is None:
            return
        for st in STATE_COLORS:
            head.remove_css_class(f"st-{st}")
        head.add_css_class(f"st-{state if state in STATE_COLORS else 'idle'}")

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
        self.plane.queue_draw()

    def _cancel_connect(self) -> None:
        if self._connect_src is not None:
            self.set_node_state(self._connect_src, "idle")
            self._connect_src = None

    def _on_key(self, _c, keyval, _keycode, state):
        if keyval == Gdk.KEY_Escape and self._connect_mode:
            self._connect_btn.set_active(False)  # untoggle -> cancela
            return False
        if keyval == Gdk.KEY_p and (state & Gdk.ModifierType.CONTROL_MASK):
            self._open_palette()  # Ctrl-P (V11-S2)
            return True
        return False

    # -- cabos (handoffs): desenhados no snapshot do _Plane --
    def _draw_cables_cr(self, cr):
        z = self.model.zoom()
        w, h = BASE_W * z, BASE_H * z

        def disp(nid):  # canto sup-esq no plano = base * zoom (mesma fonte do _place)
            return to_display(self._base_pos.get(nid, (0.0, 0.0)), z)

        pos = [disp(n) for n in self.order if self.frames.get(n) is not None]
        cr.set_source_rgb(0.34, 0.38, 0.42)
        cr.set_line_width(2)
        for x1, y1, x2, y2 in cable_segments(pos, w, h):
            cr.move_to(x1, y1)
            cr.line_to(x2, y2)
            cr.stroke()
        # cabos do usuário (V7-S2): azul; cor do estado durante o handoff (V7-S4)
        if self.edges is not None:
            cr.set_line_width(2.5)
            for src, dst in self.edges.list():
                if src not in self.frames or dst not in self.frames:
                    continue
                st = self._edge_state.get((src, dst))
                if st is not None:
                    c = _rgba(STATE_COLORS.get(st, STATE_COLORS["idle"]))
                    cr.set_source_rgb(c.red, c.green, c.blue)
                else:
                    cr.set_source_rgb(0.23, 0.51, 0.96)
                ax, ay = disp(src)
                bx, by = disp(dst)
                cr.move_to(ax + w, ay + h / 2)
                cr.line_to(bx, by + h / 2)
                cr.stroke()

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
        GLib.idle_add(self.plane.queue_draw)

    # -- disparar handoff mediado por um cabo (V7-S4) --
    def _open_handoff_dialog(self):
        if self.edges is None or self.controller is None:
            return
        edges = self.edges.list()
        if not edges:
            return  # nenhum cabo p/ disparar
        dlg, box = self._dialog("Disparar handoff")
        combo = Gtk.ComboBoxText()
        for s, d in edges:
            combo.append_text(f"{s} → {d}")
        combo.set_active(0)
        entry = Gtk.Entry()
        entry.set_placeholder_text("intenção para a origem…")
        box.append(Gtk.Label(label="Cabo:"))
        box.append(combo)
        box.append(Gtk.Label(label="Intenção:"))
        box.append(entry)
        brow = Gtk.Box(spacing=6)

        def fire(_b):
            idx = combo.get_active()
            intent = entry.get_text().strip() or "Responda apenas OK."
            dlg.destroy()
            if 0 <= idx < len(edges):
                src, dst = edges[idx]
                self._run_handoff(src, dst, intent)

        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda _b: dlg.destroy())
        ok = Gtk.Button(label="Disparar")
        ok.connect("clicked", fire)
        brow.append(cancel)
        brow.append(ok)
        box.append(brow)
        dlg.present()

    def _run_handoff(self, src: str, dst: str, intent: str) -> None:
        self._active_edge = (src, dst)
        self._edge_state[(src, dst)] = "busy"
        self.plane.queue_draw()
        run_edge_handoff_in_thread(self.controller, src, dst, intent, self._on_handoff_step_ts)

    def _on_handoff_step_ts(self, sp):
        GLib.idle_add(self._apply_handoff_step, sp)

    def _apply_handoff_step(self, sp):
        node_state = "busy" if sp.phase == "start" else _ST_MAP.get(sp.state, "idle")
        self.set_node_state(sp.agent, node_state)
        if self._active_edge is not None:
            src, dst = self._active_edge
            if sp.phase == "done":
                if sp.state == "DONE":
                    if sp.agent == dst:  # B concluiu -> cabo "done"
                        self._edge_state[(src, dst)] = "done"
                else:  # A ou B escalou -> cabo reflete o estado
                    self._edge_state[(src, dst)] = _ST_MAP.get(sp.state, "blocked")
        self.plane.queue_draw()
        return False

    # -- helper de diálogo (GTK4: sem Dialog.run; janela modal simples) --
    def _dialog(self, title: str):
        win = Gtk.Window(title=title)
        win.set_transient_for(self.win)
        win.set_modal(True)
        win.set_default_size(420, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        win.set_child(box)
        # Esc fecha o diálogo (GTK4 não dá isso de graça como o antigo Dialog.run).
        # Só afeta janelas modais (paleta/floors/routines); não rouba o Esc do terminal.
        esc = Gtk.EventControllerKey()
        esc.connect(
            "key-pressed",
            lambda _c, kv, _kc, _st, w=win: (w.destroy() or True)
            if kv == Gdk.KEY_Escape
            else False,
        )
        win.add_controller(esc)
        return win, box

    # -- floors no canvas (V8-S5) --
    def _open_floors_dialog(self):
        if self.floors is None:
            return
        dlg, box = self._dialog("Floors (ambientes isolados)")

        combo = Gtk.ComboBoxText()
        out = Gtk.Label(label="")
        out.set_xalign(0)
        out.set_selectable(True)
        out.set_wrap(True)

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
        box.append(Gtk.Label(label="Floor:"))
        box.append(combo)

        # criar
        crow = Gtk.Box(spacing=4)
        new_entry = Gtk.Entry()
        new_entry.set_placeholder_text("nome do novo floor")
        new_entry.set_hexpand(True)
        crow.append(new_entry)

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
        crow.append(cbtn)
        box.append(crow)

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
            arow.append(b)
        box.append(arow)

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
            pentry.set_hexpand(True)

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

            rrow.append(acombo)
            rrow.append(pentry)
            rb = Gtk.Button(label="rodar")
            rb.connect("clicked", do_run)
            rrow.append(rb)
            box.append(rrow)

        box.append(out)
        close = Gtk.Button(label="Fechar")
        close.connect("clicked", lambda _b: dlg.destroy())
        box.append(close)
        dlg.present()

    # -- sticky notes no canvas (V9-S3) --
    def _create_note(self):
        if self.notes is None:
            return
        n = len(self.note_frames)
        note = self.notes.create("Nota", "", x=120 + n * 40, y=320 + n * 40)
        self._add_note_widget(note)

    def _add_note_widget(self, note):
        frame = Gtk.Frame()
        frame._note_id = note.id
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # barra de título (arraste pelo "≡" + edição do título)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        head.add_css_class("notehead")
        grip = Gtk.Label(label=" ≡ ")
        head.append(grip)
        title = Gtk.Entry()
        title.set_text(note_title_display(note) if note.title else "Nota")
        title.set_hexpand(True)
        head.append(title)
        ndrag = Gtk.GestureDrag()
        ndrag.connect("drag-begin", self._note_drag_begin, frame)
        ndrag.connect("drag-update", self._note_drag_update, frame)
        ndrag.connect("drag-end", self._note_drag_end, frame)
        head.add_controller(ndrag)
        # corpo (markdown editável)
        body = Gtk.TextView()
        body.set_wrap_mode(Gtk.WrapMode.WORD)
        body.get_buffer().set_text(note.body)
        body.set_size_request(200, 110)
        # salvar ao perder foco (GTK4: EventControllerFocus)
        for w in (title, body):
            fc = Gtk.EventControllerFocus()
            fc.connect("leave", lambda _c, fr=frame: self._save_note(fr))
            w.add_controller(fc)
        frame._title_entry = title
        frame._body_view = body
        box.append(head)
        box.append(body)
        # agent-to-note: rodar um agente com a nota (V9-S4)
        if self.controller is not None:
            agents = installed_agents()
            rrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            acombo = Gtk.ComboBoxText()
            for name in agents:
                acombo.append_text(name)
            if agents:
                acombo.set_active(0)
            acombo.set_hexpand(True)
            rb = Gtk.Button(label="▶ rodar")
            rb.connect("clicked", lambda _b, fr=frame, c=acombo: self._run_note(fr, c))
            rrow.append(acombo)
            rrow.append(rb)
            box.append(rrow)
        frame.set_child(box)
        # note.x/note.y são coords-base; o zoom escala como nos nós (P5)
        self._note_base[note.id] = (note.x, note.y)
        self.plane.put(frame, 0, 0)  # posição real vem no transform (_place)
        self._place(frame, (note.x, note.y), self.model.zoom())
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
        note.x, note.y = self._note_base.get(frame._note_id, (0.0, 0.0))  # coords-base
        self.notes.save(note)
        return False

    def _note_drag_begin(self, _g, _x, _y, frame):
        frame._norigin_base = self._note_base.get(frame._note_id, (0.0, 0.0))

    def _note_drag_update(self, _g, off_x, off_y, frame):
        o = getattr(frame, "_norigin_base", None)
        if o is None:
            return
        nb = (o[0] + off_x, o[1] + off_y)  # base-delta = off (ver _node_drag_update)
        self._note_base[frame._note_id] = nb
        self._place(frame, nb, self.model.zoom())
        self._resize_plane()

    def _note_drag_end(self, _g, _ox, _oy, frame):
        if getattr(frame, "_norigin_base", None) is not None:
            frame._norigin_base = None
            self._save_note(frame)  # persiste título/corpo/posição (coords-base)

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
        dlg, box = self._dialog("Routines (prompts agendados)")

        combo = Gtk.ComboBoxText()
        out = Gtk.Label(label="")
        out.set_xalign(0)
        out.set_selectable(True)
        out.set_wrap(True)

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
        box.append(Gtk.Label(label="Routine:"))
        box.append(combo)

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
        prompt_e.set_hexpand(True)
        int_e = Gtk.Entry()
        int_e.set_text("600")
        int_e.set_width_chars(6)
        crow.append(name_e)
        crow.append(acombo)
        crow.append(prompt_e)
        crow.append(int_e)

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
        crow.append(cbtn)
        box.append(crow)

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
            arow.append(b)
        box.append(arow)
        box.append(out)
        close = Gtk.Button(label="Fechar")
        close.connect("clicked", lambda _b: dlg.destroy())
        box.append(close)
        dlg.present()

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
        z = self.model.zoom()
        nid, note_id = getattr(frame, "_nid", None), getattr(frame, "_note_id", None)
        if nid is not None:
            x, y = to_display(self._base_pos.get(nid, (0.0, 0.0)), z)
        elif note_id is not None:
            x, y = to_display(self._note_base.get(note_id, (0.0, 0.0)), z)
        else:
            return  # frame sem id: nada a centralizar (antes rolava pra origem)
        cx, cy = x + (BASE_W * z) / 2, y + (BASE_H * z) / 2  # centro do nó escalado
        ha, va = self.scrolled.get_hadjustment(), self.scrolled.get_vadjustment()
        ha.set_value(max(0, cx - ha.get_page_size() / 2))
        va.set_value(max(0, cy - va.get_page_size() / 2))

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
        dlg, box = self._dialog("Ir para… (Ctrl-P)")
        dlg.set_default_size(420, 320)
        entry = Gtk.Entry()
        entry.set_placeholder_text("buscar agente/team/floor/nota/routine…")
        box.append(entry)
        listbox = Gtk.ListBox()
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_child(listbox)
        box.append(scroller)

        rows: list = []  # PaletteItem por linha (índice = posição)

        def rebuild():
            child = listbox.get_first_child()
            while child is not None:
                nxt = child.get_next_sibling()
                listbox.remove(child)
                child = nxt
            rows.clear()
            for it in fuzzy(entry.get_text(), items):
                row = Gtk.ListBoxRow()
                lbl = Gtk.Label(label=it.label, xalign=0)
                row.set_child(lbl)
                listbox.append(row)
                rows.append(it)
            first = listbox.get_row_at_index(0)
            if first is not None:
                listbox.select_row(first)

        def activate():
            row = listbox.get_selected_row() or listbox.get_row_at_index(0)
            if row is not None and 0 <= row.get_index() < len(rows):
                item = rows[row.get_index()]
                dlg.destroy()
                self._palette_act(item)
                return
            dlg.destroy()

        entry.connect("changed", lambda _e: rebuild())
        entry.connect("activate", lambda _e: activate())
        listbox.connect("row-activated", lambda _lb, _r: activate())
        rebuild()
        dlg.present()
        entry.grab_focus()

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
        self.win.present()


def run(store: Store | None = None) -> None:  # pragma: no cover - loop GTK
    from ..bootstrap import build_controller, default_home
    from ..engine.notes import Notes
    from ..engine.roles import agent_badges
    from ..engine.routines import Routines
    from ..engine.session import SessionManager
    from .floors_ui import resolve_floors

    app = Gtk.Application(
        application_id="app.maestro.canvas", flags=Gio.ApplicationFlags.NON_UNIQUE
    )
    state: dict = {}

    def on_activate(_a):
        base = default_home()
        controller, st = build_controller()
        state["store"] = st
        # um terminal de AGENTE interativo (sandbox bwrap) por CLI instalado
        ws = Workspace(f"{base}/workspaces")
        nodes = []
        for name, profile in installed_agents().items():
            nodes.append((name, name, agent_argv(profile, str(ws.create(name)))))
        if not nodes:  # nenhum agente instalado -> um shell de exemplo
            nodes = [("term1", "shell", ["/bin/bash"])]
        floors = resolve_floors(st, f"{base}/floors")
        badges = agent_badges(controller.get_team("coder-reviewer"))
        win = CanvasWindow(
            app,
            CanvasModel(st),
            nodes,
            controller=controller,
            edges=EdgeModel(st),
            floors=floors,
            session_manager=SessionManager(st) if floors is not None else None,
            repo=str(floors.repo) if floors is not None else None,
            notes=Notes(st),
            badges=badges,
            routines=Routines(st),
            store=st,
        )
        win.show()
        # tick in-app do scheduler: dispara routines vencidas enquanto aberto (V10-S4)
        GLib.timeout_add_seconds(30, win._routines_tick)
        # attention: realça/notifica o que precisa de você (V11-S1)
        GLib.timeout_add_seconds(10, win._refresh_attention)
        win._refresh_attention()

    def on_shutdown(_a):
        st = state.get("store")
        if st is not None:
            st.close()

    app.connect("activate", on_activate)
    app.connect("shutdown", on_shutdown)
    app.run([])
