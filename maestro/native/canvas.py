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
import os
import sys
import threading
from pathlib import Path

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
from ..engine.ask_bus import AskBus, install_ask_skill, install_client  # noqa: E402
from ..engine.ask_router import AskRouter, policy_from_env  # noqa: E402
from ..engine.envelope import EnvelopeState  # noqa: E402
from ..engine.workspace import Workspace  # noqa: E402
from ..engine.workspace_registry import WorkspaceRegistry  # noqa: E402
from .agents import STATE_COLORS, agent_argv, installed_agents  # noqa: E402
from .filetree import list_children  # noqa: E402
from .floors_ui import floor_rows, merge_text, preview_text  # noqa: E402
from .notes_ui import note_title_display  # noqa: E402
from .orchestrate import (  # noqa: E402
    _run_sync,
    run_edge_handoff_in_thread,
    run_floor_agent_in_thread,
    run_note_to_agent_in_thread,
    run_one_routine_in_thread,
    run_routines_tick_in_thread,
    run_team_in_thread,
)
from .palette import build_palette_items, fuzzy  # noqa: E402
from .routines_ui import parse_steps, routine_rows  # noqa: E402
from .state import CanvasModel, EdgeModel, to_display  # noqa: E402
from .themes import get_theme, theme_names  # noqa: E402
from .toolbar import action_menu_items  # noqa: E402

BASE_W, BASE_H = 420, 220
MIN_NODE_W, MIN_NODE_H = 240, 120  # piso ao redimensionar um card (arrastar a alça ⤡)
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
        ask_bus_dir=None,
        project_dir=None,
        home_base=None,
    ):
        self.model = model
        self._project_dir = project_dir  # raiz do projeto (workspace atual) p/ File Tree
        self._home_base = home_base  # base do app (p/ o registro de workspaces)
        self.controller = controller
        self.run_team_name = run_team_name
        self.edges = edges  # EdgeModel | None — cabos criados pelo usuário (V7-S2)
        self.floors = floors  # Floors | None — ambientes isolados (V8-S5)
        self.session_manager = session_manager  # p/ rodar agente num floor
        self.repo = repo  # path do repo de projeto (floors)
        self.notes = notes  # Notes | None — notas no canvas (V9-S3)
        self.badges = badges or {}  # agente -> cor do badge de papel (V9-S3)
        self.note_frames: dict[str, Gtk.Widget] = {}
        self._ft_frames: dict[str, Gtk.Widget] = {}  # árvores de arquivos no canvas (Fase B)
        self._ft_base: dict[str, tuple[float, float]] = {}
        # coords-base independentes do zoom; display = base * zoom (P5)
        self._base_pos: dict[str, tuple[float, float]] = {}
        self._note_base: dict[str, tuple[float, float]] = {}
        self._node_size: dict[str, tuple[float, float]] = {}  # tamanho por card (resize)
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
        self._focused_nid: str | None = None  # terminal em foco (p/ fechar via teclado)
        # cabos interativos (ADR-11): mailbox + router — só com controller + edges
        self._ask_bus_dir = ask_bus_dir  # p/ criar novos terminais de agente em runtime
        self._ask_bus = None
        self._ask_router = None
        self._ask_inflight: set[str] = set()
        if ask_bus_dir and controller is not None and edges is not None:
            self._ask_bus = AskBus(ask_bus_dir)
            self._ask_router = AskRouter(
                edge_allowed=self._ask_edge_allowed,
                delegate=self._ask_delegate,
                policy=policy_from_env(),  # limites calibráveis por ambiente
            )

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
        self.plane.add_css_class("maestro-plane")  # fundo escuro do canvas (UI-1)
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
        # tema escuro app-wide (UI-1): deixa o GTK usar a variante dark
        settings = Gtk.Settings.get_default()
        if settings is not None:
            settings.set_property("gtk-application-prefer-dark-theme", True)
        rules = [
            ".maestro-plane { background-color: #15151e; }",  # canvas escuro
            # card: fundo, borda sutil, cantos arredondados, sombra leve
            ".node-card { background-color: #1e1e2e; border: 1px solid #313244;"
            " border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.45); }",
            ".nodehead { padding: 2px 8px; background-color: #313244;"
            " border-radius: 7px 7px 0 0; }",
            ".notehead { background-color: #f9e2af; color: #1e1e2e; padding: 2px 8px;"
            " border-radius: 7px 7px 0 0; }",
            ".state-dot { font-size: 9px; margin-right: 2px; }",  # estado vira um DOT
        ]
        for st, hexc in STATE_COLORS.items():
            rules.append(f".dot-{st} {{ color: {hexc}; }}")
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
            self._connect_btn.set_tooltip_text(
                "ligar agentes por cabo (clique A, depois B) · atalho: Ctrl+Shift+L"
            )
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
            "newterm": self._open_new_terminal_dialog,
            "filetree": self._create_file_tree,
            "workspaces": self._open_workspaces_dialog,
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
        frame.add_css_class("node-card")  # card escuro: borda/cantos/sombra (UI-1)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        head.add_css_class("nodehead")
        num_lbl = Gtk.Label(label="")  # nº de posição (Ctrl+Shift+N foca) [A.2]
        num_lbl.add_css_class("dim-label")
        frame._num_lbl = num_lbl
        head.append(num_lbl)
        dot = Gtk.Label(label="●")  # estado do nó vira um DOT (UI-1)
        dot.add_css_class("state-dot")
        dot.add_css_class("dot-idle")
        head._dot = dot
        head.append(dot)
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
        title = self.model.node_name(nid, title)  # nome de exibição (renomeável/persistido)
        lbl = Gtk.Label(label=f"  {title}  ")
        lbl.set_hexpand(True)
        frame._title_lbl = lbl
        rn = Gtk.GestureClick()
        rn.connect("pressed", self._maybe_rename, nid)  # duplo-clique no título renomeia
        lbl.add_controller(rn)
        head.append(lbl)
        nclose = Gtk.Button(label="✕")
        nclose.set_has_frame(False)
        nclose.set_tooltip_text("fechar este terminal (remove do canvas nesta sessão)")
        nclose.connect("clicked", lambda _b, n=nid: self._close_node(n))
        head.append(nclose)
        # arrastar o nó pelo título (ou, em modo conexão, escolher origem/destino)
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._node_drag_begin, frame)
        drag.connect("drag-update", self._node_drag_update, frame)
        drag.connect("drag-end", self._node_drag_end, frame, nid)
        head.add_controller(drag)
        self.heads[nid] = head
        term = make_terminal(argv)
        frame._term = term  # ref p/ remover de self.terms ao fechar o nó
        fc = Gtk.EventControllerFocus()
        fc.connect("enter", lambda _c, n=nid: setattr(self, "_focused_nid", n))
        term.add_controller(fc)  # rastreia o terminal em foco (fechar via Ctrl+Shift+W)
        sz = self.model.node_size(nid, (BASE_W, BASE_H))  # tamanho por nó (persistido)
        self._node_size[nid] = sz
        term.set_hexpand(True)
        term.set_vexpand(True)
        # tamanho NATURAL (zoom é por transform); mudar isto reflui o PTY (cols/linhas)
        term.set_size_request(int(sz[0]), int(sz[1]))
        self.terms.append(term)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(head)
        box.append(term)
        # rodapé com alça de redimensionar: arraste o ⤡ p/ dar mais colunas/linhas
        foot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        foot.set_halign(Gtk.Align.END)
        grip = Gtk.Label(label="⤡")
        grip.set_tooltip_text("arraste p/ redimensionar (mais colunas/linhas pro agente)")
        grip.set_cursor(Gdk.Cursor.new_from_name("nwse-resize", None))
        rg = Gtk.GestureDrag()
        rg.connect("drag-begin", self._resize_node_begin, nid)
        rg.connect("drag-update", self._resize_node_update, nid)
        rg.connect("drag-end", self._resize_node_end, nid)
        grip.add_controller(rg)
        foot.append(grip)
        box.append(foot)
        frame.set_child(box)
        bx, by = self.model.position(nid, default)
        self._base_pos[nid] = (bx, by)
        self.plane.put(frame, 0, 0)  # posição real vem no transform (_place)
        self._place(frame, (bx, by), self.model.zoom())
        self.frames[nid] = frame
        self.order.append(nid)
        self._renumber_nodes()  # atualiza os números de posição (Ctrl+Shift+N) [A.2]

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

    # -- redimensionar um card (arrastar a alça ⤡) --
    def _resize_node_begin(self, _g, _x, _y, nid):
        self._resize_origin = self._node_size.get(nid, (BASE_W, BASE_H))

    def _resize_node_update(self, _g, off_x, off_y, nid):
        o = getattr(self, "_resize_origin", None)
        if o is None:
            return
        # a alça vive na subárvore escalada por z -> off já vem em unidades-base (=/z)
        w = max(MIN_NODE_W, o[0] + off_x)
        h = max(MIN_NODE_H, o[1] + off_y)
        self._node_size[nid] = (w, h)
        frame = self.frames.get(nid)
        term = getattr(frame, "_term", None) if frame is not None else None
        if term is not None:
            term.set_size_request(int(w), int(h))  # VTE reflui cols/linhas (PTY) sozinho
        self._resize_plane()
        self.plane.queue_draw()

    def _resize_node_end(self, _g, _ox, _oy, nid):
        self._resize_origin = None
        w, h = self._node_size.get(nid, (BASE_W, BASE_H))
        self.model.set_node_size(nid, w, h)  # persiste o tamanho

    def _maybe_rename(self, _gesture, n_press, _x, _y, nid):
        if n_press >= 2:  # duplo-clique
            self._rename_node(nid)

    def _rename_node(self, nid: str) -> None:
        frame = self.frames.get(nid)
        if frame is None:
            return
        dlg, box = self._dialog("Renomear terminal")
        entry = Gtk.Entry()
        entry.set_text(self.model.node_name(nid, nid))
        box.append(entry)

        def save(_w=None):
            name = entry.get_text().strip() or nid
            self.model.set_node_name(nid, name)  # persiste
            lbl = getattr(frame, "_title_lbl", None)
            if lbl is not None:
                lbl.set_text(f"  {name}  ")
            dlg.destroy()

        entry.connect("activate", save)
        b = Gtk.Button(label="OK")
        b.connect("clicked", save)
        box.append(b)
        dlg.present()
        entry.grab_focus()

    def _close_node(self, nid: str) -> None:
        """Remove o nó-terminal do canvas NESTA sessão (widget + PTY do agente).

        Não apaga posição persistida nem cabos no Store — relançar restaura o nó.
        O desenho de cabos já ignora nós fora de self.frames, então não sobra cabo
        solto. Remove o terminal de self.terms p/ não vazar nem quebrar _apply_theme.
        """
        frame = self.frames.pop(nid, None)
        if frame is None:
            return
        if nid in self.order:
            self.order.remove(nid)
        self.heads.pop(nid, None)
        self._base_pos.pop(nid, None)
        if self._connect_src == nid:
            self._cancel_connect()
        term = getattr(frame, "_term", None)
        if term is not None and term in self.terms:
            self.terms.remove(term)
        self.plane.remove(frame)  # destrói a subárvore -> fecha o PTY (SIGHUP no filho)
        if self._focused_nid == nid:
            self._focused_nid = None
        self._renumber_nodes()
        self.plane.queue_draw()

    # -- foco rápido por teclado (A.2) --
    def _focus_node(self, nid: str) -> None:
        fr = self.frames.get(nid)
        if fr is None:
            return
        self._center_on(fr)
        term = getattr(fr, "_term", None)
        if term is not None:
            term.grab_focus()
        self._focused_nid = nid

    def _focus_next_attention(self) -> None:
        if self._store is None:
            return
        ids = [it.agent for it in attention_items(self._store) if it.agent in self.frames]
        if not ids:
            return
        start = ids.index(self._focused_nid) + 1 if self._focused_nid in ids else 0
        self._focus_node(ids[start % len(ids)])

    def _renumber_nodes(self) -> None:
        for i, nid in enumerate(self.order, 1):
            fr = self.frames.get(nid)
            lbl = getattr(fr, "_num_lbl", None) if fr is not None else None
            if lbl is not None:
                lbl.set_text(f"{i} " if i <= 9 else "")

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
        bases = (
            list(self._base_pos.values())
            + list(self._note_base.values())
            + list(self._ft_base.values())
        )
        max_bx = max((b[0] for b in bases), default=0.0)
        max_by = max((b[1] for b in bases), default=0.0)
        max_w = max((s[0] for s in self._node_size.values()), default=BASE_W)
        max_h = max((s[1] for s in self._node_size.values()), default=BASE_H)
        need_w = max(5000, int(max_bx * z + max_w * z + 400))
        need_h = max(4000, int(max_by * z + max_h * z + 400))
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
        for fid, frame in self._ft_frames.items():
            self._place(frame, self._ft_base.get(fid, (0.0, 0.0)), z)
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
        """Estado do nó vira a COR DE UM DOT no cabeçalho (não inunda o head). UI-1."""
        head = self.heads.get(nid)
        dot = getattr(head, "_dot", None) if head is not None else None
        if dot is None:
            return
        s = state if state in STATE_COLORS else "idle"
        for st in STATE_COLORS:
            dot.remove_css_class(f"dot-{st}")
        dot.add_css_class(f"dot-{s}")

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
        pairs = set(self.edges.list())
        if (src, dst) in pairs or (dst, src) in pairs:
            # já conectados (em QUALQUER sentido) -> desconecta (toggle, sem depender da ordem)
            self.edges.remove(src, dst)
            self.edges.remove(dst, src)
            self._edge_state.pop((src, dst), None)
            self._edge_state.pop((dst, src), None)
        else:
            self.edges.add(src, dst)
            self._ask_hint(src, dst)  # avisa os terminais sobre o maestro-ask (ADR-11)
        self.plane.queue_draw()

    def _cancel_connect(self) -> None:
        if self._connect_src is not None:
            self.set_node_state(self._connect_src, "idle")
            self._connect_src = None

    # -- cabos interativos: maestro-ask (ADR-11, Fase 3) --
    def start_ask_watcher(self, interval_ms: int = 500) -> None:
        """Liga o poll do mailbox (host roteia os 'maestro-ask' dos agentes)."""
        if self._ask_bus is None:
            return
        self._ask_bus.cleanup(max_age_seconds=3600)  # limpa órfãos (broker sobrevive)
        GLib.timeout_add(interval_ms, self._ask_tick)

    def _ask_edge_allowed(self, frm: str, to: str) -> bool:
        if self.edges is None:
            return False
        pairs = set(self.edges.list())
        return (frm, to) in pairs or (to, frm) in pairs  # cabo em qualquer sentido

    def _ask_delegate(self, to: str, prompt: str) -> str:
        env = _run_sync(self.controller.delegate(to, prompt))  # síncrono no worker
        if env.state is EnvelopeState.DONE:
            return env.result or ""
        return f"[{to} retornou {env.state}] {env.note or env.result or ''}"

    def _ask_tick(self) -> bool:
        if self._ask_bus is None:
            return False
        started = False
        try:
            for req in self._ask_bus.pending_requests():
                if req.id in self._ask_inflight:
                    continue
                self._ask_inflight.add(req.id)
                self._ask_set_edge_state(req.frm, req.to, "busy")
                threading.Thread(target=self._ask_process, args=(req,), daemon=True).start()
                started = True
        except Exception as exc:  # nunca derruba o tick
            _log.error("ask_tick falhou: %s", exc)
        if started:
            self.plane.queue_draw()
        return True  # continua o poll

    def _ask_process(self, req) -> None:
        """Roda em thread daemon: AskRouter.handle chama delegate (síncrono via _run_sync)."""
        resp = None
        try:
            resp = self._ask_router.handle(req)
            self._ask_bus.write_response(resp)
        except Exception as exc:
            _log.error("ask_process falhou: %s", exc)
        finally:
            self._ask_inflight.discard(req.id)
        GLib.idle_add(self._ask_reflect, req, resp)

    def _ask_reflect(self, req, resp) -> bool:
        ok = bool(resp and resp.ok)
        fr = self.frames.get(req.to)
        term = getattr(fr, "_term", None) if fr is not None else None
        if term is not None:
            term.feed(
                f"\r\n\x1b[2m[{req.frm} perguntou via cabo] {req.prompt}\x1b[0m\r\n".encode()
            )
            term.feed(f"\x1b[2m[resposta enviada a {req.frm}]\x1b[0m\r\n".encode())
        self._ask_set_edge_state(req.frm, req.to, "done" if ok else "failed")
        self.plane.queue_draw()
        return False

    def _ask_set_edge_state(self, frm: str, to: str, state: str) -> None:
        if self.edges is None:
            return
        for e in self.edges.list():
            if set(e) == {frm, to}:
                self._edge_state[e] = state

    def _ask_hint(self, src: str, dst: str) -> None:
        """Avisa ambos os terminais que podem conversar pelo cabo (maestro-ask)."""
        if self._ask_bus is None:
            return
        for a, b in ((src, dst), (dst, src)):
            fr = self.frames.get(a)
            term = getattr(fr, "_term", None) if fr is not None else None
            if term is not None:
                term.feed(
                    f"\r\n\x1b[2m[maestro] cabo ligado a '{b}'. Para perguntar: "
                    f'maestro-ask {b} "<sua pergunta>"\x1b[0m\r\n'.encode()
                )

    def _on_key(self, _c, keyval, _keycode, state):
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        has_connect = getattr(self, "_connect_btn", None) is not None
        # Ctrl+Shift+L: alterna o modo conectar. NÃO usamos Esc/Ctrl-L p/ não brigar
        # com o terminal (Esc = interromper a IA; Ctrl-L = limpar a tela no shell).
        if ctrl and shift and keyval in (Gdk.KEY_l, Gdk.KEY_L) and has_connect:
            self._connect_btn.set_active(not self._connect_btn.get_active())
            return True
        # Ctrl+Shift+W: fecha o terminal em foco (Ctrl+W puro é "apagar palavra" no shell)
        if ctrl and shift and keyval in (Gdk.KEY_w, Gdk.KEY_W):
            nid = self._focused_nid
            if nid and nid in self.frames:
                self._close_node(nid)
            return True
        # Ctrl+Shift+A: pula pro próximo terminal que precisa de você (atenção) [A.2]
        if ctrl and shift and keyval in (Gdk.KEY_a, Gdk.KEY_A):
            self._focus_next_attention()
            return True
        # Ctrl+Shift+1..9: foca o terminal N (posição na ordem) [A.2]
        if ctrl and shift and Gdk.KEY_1 <= keyval <= Gdk.KEY_9:
            i = keyval - Gdk.KEY_1
            if i < len(self.order):
                self._focus_node(self.order[i])
            return True
        # Esc cancela o modo conectar SOMENTE se ele está ativo. Só chega aqui quando
        # o foco não está num terminal (o VTE consome o próprio Esc), então o Esc do
        # terminal fica preservado. return True: não propaga depois de tratado.
        if keyval == Gdk.KEY_Escape and self._connect_mode and has_connect:
            self._connect_btn.set_active(False)  # untoggle -> cancela
            return True
        if keyval == Gdk.KEY_p and ctrl:
            self._open_palette()  # Ctrl-P (V11-S2)
            return True
        return False

    # -- cabos (handoffs): desenhados no snapshot do _Plane --
    def _draw_cables_cr(self, cr):
        z = self.model.zoom()

        def box(nid):  # (x,y,w,h) no plano = base*zoom + tamanho do nó * zoom
            bx, by = to_display(self._base_pos.get(nid, (0.0, 0.0)), z)
            nw, nh = self._node_size.get(nid, (BASE_W, BASE_H))
            return (bx, by, nw * z, nh * z)

        # SÓ cabos EXPLÍCITOS do usuário (sem auto-conexão por ordem): o usuário
        # decide se/quem conectar (modo conectar). Cor azul; estado durante handoff.
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
                ax, ay, aw, ah = box(src)
                bx, by, _bw, bh = box(dst)
                cr.move_to(ax + aw, ay + ah / 2)
                cr.line_to(bx, by + bh / 2)
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
    # -- ➕ novo terminal em runtime (shell ou nova instância de agente) --
    def _unique_nid(self, prefix: str) -> str:
        i = 2
        while f"{prefix}-{i}" in self.frames:
            i += 1
        return f"{prefix}-{i}"

    def _next_node_default(self) -> tuple[int, int]:
        n = len(self.order) + len(self.note_frames)
        return (60 + (n % 6) * 80, 60 + (n % 6) * 70)  # cascata p/ não empilhar exato

    def _open_new_terminal_dialog(self):
        dlg, box = self._dialog("➕ novo terminal")
        bsh = Gtk.Button(label="🐚 terminal shell (/bin/bash)")
        bsh.connect("clicked", lambda _b: (self._new_shell_terminal(), dlg.destroy()))
        box.append(bsh)
        agents = list(installed_agents().keys())
        if self.controller is not None and self._ask_bus_dir and agents:
            box.append(Gtk.Label(label="ou nova instância de um agente:"))
            combo = Gtk.ComboBoxText()
            for a in agents:
                combo.append_text(a)
            combo.set_active(0)
            box.append(combo)
            bag = Gtk.Button(label="🤖 criar agente (participa de cabos)")
            bag.connect(
                "clicked",
                lambda _b: (self._new_agent_terminal(combo.get_active_text()), dlg.destroy()),
            )
            box.append(bag)
        dlg.present()

    def _new_shell_terminal(self) -> str | None:
        nid = self._unique_nid("shell")
        self._add_node(nid, "shell", ["/bin/bash"], default=self._next_node_default())
        self._resize_plane()
        self.plane.queue_draw()
        return nid

    def _new_agent_terminal(self, base: str | None) -> str | None:
        if not base or self.controller is None or not self._ask_bus_dir:
            return None
        profiles = installed_agents()
        if base not in profiles:
            return None
        nid = self._unique_nid(base)
        try:
            self.controller.add_agent_instance(nid, base)  # delegate/maestro-ask resolve nid
        except Exception as exc:
            _log.error("add_agent_instance falhou: %s", exc)
            return None
        base_home = Path(self._ask_bus_dir).parent
        wsp = Workspace(str(base_home / "workspaces")).create(nid)
        install_ask_skill(wsp, nid)  # ensina o maestro-ask ao novo agente
        argv = agent_argv(profiles[base], str(wsp), node=nid, ask_bus_dir=self._ask_bus_dir)
        self._add_node(nid, nid, argv, default=self._next_node_default())
        self._resize_plane()
        self.plane.queue_draw()
        return nid

    # -- workspaces / multi-projeto (Fase C) --
    def _open_workspaces_dialog(self):
        if not self._home_base:
            return
        reg = WorkspaceRegistry(self._home_base)
        reg.ensure_default(str(self._home_base))
        cur = reg.current()
        dlg, box = self._dialog("🗂️ workspaces (projetos)")
        for w in reg.list():
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            mark = "● " if w.name == cur else "○ "
            lbl = Gtk.Label(label=f"{mark}{w.name}")
            lbl.set_halign(Gtk.Align.START)
            row.append(lbl)
            sp = Gtk.Box()
            sp.set_hexpand(True)
            row.append(sp)
            if w.name != cur:
                b = Gtk.Button(label="abrir")
                b.set_tooltip_text("relança o app neste workspace")
                b.connect("clicked", lambda _b, n=w.name: self._switch_workspace(n))
                row.append(b)
            box.append(row)
        box.append(Gtk.Label(label="— novo workspace —"))
        ne = Gtk.Entry()
        ne.set_placeholder_text("nome (ex.: backend)")
        box.append(ne)
        pe = Gtk.Entry()
        pe.set_placeholder_text("caminho do projeto")
        pe.set_text(str(Path.home()))
        box.append(pe)
        addb = Gtk.Button(label="criar")

        def add(_b):
            try:
                reg.add(ne.get_text().strip(), pe.get_text().strip() or str(Path.home()))
            except ValueError as exc:
                _log.error("criar workspace: %s", exc)
                return
            dlg.destroy()
            self._open_workspaces_dialog()  # reabre já com o novo

        addb.connect("clicked", add)
        box.append(addb)
        dlg.present()

    def _switch_workspace(self, name: str) -> None:
        if not self._home_base:
            return
        WorkspaceRegistry(self._home_base).set_current(name)
        # relança o app no workspace escolhido (estado/DB isolado, ADR/Fase C)
        os.execv(sys.executable, [sys.executable, "-m", "maestro", "canvas"])

    # -- árvore de arquivos no canvas (Fase B) --
    def _ft_root(self) -> str:
        return self._project_dir or (str(self.repo) if self.repo else str(Path.home()))

    def _create_file_tree(self):
        root = self._ft_root()
        n = 1
        while f"ft-{n}" in self._ft_frames:
            n += 1
        fid = f"ft-{n}"
        frame = Gtk.Frame()
        frame._ft_id = fid
        frame.add_css_class("node-card")  # UI-1
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        head.add_css_class("nodehead")
        head.append(Gtk.Label(label=f"  📁 {Path(root).name or root}  "))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        head.append(spacer)
        close = Gtk.Button(label="✕")
        close.set_has_frame(False)
        close.set_tooltip_text("fechar a árvore de arquivos")
        close.connect("clicked", lambda _b, i=fid: self._close_file_tree(i))
        head.append(close)
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._ft_drag_begin, frame)
        drag.connect("drag-update", self._ft_drag_update, frame)
        drag.connect("drag-end", self._ft_drag_end, frame)
        head.add_controller(drag)
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_size_request(280, 320)
        scroller.set_child(self._ft_build_dir(root))
        box.append(head)
        box.append(scroller)
        frame.set_child(box)
        default = self._next_node_default()
        self._ft_base[fid] = default
        self.plane.put(frame, 0, 0)
        self._place(frame, default, self.model.zoom())
        self._ft_frames[fid] = frame
        self._resize_plane()
        self.plane.queue_draw()

    def _ft_build_dir(self, path: str) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for e in list_children(path):
            if e.is_dir:
                exp = Gtk.Expander(label=f"📁 {e.name}")
                exp._ft_path = e.path
                exp._ft_loaded = False
                exp.connect("notify::expanded", self._ft_on_expand)  # lazy
                box.append(exp)
            else:
                b = Gtk.Button(label=f"📄 {e.name}")
                b.set_has_frame(False)
                b.set_halign(Gtk.Align.START)
                b.set_tooltip_text("clique p/ copiar o caminho")
                b.connect("clicked", lambda _b, p=e.path: self._ft_copy_path(p))
                box.append(b)
        return box

    def _ft_on_expand(self, exp, _param):
        if exp.get_expanded() and not exp._ft_loaded:
            exp._ft_loaded = True
            exp.set_child(self._ft_build_dir(exp._ft_path))  # carrega filhos só ao abrir

    def _ft_copy_path(self, path: str) -> None:
        try:
            self.win.get_clipboard().set(path)  # cola num prompt de agente depois
        except Exception as exc:
            _log.error("copiar caminho falhou: %s", exc)

    def _ft_drag_begin(self, _g, _x, _y, frame):
        frame._ft_origin = self._ft_base.get(frame._ft_id, (0.0, 0.0))

    def _ft_drag_update(self, _g, off_x, off_y, frame):
        o = getattr(frame, "_ft_origin", None)
        if o is None:
            return
        nb = (o[0] + off_x, o[1] + off_y)
        self._ft_base[frame._ft_id] = nb
        self._place(frame, nb, self.model.zoom())
        self._resize_plane()

    def _ft_drag_end(self, _g, _ox, _oy, frame):
        frame._ft_origin = None

    def _close_file_tree(self, fid: str) -> None:
        frame = self._ft_frames.pop(fid, None)
        if frame is None:
            return
        self._ft_base.pop(fid, None)
        self.plane.remove(frame)
        self.plane.queue_draw()

    def _create_note(self):
        if self.notes is None:
            return
        n = len(self.note_frames)
        note = self.notes.create("Nota", "", x=120 + n * 40, y=320 + n * 40)
        self._add_note_widget(note)

    def _add_note_widget(self, note):
        frame = Gtk.Frame()
        frame._note_id = note.id
        frame.add_css_class("node-card")  # UI-1
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
        nclose = Gtk.Button(label="✕")
        nclose.set_has_frame(False)
        nclose.set_tooltip_text("apagar esta nota")
        nclose.connect("clicked", lambda _b, fr=frame: self._close_note(fr))
        head.append(nclose)
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

    def _close_note(self, frame) -> None:
        """Apaga a nota (persistente, via Notes.delete) e remove o widget do canvas."""
        note_id = getattr(frame, "_note_id", None)
        if note_id is None:
            return
        if self.notes is not None:
            self.notes.delete(note_id)
        self.note_frames.pop(note_id, None)
        self._note_base.pop(note_id, None)
        self.plane.remove(frame)
        self.plane.queue_draw()

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
            nw, nh = self._node_size.get(nid, (BASE_W, BASE_H))
        elif note_id is not None:
            x, y = to_display(self._note_base.get(note_id, (0.0, 0.0)), z)
            nw, nh = BASE_W, BASE_H
        else:
            return  # frame sem id: nada a centralizar (antes rolava pra origem)
        cx, cy = x + (nw * z) / 2, y + (nh * z) / 2  # centro do nó escalado
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
        if state.get("store") is not None:  # re-ativação: traz a janela existente, não reconstrói
            win = state.get("win")  # (W5) evita vazar o store anterior em 2ª ativação
            if win is not None:
                win.show()  # show() já chama present() na janela criada
            return
        base = default_home()
        reg = WorkspaceRegistry(base)
        reg.ensure_default(str(base))  # estado legado vira o workspace 'default'
        cur = reg.current()
        ws_meta = reg.get(cur)
        project_dir = ws_meta.project_dir if (ws_meta and ws_meta.project_dir) else None
        controller, st = build_controller(db_path=reg.db_path(cur))  # DB isolado por workspace
        state["store"] = st
        # um terminal de AGENTE interativo (sandbox bwrap) por CLI instalado
        ws = Workspace(f"{base}/workspaces")
        ask_bus_dir = f"{base}/ask-bus"
        install_client(ask_bus_dir)  # instala o maestro-ask no mailbox (montado nos agentes)
        nodes = []
        for name, profile in installed_agents().items():
            wsp = ws.create(name)
            install_ask_skill(wsp, name)  # ensina o agente a usar o maestro-ask
            nodes.append(
                (name, name, agent_argv(profile, str(wsp), node=name, ask_bus_dir=ask_bus_dir))
            )
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
            ask_bus_dir=ask_bus_dir,
            project_dir=project_dir,
            home_base=str(base),
        )
        win.show()
        state["win"] = win  # ref p/ re-ativação idempotente (W5)
        win.start_ask_watcher()  # poll do mailbox dos cabos interativos (ADR-11)
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
