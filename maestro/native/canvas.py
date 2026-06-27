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

from ..engine.ask_bus import AskBus, install_ask_skill, install_client  # noqa: E402
from ..engine.ask_router import AskRouter, policy_from_env  # noqa: E402
from ..engine.attention import attention_items, notify  # noqa: E402
from ..engine.envelope import EnvelopeState  # noqa: E402
from ..engine.floor_merge import merge_floor, merge_preview  # noqa: E402
from ..engine.notes import md_line_prefix, md_wrap  # noqa: E402
from ..engine.state.store import Store  # noqa: E402
from ..engine.workspace import Workspace  # noqa: E402
from ..engine.workspace_registry import WorkspaceRegistry  # noqa: E402
from .agents import STATE_COLORS, agent_argv, installed_agents  # noqa: E402
from .ask_capture import (  # noqa: E402
    LIVE_CAP_MS,
    LIVE_QUIET_MS,
    LIVE_SUBMIT_MS,
    LIVE_WAIT_S,
    clean_capture,
    tui_busy,
)
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
from .palette import build_action_items, build_palette_items, fuzzy, hintbar_text  # noqa: E402
from .routines_ui import parse_steps, routine_rows  # noqa: E402
from .state import (  # noqa: E402
    GRID,
    CanvasModel,
    EdgeModel,
    cable_bezier,
    minimap_layout,
    snap_point,
    snap_to_grid,
    state_activity,
    to_display,
)
from .themes import get_theme, theme_names  # noqa: E402
from .toolbar import action_menu_items  # noqa: E402

BASE_W, BASE_H = 420, 220
MIN_NODE_W, MIN_NODE_H = 240, 120  # piso ao redimensionar um card (arrastar a alça ⤡)
PAN_SCROLL_STEP = 90.0  # px de pan por unidade de scroll (SELECT + trackball) — velocidade do pan
# estado do envelope (passo done) -> estado visual do nó
_ST_MAP = {"DONE": "done", "BLOCKED": "blocked", "FAILED": "failed", "NEEDS_INPUT": "blocked"}
# C4: cores das notas (paleta enxuta, ~5; estilo catppuccin p/ casar com o tema)
NOTE_COLORS = {
    "yellow": "#f9e2af",
    "green": "#a6e3a1",
    "blue": "#89b4fa",
    "pink": "#f5c2e7",
    "mauve": "#cba6f7",
}
NOTE_COLOR_DEFAULT = "yellow"
# C2: geometria dos grupos (coords-base; *zoom na hora de desenhar)
GROUP_TITLE_H = 22  # faixa do título (alça de arrasto)
GROUP_MIN_W, GROUP_MIN_H = 200, 140
GROUP_CORNER = 16  # quadradinho de resize no canto inf-direito (px de tela)
GROUP_PAD = 16  # respiro (margem) entre a borda do grupo e os itens contidos (auto-fit)
GROUP_PAD_BOTTOM = 50  # margem inferior maior (equilibra com o topo, que tem a faixa do título)
GROUP_MEMBER_FRAC = 0.25  # item conta como "dentro" ao sobrepor >=25% (não precisa 100%)
# estado: cor + FORMA + tooltip (acessibilidade: não depender só da cor) — UI-1
_STATE_GLYPH = {"idle": "●", "busy": "◐", "blocked": "▲", "failed": "✕", "done": "✓"}
_STATE_PT = {
    "idle": "ocioso",
    "busy": "ocupado",
    "blocked": "bloqueado",
    "failed": "falhou",
    "done": "concluído",
}
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
            # Superfície cairo cobre o CONTEÚDO (grupos+cabos), não a viewport: ao rolar,
            # o GTK reaproveita/desloca o snapshot do plano, então limitar à viewport
            # deixava metade em branco. Cobrir o conteúdo evita isso E não aloca o plano
            # inteiro (5000×4000 ~80MB) — só a área onde há coisas.
            b = o._cairo_bounds()
            if b is not None:
                camx, camy = o._cam  # canvas infinito: superfície e desenho seguem a câmera
                cr = snapshot.append_cairo(Graphene.Rect().init(b[0] + camx, b[1] + camy, b[2], b[3]))
                cr.translate(camx, camy)  # desenha em base*zoom; a câmera desloca tudo
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
        groups=None,
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
        self._pan = None  # estado do pan da vista (fundo)
        self._drag = None  # estado do arrasto de nó (via gesto do plano, estável)
        self._note_pinned: set[str] = set()  # notas fixadas (não arrastam) — C4
        self.groups = groups  # Groups | None — grupos/áreas (C2), desenhados via cairo
        self._group_base: dict[str, tuple[float, float]] = {}  # EXIBIDO (auto-fit)
        self._group_size: dict[str, tuple[float, float]] = {}  # EXIBIDO (auto-fit)
        self._group_manual: dict[str, tuple[float, float, float, float]] = {}  # piso (x,y,w,h)
        self._group_color: dict[str, str] = {}
        self._group_title: dict[str, str] = {}
        self._group_user_sized: set[str] = set()  # grupos redimensionados de propósito (piso)
        self._group_excluded: set[tuple[str, str]] = set()  # (kind,id) destacados via Ctrl (não-membros)
        self._loading = False  # True só no startup: suspende auto-fit p/ restaurar tamanho EXATO
        self._group_resize = None  # estado do resize de grupo (alça canto inf-dir)
        self._edge_state: dict[tuple[str, str], str] = {}  # cor do cabo por handoff (V7-S4)
        self._active_edge: tuple[str, str] | None = None
        self._pan: tuple[float, float] | None = None
        self._focused_nid: str | None = None  # terminal em foco (p/ fechar via teclado)
        self._selected: tuple[str, str] | None = None  # (kind, id) selecionado (borda azul)
        self._ptr_over: tuple[str, str] | None = None  # (kind,id) sob o cursor (roteio do scroll)
        # cabos interativos (ADR-11): mailbox + router — só com controller + edges
        self._ask_bus_dir = ask_bus_dir  # p/ criar novos terminais de agente em runtime
        self._ask_bus = None
        self._ask_router = None
        self._ask_inflight: set[str] = set()
        # modo do cabo: "live" (Maestri: digita no terminal vivo do B) ou "headless" (mediado).
        # default live; cai no headless automaticamente se a captura falhar.
        self._ask_mode = os.environ.get("MAESTRO_ASK_MODE", "live").strip().lower()
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
        # CANVAS INFINITO: ScrolledWindow só dá a viewport (NEVER = sem rolagem/parede);
        # o pan é por CÂMERA (self._cam), sem limite — ver _pan_*/_place.
        self.scrolled = Gtk.ScrolledWindow()
        # EXTERNAL (não NEVER): com NEVER o ScrolledWindow não rola e por isso EXIGE o
        # mínimo INTEIRO do filho -> como o _Plane (Gtk.Fixed) mede a caixa dos filhos com a
        # câmera assada nos transforms, o mínimo crescia e EMPURRAVA a janela (inchava/saía
        # da tela; maximizar quebrava). EXTERNAL permite rolar programaticamente (sem barra
        # visível), então o ScrolledWindow pede mínimo pequeno e RECORTA o conteúdo na
        # viewport — a câmera (self._cam) dá o alcance infinito sem crescer a janela.
        self.scrolled.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.EXTERNAL)
        self.scrolled.set_hexpand(True)
        self.scrolled.set_vexpand(True)
        self.plane = _Plane()
        self.plane.add_css_class("maestro-plane")  # fundo escuro do canvas (UI-1)
        self.plane._owner = self
        # plano = tamanho da VIEWPORT (a câmera move o conteúdo dentro). NÃO usar um plano
        # gigante 5000×4000: com a GPU isso vira uma textura enorme do fundo CSS -> VRAM OOM.
        self.plane.set_hexpand(True)
        self.plane.set_vexpand(True)
        self._plane_size = (0, 0)  # legado (não mais usado p/ dimensionar o plano)
        self._cam = (0.0, 0.0)  # câmera (tela=base*zoom+cam); _fit_view centraliza ao abrir
        # gesto no scrolled (que NÃO rola -> referência estável, sem tremor)
        pan = Gtk.GestureDrag()
        pan.connect("drag-begin", self._pan_begin)
        pan.connect("drag-update", self._pan_update)
        pan.connect("drag-end", self._pan_end)
        self.scrolled.add_controller(pan)
        dbl = Gtk.GestureClick()  # C2: duplo-clique na faixa do grupo -> editar/renomear
        dbl.connect("pressed", self._on_canvas_click)
        self.scrolled.add_controller(dbl)
        # SELECT + trackball no uConsole vira eventos de SCROLL (ver INVENTARIO: trackball
        # natural-scroll). Tratamos scroll como PAN da câmera -> segurar SELECT e girar a
        # bola move o canvas, suave (deltas fracionários do scroll).
        scroll = Gtk.EventControllerScroll()
        scroll.set_flags(Gtk.EventControllerScrollFlags.BOTH_AXES)
        scroll.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)  # intercepta ANTES do VTE
        scroll.connect("scroll", self._on_scroll)
        self.scrolled.add_controller(scroll)
        motion = Gtk.EventControllerMotion()  # rastreia o elemento sob o cursor (roteio do scroll)
        motion.connect("motion", self._on_motion)
        self.scrolled.add_controller(motion)
        self.scrolled.set_child(self.plane)
        # Canvas é CÂMERA, não rola: o ScrolledWindow embrulha o Gtk.Fixed num GtkViewport
        # interno cujo scroll-to-focus (default LIGADO) desloca TODO o conteúdo quando um
        # filho focável (VTE/Entry) ganha foco fora da viewport -> o canvas "anda sozinho"
        # depois de um tempo, sem o usuário rolar. Desligar mantém a câmera (self._cam) como
        # única fonte de deslocamento.
        _vp = self.scrolled.get_child()
        if isinstance(_vp, Gtk.Viewport):
            _vp.set_scroll_to_focus(False)
        # C1: minimapa sobreposto (canto inf-direito) p/ navegar canvas grande
        overlay = Gtk.Overlay()
        overlay.set_child(self.scrolled)
        self._minimap = Gtk.DrawingArea()
        self._minimap.set_size_request(180, 120)
        self._minimap.set_halign(Gtk.Align.END)
        self._minimap.set_valign(Gtk.Align.END)
        self._minimap.set_margin_end(8)
        self._minimap.set_margin_bottom(8)
        self._minimap.add_css_class("minimap")
        self._minimap.set_draw_func(self._draw_minimap)
        mmclick = Gtk.GestureClick()
        mmclick.connect("pressed", self._minimap_click)
        self._minimap.add_controller(mmclick)
        overlay.add_overlay(self._minimap)
        overlay.add_overlay(self._build_fab())  # barra flutuante de ferramentas (topo-centro)
        overlay.add_overlay(self._build_note_ctx())  # 2ª pílula: contexto da NOTA selecionada
        root.append(overlay)
        self._hint_lbl = Gtk.Label(label=hintbar_text(), xalign=0)  # B2: ensina atalhos
        self._hint_lbl.add_css_class("hintbar")
        root.append(self._hint_lbl)
        self.win.set_child(root)

        self._loading = True  # suspende auto-fit no startup -> grupos voltam no tamanho EXATO salvo
        if self.groups is not None:  # carrega grupos (desenhados atrás dos nós) — C2
            for g in self.groups.list():
                self._load_group(g)
        for i, (nid, title, argv) in enumerate(nodes):
            self._add_node(nid, title, argv, default=(60 + i * 460, 60))
        if self.notes is not None:  # restaura notas salvas (V9-S3)
            for note in self.notes.list():
                self._add_note_widget(note)
        self._loading = False  # fim do startup: auto-fit volta a valer (interações ao vivo)
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
            # E3: status proativo no card — discreto, à direita do título
            ".node-status { font-size: 10px; color: #9399b2; margin: 0 6px; }",
            # B2: rodapé que ensina os atalhos (Zellij-like)
            ".hintbar { font-size: 10px; color: #9399b2; padding: 2px 8px;"
            " background-color: #181825; border-top: 1px solid #313244; }",
            # C1: minimapa sobreposto
            ".minimap { background-color: rgba(24,24,37,0.85); border: 1px solid #45475a;"
            " border-radius: 6px; }",
            # seleção: borda azul tracejada (outline não desloca o layout) p/ saber qual
            # nó/nota/árvore está selecionado (e recebe scroll do SELECT+trackball)
            ".selected { outline-color: #89b4fa; outline-style: dashed; outline-width: 2px;"
            " outline-offset: 3px; }",  # 3px de folga: a linha não fica colada no card
            # barra flutuante de ferramentas (pílula no topo-centro, estilo Maestri)
            ".fab-bar { background-color: rgba(30,30,46,0.95); border: 1px solid #45475a;"
            " border-radius: 22px; padding: 4px 8px; box-shadow: 0 4px 14px rgba(0,0,0,0.55); }",
            ".fab-btn { background: transparent; border: none; min-width: 34px;"
            " min-height: 34px; padding: 4px; color: #cdd6f4; }",
            ".fab-btn:hover { background-color: rgba(255,255,255,0.08); border-radius: 10px; }",
            ".fab-btn:disabled { opacity: 0.35; }",
            ".fab-run { color: #89b4fa; }",  # o play (azul)
            # 2ª pílula (contexto da nota): menor que a principal
            ".note-ctx-bar { border-radius: 16px; padding: 2px 5px; }",
            ".note-ctx-btn { min-width: 26px; min-height: 26px; padding: 2px; font-size: 12px; }",
            # bloco de nota estilo sticky-note (Maestri): cabeçalho compacto, título flat,
            # fechar minimalista redondo. A cor pastel preenche a nota TODA (ver .notebody-*).
            ".notehead-min { padding: 1px 4px; }",
            ".note-title { background: transparent; border: none; box-shadow: none; outline: none;"
            " min-height: 0; padding: 0 2px; font-weight: bold; color: #1e1e2e; }",
            ".note-title:focus-within { outline: none; box-shadow: none; }",
            ".note-close { min-width: 20px; min-height: 20px; padding: 0; border-radius: 10px;"
            " color: #1e1e2e; opacity: 0.5; }",
            ".note-close:hover { background-color: rgba(0,0,0,0.12); opacity: 1; }",
        ]
        for cname, hexc in NOTE_COLORS.items():  # C4: classes de cor das notas
            rules.append(f".notecol-{cname} {{ background-color: {hexc}; color: #1e1e2e; }}")
            # corpo (TextView) na MESMA cor pastel → sticky-note inteira colorida
            rules.append(f".notebody-{cname} {{ background-color: {hexc}; }}")
            rules.append(f".notebody-{cname} text {{ background-color: {hexc}; color: #1e1e2e; }}")
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
        # C3 (perf): grid como background CSS (composto na GPU) — sem cairo por frame.
        # Provider próprio: background-size = 20·zoom, atualizado só no zoom.
        self._grid_provider = Gtk.CssProvider()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, self._grid_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
            )
        self._apply_grid()

    def _apply_grid(self) -> None:
        """Grid de pontos via radial-gradient no CSS do plano (GPU; rola liso, sem lag).
        Espaçamento = 20·zoom; some em zoom muito baixo."""
        prov = getattr(self, "_grid_provider", None)
        if prov is None:
            return
        s = GRID * self.model.zoom()
        if s < 8:  # zoom muito longe: sem grid (evita poluir)
            css = ".maestro-plane { background-image: none; }"
        else:
            camx, camy = getattr(self, "_cam", (0.0, 0.0))  # grid acompanha a câmera
            px, py = camx % s, camy % s  # background-position (mód. p/ alinhar com os nós)
            css = (
                ".maestro-plane { background-image: radial-gradient(circle, "
                "rgba(128,133,159,0.5) 0px, rgba(128,133,159,0.5) 1.4px, transparent 1.8px); "
                f"background-repeat: repeat; background-size: {s:.1f}px {s:.1f}px; "
                f"background-position: {px:.1f}px {py:.1f}px; }}"
            )
        if hasattr(prov, "load_from_string"):
            prov.load_from_string(css)
        else:  # GTK4 < 4.12
            prov.load_from_data(css.encode())

    def _action_spec(self):
        """Ações do app (rótulo, chave) + mapa chave→callback. Reusado pela toolbar (☰)
        e pela paleta (D1), pra não duplicar a lista de comandos."""
        spec = action_menu_items(
            has_controller=self.controller is not None,
            has_edges=self.edges is not None,
            has_notes=self.notes is not None,
            has_floors=self.floors is not None,
            has_routines=self.routines is not None,
            team_name=self.run_team_name,
            has_groups=self.groups is not None,
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
            "group": self._create_group,
        }
        return spec, cbmap

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
        spec, cbmap = self._action_spec()
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

    def _fab_icon(self, icon_name: str, emoji: str) -> Gtk.Widget:
        """Ícone symbolic (visual line-art do print) com fallback p/ emoji se o tema não tiver."""
        try:
            disp = Gdk.Display.get_default()
            theme = Gtk.IconTheme.get_for_display(disp) if disp is not None else None
            if theme is not None and theme.has_icon(icon_name):
                return Gtk.Image.new_from_icon_name(icon_name)
        except Exception:
            pass
        return Gtk.Label(label=emoji)

    def _fab_button(self, icon_name, emoji, tip, cb, *, css=None, enabled=True) -> Gtk.Button:
        b = Gtk.Button()
        b.set_child(self._fab_icon(icon_name, emoji))
        b.set_has_frame(False)
        b.add_css_class("fab-btn")
        if css:
            b.add_css_class(css)
        b.set_tooltip_text(tip)
        b.set_sensitive(enabled and cb is not None)
        if cb is not None:
            b.connect("clicked", lambda _b: cb())
        return b

    def _build_fab(self) -> Gtk.Widget:
        """Barra FLUTUANTE de ferramentas (pílula no topo-centro, estilo Maestri). Passo 1:
        liga aos callbacks que já existem; clipe/globo/autonomia ficam desabilitados (em breve)."""
        _spec, cb = self._action_spec()
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        bar.add_css_class("fab-bar")
        bar.set_halign(Gtk.Align.CENTER)
        bar.set_valign(Gtk.Align.START)
        bar.set_margin_top(12)
        # 1) ▶ executar orquestrador (azul) — só se houver controller/time
        bar.append(self._fab_button(
            "media-playback-start-symbolic", "▶", "Executar orquestrador (rodar time)",
            cb.get("run_team"), css="fab-run", enabled="run_team" in cb))
        # 2) terminal — novo terminal
        bar.append(self._fab_button(
            "utilities-terminal-symbolic", "🖥", "Novo terminal", cb.get("newterm")))
        # 3) documento — nova nota
        bar.append(self._fab_button(
            "text-x-generic-symbolic", "📝", "Nova nota", cb.get("note"),
            enabled="note" in cb))
        # 4) clipe — contexto/anexos (em breve)
        bar.append(self._fab_button(
            "mail-attachment-symbolic", "📎", "Contexto/anexos (em breve)", None))
        # 5) pasta — árvore de arquivos
        bar.append(self._fab_button(
            "folder-symbolic", "📁", "Árvore de arquivos", cb.get("filetree")))
        # 6) globo — web/pesquisa (em breve)
        bar.append(self._fab_button(
            "globe-symbolic", "🌐", "Web/pesquisa (em breve)", None))
        # 7) Aa — paleta de comandos
        aa = Gtk.Button(label="Aa")
        aa.set_has_frame(False)
        aa.add_css_class("fab-btn")
        aa.set_tooltip_text("Paleta de comandos (Ctrl-P)")
        aa.connect("clicked", lambda _b: self._open_palette())
        bar.append(aa)
        # 8) ⦸ — controle de autonomia (em breve)
        bar.append(self._fab_button(
            "action-unavailable-symbolic", "⦸", "Autonomia: manual/auto (em breve)", None))
        return bar

    def _ctx_btn(self, label, tip, cb) -> Gtk.Button:
        """Botão de glifo-texto (B, I, #, …) p/ a barra de contexto da nota."""
        b = Gtk.Button(label=label)
        b.set_has_frame(False)
        b.add_css_class("fab-btn")
        b.add_css_class("note-ctx-btn")  # menor que a barra principal
        b.set_tooltip_text(tip)
        b.connect("clicked", lambda _b: cb())
        return b

    def _build_note_ctx(self) -> Gtk.Widget:
        """2ª pílula flutuante (estilo Maestri): ferramentas da NOTA selecionada.
        Aparece só quando uma nota está selecionada (ver _update_note_ctx)."""
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        bar.add_css_class("fab-bar")
        bar.add_css_class("note-ctx-bar")  # menor que a principal
        bar.set_halign(Gtk.Align.CENTER)
        bar.set_valign(Gtk.Align.START)
        bar.set_margin_top(66)  # folga clara abaixo da barra principal (margin_top=12)
        bar.set_visible(False)
        # 🎨 cor — popover com os 5 presets, age na nota selecionada
        colorbtn = Gtk.MenuButton(label="🎨")
        colorbtn.set_has_frame(False)
        colorbtn.add_css_class("fab-btn")
        colorbtn.add_css_class("note-ctx-btn")
        colorbtn.set_tooltip_text("cor da nota")
        cpop = Gtk.Popover()
        crow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        for cname in NOTE_COLORS:
            sw = Gtk.Button()
            sw.add_css_class(f"notecol-{cname}")
            sw.set_size_request(22, 22)
            sw.connect(
                "clicked",
                lambda _b, c=cname, p=cpop: (p.popdown(), self._ctx_set_color(c)),
            )
            crow.append(sw)
        cpop.set_child(crow)
        colorbtn.set_popover(cpop)
        bar.append(colorbtn)
        # formatação inline (envolve a seleção com markdown)
        bar.append(self._ctx_btn("B", "Negrito (**)", lambda: self._note_wrap("**", "**")))
        bar.append(self._ctx_btn("I", "Itálico (*)", lambda: self._note_wrap("*", "*")))
        bar.append(self._ctx_btn("S", "Tachado (~~)", lambda: self._note_wrap("~~", "~~")))
        bar.append(self._ctx_btn("</>", "Código inline (`)", lambda: self._note_wrap("`", "`")))
        # prefixos de linha
        bar.append(self._ctx_btn("#", "Título (heading)", lambda: self._note_line_prefix("# ")))
        bar.append(self._ctx_btn("☑", "Checklist", lambda: self._note_line_prefix("- [ ] ")))
        bar.append(self._ctx_btn("•", "Lista", lambda: self._note_line_prefix("- ")))
        # ações
        dup = self._fab_button("edit-copy-symbolic", "⧉", "Duplicar nota", self._note_duplicate)
        dup.add_css_class("note-ctx-btn")
        bar.append(dup)
        dele = self._fab_button("user-trash-symbolic", "🗑", "Apagar nota", self._note_delete)
        dele.add_css_class("note-ctx-btn")
        bar.append(dele)
        self._note_ctx_bar = bar
        return bar

    def _update_note_ctx(self) -> None:
        """Mostra a pílula de contexto só quando há uma NOTA selecionada."""
        bar = getattr(self, "_note_ctx_bar", None)
        if bar is not None:
            bar.set_visible(bool(self._selected) and self._selected[0] == "note")

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
        dot = Gtk.Label(label=_STATE_GLYPH["idle"])  # estado: cor + forma + tooltip (UI-1)
        dot.add_css_class("state-dot")
        dot.add_css_class("dot-idle")
        dot.set_tooltip_text(_STATE_PT["idle"])
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
        status = Gtk.Label(label="")  # E3: status proativo ("trabalhando…"/"esperando você")
        status.add_css_class("node-status")
        head._status = status
        head.append(status)
        nclose = Gtk.Button(label="✕")
        nclose.set_has_frame(False)
        nclose.set_tooltip_text("fechar este terminal (remove do canvas nesta sessão)")
        nclose.connect("clicked", lambda _b, n=nid: self._close_node(n))
        head.append(nclose)
        # Arrastar o nó: tratado pelo gesto do PLANO (estável), NÃO por um gesto preso
        # ao próprio cabeçalho — senão a referência se move junto e dá tremor (gist
        # KurtJacobson). A tag _drag_nid identifica o head como alça de arrasto.
        head._drag_nid = nid
        self.heads[nid] = head
        term = make_terminal(argv)
        frame._term = term  # ref p/ remover de self.terms ao fechar o nó
        fc = Gtk.EventControllerFocus()
        fc.connect("enter", lambda _c, n=nid: self._on_term_focus(n))  # clicar/focar = selecionar
        fc.connect("leave", lambda _c, n=nid: self._on_term_unfocus(n))  # monitorar só desfocado
        term.add_controller(fc)  # rastreia o terminal em foco (fechar via Ctrl+Shift+W)
        # seleção em QUALQUER clique no card (fase CAPTURE = antes do VTE consumir; não claima,
        # então o terminal/arraste seguem). Cobre re-clicar um card já focado (foco-enter só
        # dispara em MUDANÇA de foco, então sozinho falhava ao re-selecionar após clicar fora).
        selclick = Gtk.GestureClick()
        selclick.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        selclick.connect("pressed", lambda *_a, n=nid: self._select(("node", n)))
        frame.add_controller(selclick)
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
        self._mm_refresh()  # C1: novo nó aparece no minimapa
        self._autofit_all_groups()  # C2: se o nó nasceu dentro de um grupo, ele abraça

    def _place(self, child, base, z) -> None:
        """Posiciona+escala o child: tela = base*zoom + câmera (canvas infinito)."""
        px, py = to_display(base, z)
        camx, camy = self._cam
        self.plane.set_child_transform(child, _plane_xform(px + camx, py + camy, z))

    # (arrastar nó: agora via o gesto do PLANO — ver _pan_begin/_pan_update/_pan_end)

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
        w = max(MIN_NODE_W, snap_to_grid(w, GRID))  # C3: tamanho imanta à grade
        h = max(MIN_NODE_H, snap_to_grid(h, GRID))
        self._node_size[nid] = (w, h)
        frame = self.frames.get(nid)
        term = getattr(frame, "_term", None) if frame is not None else None
        if term is not None:
            term.set_size_request(int(w), int(h))  # reflui VTE p/ o tamanho alinhado
        self.model.set_node_size(nid, w, h)  # persiste o tamanho
        self._autofit_all_groups()  # C2: grupo cresce se o nó ficou maior que ele
        self._resize_plane()
        self.plane.queue_draw()

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
        """Fecha o nó-terminal: ✕ REMOVE DE VEZ (sai do roster -> não volta ao reabrir).

        Remove o widget + PTY do agente e tira o nó do roster persistido. Cabos órfãos
        são ignorados no desenho (já filtra por self.frames). Remove o terminal de
        self.terms p/ não vazar nem quebrar _apply_theme.
        """
        frame = self.frames.pop(nid, None)
        if frame is None:
            return
        self.model.remove_from_roster(nid)  # ✕ = remoção permanente (decisão do usuário)
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
        self._mm_refresh()

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
    # Arrasto unificado pelo gesto do PLANO (estável) — nó, nota e árvore de arquivos.
    def _drag_store(self, kind):
        return {"node": self._base_pos, "note": self._note_base, "ft": self._ft_base}[kind]

    def _drag_frame(self, kind, tid):
        maps = {"node": self.frames, "note": self.note_frames, "ft": self._ft_frames}
        return maps[kind].get(tid)

    def _drag_handle(self, picked):
        """Sobe da widget escolhida até achar uma ALÇA de arrasto (head de nó/nota/árvore).
        Devolve (kind, id) ou None. Botões (✕) e campos de texto não arrastam (deixam
        fechar/editar)."""
        w = picked
        while w is not None and w is not self.plane:
            if isinstance(w, (Gtk.Button, Gtk.Entry, Gtk.Text)):
                return None
            for attr, kind in (("_drag_nid", "node"), ("_drag_note", "note"), ("_drag_ft", "ft")):
                tid = getattr(w, attr, None)
                if tid is not None:
                    if kind == "note" and tid in self._note_pinned:
                        return None  # nota fixada (pin) não arrasta — C4
                    return (kind, tid)
            w = w.get_parent()
        return None

    def _over_child(self, picked) -> bool:
        """True se o ponto caiu sobre um nó/nota/árvore (não no fundo do plano)."""
        return self._elem_at(picked) is not None

    def _elem_at(self, picked):
        """(kind, id) do nó/nota/árvore sob a widget escolhida, ou None (fundo do plano)."""
        w = picked
        while w is not None and w is not self.plane:
            for attr, kind in (("_nid", "node"), ("_note_id", "note"), ("_ft_id", "ft")):
                tid = getattr(w, attr, None)
                if tid is not None:
                    return (kind, tid)
            w = w.get_parent()
        return None

    def _frame_of(self, sel):
        """Widget-frame de um (kind, id) selecionado, ou None."""
        if sel is None:
            return None
        kind, tid = sel
        store = {"node": self.frames, "note": self.note_frames, "ft": self._ft_frames}.get(kind, {})
        return store.get(tid)

    def _select(self, sel) -> None:
        """Marca (kind, id) como selecionado: borda azul tracejada. None = limpa seleção."""
        if sel == self._selected:
            return
        old = self._frame_of(self._selected)
        if old is not None:
            old.remove_css_class("selected")
        self._selected = sel
        new = self._frame_of(sel)
        if new is not None:
            new.add_css_class("selected")
        self._update_note_ctx()  # mostra/esconde a pílula de contexto da nota

    def _on_motion(self, _c, x, y):
        """Rastreia qual elemento está sob o cursor (p/ rotear o scroll do SELECT+trackball)."""
        self._ptr_over = self._elem_at(self.plane.pick(x, y, Gtk.PickFlags.DEFAULT))

    def _on_canvas_click(self, _g, n_press, x, y):
        if n_press < 2:  # só duplo-clique
            return
        picked = self.plane.pick(x, y, Gtk.PickFlags.DEFAULT)  # x,y já são coords de tela
        if self._drag_handle(picked) is not None or self._over_child(picked):
            return  # clique sobre nó/nota/árvore: deixa eles tratarem (ex.: renomear nó)
        camx, camy = self._cam  # hit-test de grupo é em base*zoom (tela - câmera)
        gid = self._group_title_band_hit(x - camx, y - camy)
        if gid is not None:
            self._group_dialog(gid)

    def _pan_begin(self, gesture, x, y):
        # x,y vêm em coords do scrolled (que NÃO rola) = coords de TELA -> estável.
        picked = self.plane.pick(x, y, Gtk.PickFlags.DEFAULT)
        self._select(self._elem_at(picked))  # pressionar seleciona o nó/nota/árvore (ou limpa no fundo)
        camx, camy = self._cam
        px, py = x - camx, y - camy  # coords base*zoom (p/ hit-test de grupo)
        self._pan = None
        self._drag = None
        self._group_resize = None
        target = self._drag_handle(picked)
        if target is not None:  # alça: conectar (nó, se no modo) ou mover
            kind, tid = target
            if kind == "node" and self._connect_mode:
                self._connect_pick(tid)
                gesture.set_state(Gtk.EventSequenceState.DENIED)
                return
            # pertença ao grupo é decidida pelo CURSOR ao vivo (simétrico): ENTRA quando o
            # cursor entra no grupo, SAI quando o cursor não está sobre nenhum. Ctrl só
            # CONGELA o auto-fit (grupo não persegue) p/ dar pra sair limpo.
            detach = bool(gesture.get_current_event_state() & Gdk.ModifierType.CONTROL_MASK)
            self._drag = {
                "kind": kind, "id": tid,
                "base": self._drag_store(kind).get(tid, (0.0, 0.0)),
                "detach": detach, "start": (x, y),
            }
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)  # não vaza p/ window-drag
            return
        if self._over_child(picked):  # corpo do nó/nota/árvore: deixa o filho interagir
            gesture.set_state(Gtk.EventSequenceState.DENIED)
            return
        # C2: grupos (cairo) — resize no canto tem prioridade sobre arrasto pela faixa
        gid = self._group_corner_hit(px, py)
        if gid is not None:
            self._group_resize = {"id": gid, "size": self._group_size.get(gid, (600.0, 360.0))}
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            return
        gid = self._group_title_band_hit(px, py)
        if gid is not None:  # arrasta o grupo + os nós contidos (move junto)
            self._drag = {
                "kind": "group",
                "id": gid,
                "base": self._group_base.get(gid, (0.0, 0.0)),
                "members": self._group_members(gid),
            }
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            return
        self._pan = self._cam  # fundo: pan move a CÂMERA (canvas infinito, sem limite)
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)  # reivindica: não move a janela

    def _pan_update(self, _g, off_x, off_y):
        z = self.model.zoom()
        if self._group_resize is not None:  # C2: redimensiona o grupo
            gid, o = self._group_resize["id"], self._group_resize["size"]
            w = max(GROUP_MIN_W, o[0] + off_x / z)
            h = max(GROUP_MIN_H, o[1] + off_y / z)
            self._group_size[gid] = (w, h)
            self.plane.queue_draw()
            return
        if self._drag is not None and self._drag["kind"] == "group":  # C2: move grupo+membros
            o, gid = self._drag["base"], self._drag["id"]
            nb = snap_point((o[0] + off_x / z, o[1] + off_y / z), GRID)
            if nb != self._group_base.get(gid):
                dx, dy = nb[0] - o[0], nb[1] - o[1]
                self._group_base[gid] = nb
                for (kind, iid), mbase in self._drag["members"].items():
                    mb = (mbase[0] + dx, mbase[1] + dy)
                    self._drag_store(kind)[iid] = mb
                    fr = self._drag_frame(kind, iid)
                    if fr is not None:
                        self._place(fr, mb, z)
                self.plane.queue_draw()
            return
        if self._drag is not None:  # mover: off em coords-PLANO (estável) -> base = off/z
            o = self._drag["base"]
            # imanta À GRADE já durante o arrasto: a janela "anda" de ponto em ponto
            nb = snap_point((o[0] + off_x / z, o[1] + off_y / z), GRID)
            kind, tid = self._drag["kind"], self._drag["id"]
            store = self._drag_store(kind)
            if nb != store.get(tid):
                store[tid] = nb
                frame = self._drag_frame(kind, tid)
                if frame is not None:
                    self._place(frame, nb, z)
                self._membership_by_cursor(kind, tid, off_x, off_y)  # entra/sai pelo CURSOR
                if not self._drag.get("detach"):  # sem Ctrl: grupo abraça os membros ao vivo
                    for gid in self._group_base:
                        self._autofit_group(gid)
                self.plane.queue_draw()
            return
        if self._pan is None:
            return
        # pan = mover a câmera (conteúdo segue o dedo), SEM limite -> canvas infinito
        self._cam = (self._pan[0] + off_x, self._pan[1] + off_y)
        self._reposition_all()

    def _pan_end(self, _g, _ox, _oy):
        if self._group_resize is not None:  # C2: fim do resize MANUAL do grupo (vira o piso)
            gid = self._group_resize["id"]
            self._group_resize = None
            w, h = self._group_size.get(gid, (600.0, 360.0))
            w = max(GROUP_MIN_W, snap_to_grid(w, GRID))
            h = max(GROUP_MIN_H, snap_to_grid(h, GRID))
            gx, gy = self._group_base.get(gid, (0.0, 0.0))
            self._group_manual[gid] = (gx, gy, w, h)  # piso = retângulo manual atual
            self._group_user_sized.add(gid)  # a partir daqui o manual é piso (primeira opção)
            self._autofit_group(gid)  # ainda cresce se um nó passar do piso
            self._persist_group(gid)  # salva o tamanho EXIBIDO (WYSIWYG) -> reabre igual
            self._resize_plane()
            self.plane.queue_draw()
            self._mm_refresh()
            return
        if self._drag is not None and self._drag["kind"] == "group":  # C2: fim do move do grupo
            gid = self._drag["id"]
            members = self._drag.get("members", {})
            self._drag = None
            gx, gy = self._group_base.get(gid, (0.0, 0.0))
            gw, gh = self._group_size.get(gid, (600.0, 360.0))
            self._group_manual[gid] = (gx, gy, gw, gh)  # piso acompanha o move
            for kind, iid in members:  # persiste cada item que moveu junto
                if kind == "node" and iid in self._base_pos:
                    self.model.set_position(iid, *self._base_pos[iid])
                elif kind == "note":
                    fr = self.note_frames.get(iid)
                    if fr is not None:
                        self._save_note(fr)
                # ft: posição não é persistida (efêmera)
            self._autofit_group(gid)
            self._persist_group(gid)  # salva o tamanho EXIBIDO (WYSIWYG) -> reabre igual
            self._resize_plane()
            self.plane.queue_draw()
            self._mm_refresh()
            return
        if self._drag is not None:  # soltou: imanta à grade + persiste (C3)
            kind, tid = self._drag["kind"], self._drag["id"]
            self._drag = None
            store = self._drag_store(kind)
            bx, by = snap_point(store.get(tid, (0.0, 0.0)), GRID)
            store[tid] = (bx, by)
            frame = self._drag_frame(kind, tid)
            if frame is not None:
                self._place(frame, (bx, by), self.model.zoom())
            if kind == "node":
                self.model.set_position(tid, bx, by)  # persiste posição do nó
            elif kind == "note" and frame is not None:
                self._save_note(frame)  # persiste posição da nota
            self._autofit_all_groups()  # C2: grupo abraça quem entrou/saiu/moveu
            self._resize_plane()
            self.plane.queue_draw()
            self._mm_refresh()
        self._pan = None

    # -- zoom: escala o PLANO (posição + transform); terminal mantém alocação/PTY --
    def _on_scroll(self, _c, dx, dy):
        # SELECT + trackball vira SCROLL no uConsole. Regra: o scroll só "entra" num nó/nota
        # se ele for o SELECIONADO **e** estiver sob o cursor; caso contrário PANA o canvas.
        # Como o controller está na fase CAPTURE, interceptamos ANTES do terminal (VTE) —
        # então o pan nunca é "roubado" ao passar por cima de uma janela.
        if self._selected is not None and self._ptr_over == self._selected:
            return False  # deixa o scroll ir pro selecionado (ex.: scrollback do terminal)
        # Pan por scroll: move a câmera pelos deltas (sinal negativo = conteúdo segue a bola).
        step = PAN_SCROLL_STEP
        camx, camy = self._cam
        self._cam = (camx - dx * step, camy - dy * step)
        self._reposition_all()
        return True  # consome: nem o terminal nem o ScrolledWindow rolam

    def _fit_view(self) -> bool:
        """Centraliza a câmera no conteúdo (cards/notas/árvores) — mostra tudo ao abrir.
        Chamado após a 1ª alocação da viewport (get_width real). One-shot p/ GLib."""
        items, _vp = self._mm_items()  # itens em coords-base (x, y, w, h, cor)
        z = self.model.zoom() or 1.0
        vw = self.scrolled.get_width() or 1
        vh = self.scrolled.get_height() or 1
        if items:
            xs0 = min(i[0] for i in items)
            ys0 = min(i[1] for i in items)
            xs1 = max(i[0] + i[2] for i in items)
            ys1 = max(i[1] + i[3] for i in items)
            cx, cy = (xs0 + xs1) / 2.0, (ys0 + ys1) / 2.0  # centro do conteúdo (base)
            self._cam = (vw / 2 - cx * z, vh / 2 - cy * z)  # leva ao meio da tela
        else:
            self._cam = (0.0, 0.0)
        self._reposition_all()
        return False  # one-shot (GLib)

    def _zoom(self, dz):
        self.model.set_zoom(self.model.zoom() + dz)
        self._apply_zoom()

    def _resize_plane(self) -> None:
        """No-op (canvas infinito): o plano fica do tamanho da viewport e a CÂMERA dá o
        alcance ilimitado. Antes crescia o plano (5000×4000+), o que com a GPU virava
        textura gigante do fundo CSS -> VRAM OOM. Mantido como no-op p/ não mexer nos
        muitos chamadores."""
        return

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
        self._apply_grid()  # espaçamento do grid acompanha o zoom
        self.plane.queue_draw()
        self._mm_refresh()

    def _reposition_all(self) -> None:
        """Re-coloca todos os widgets segundo a câmera atual (pan do canvas infinito)."""
        z = self.model.zoom()
        for nid, frame in self.frames.items():
            self._place(frame, self._base_pos.get(nid, (0.0, 0.0)), z)
        for note_id, frame in self.note_frames.items():
            self._place(frame, self._note_base.get(note_id, (0.0, 0.0)), z)
        for fid, frame in self._ft_frames.items():
            self._place(frame, self._ft_base.get(fid, (0.0, 0.0)), z)
        self._apply_grid()  # grid acompanha a câmera (background-position)
        self.plane.queue_draw()
        self._mm_refresh()

    # -- minimapa (C1): visão geral + clique navega --
    def _mm_refresh(self) -> None:
        mm = getattr(self, "_minimap", None)
        if mm is not None:
            mm.queue_draw()

    def _mm_items(self):
        """Itens do 'mundo' em coords-base: (x,y,w,h,(r,g,b)) + o retângulo da viewport."""
        items = []
        for nid, (bx, by) in self._base_pos.items():
            nw, nh = self._node_size.get(nid, (BASE_W, BASE_H))
            items.append((bx, by, nw, nh, (0.55, 0.60, 0.85)))  # nós: azulado
        for _id, (bx, by) in self._note_base.items():
            items.append((bx, by, 240, 160, (0.98, 0.89, 0.43)))  # notas: amarelo
        for _id, (bx, by) in self._ft_base.items():
            items.append((bx, by, 300, 360, (0.40, 0.70, 0.50)))  # árvore: verde
        z = self.model.zoom() or 1.0
        camx, camy = self._cam  # viewport em coords-base: canto = -cam/z, tamanho = tela/z
        vw = self.scrolled.get_width() or 1
        vh = self.scrolled.get_height() or 1
        vp = (-camx / z, -camy / z, vw / z, vh / z)
        return items, vp

    def _draw_minimap(self, _area, cr, w, h):  # pragma: no cover - precisa de GTK
        items, vp = self._mm_items()
        layout = minimap_layout([(i[0], i[1], i[2], i[3]) for i in items] + [vp], w, h)
        if layout is None:
            return
        scale, offx, offy = layout
        for x, y, rw, rh, col in items:
            cr.set_source_rgba(col[0], col[1], col[2], 0.9)
            cr.rectangle(offx + x * scale, offy + y * scale, max(rw * scale, 1.5), max(rh * scale, 1.5))
            cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.9)  # viewport (onde você está)
        cr.set_line_width(1.0)
        cr.rectangle(offx + vp[0] * scale, offy + vp[1] * scale, max(vp[2] * scale, 2), max(vp[3] * scale, 2))
        cr.stroke()

    def _minimap_click(self, _g, _n, x, y):
        items, vp = self._mm_items()
        layout = minimap_layout([(i[0], i[1], i[2], i[3]) for i in items] + [vp], self._minimap.get_width(), self._minimap.get_height())
        if layout is None:
            return
        scale, offx, offy = layout
        z = self.model.zoom() or 1.0
        world_x = (x - offx) / scale  # clique -> coord-mundo (base)
        world_y = (y - offy) / scale
        vw = self.scrolled.get_width() or 1  # centra a câmera nesse ponto (sem limite)
        vh = self.scrolled.get_height() or 1
        self._cam = (vw / 2 - world_x * z, vh / 2 - world_y * z)
        self._reposition_all()

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
        dot.set_text(_STATE_GLYPH.get(s, "●"))  # forma por estado (não só cor)
        dot.set_tooltip_text(_STATE_PT.get(s, s))
        st_lbl = getattr(head, "_status", None)  # E3: status proativo ("fazendo X")
        if st_lbl is not None:
            st_lbl.set_text(state_activity(s))

    # -- modo conexão: criar/remover cabos por clique (V7-S2) --
    def _update_hintbar(self) -> None:
        """B2: rodapé reflete o modo atual (normal / conectar / escolhendo destino)."""
        lbl = getattr(self, "_hint_lbl", None)
        if lbl is not None:
            lbl.set_text(
                hintbar_text(connect=self._connect_mode, picking=self._connect_src is not None)
            )

    def _toggle_connect(self, btn):
        self._connect_mode = btn.get_active()
        if not self._connect_mode:
            self._cancel_connect()
        self._update_hintbar()

    def _connect_pick(self, nid: str) -> None:
        """1º clique escolhe a origem; 2º cria (ou remove, se já existe) o cabo."""
        if self.edges is None:
            return
        if self._connect_src is None:
            self._connect_src = nid
            self.set_node_state(nid, "busy")  # realça a origem pendente
            self._update_hintbar()  # B2: agora "clique no DESTINO"
            return
        src, dst = self._connect_src, nid
        self._connect_src = None
        self.set_node_state(src, "idle")
        self._update_hintbar()
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
        self._update_hintbar()

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
        # MODO LIVE (padrão, estilo Maestri): digita o prompt no terminal VIVO do B e captura
        # a resposta dele. Cai no HEADLESS (variante a) se não der — A sempre recebe algo.
        if self._ask_mode != "headless":
            ans = self._ask_live(to, prompt)
            if ans and ans.strip():
                return ans
        return self._ask_headless(to, prompt)

    def _ask_headless(self, to: str, prompt: str) -> str:
        env = _run_sync(self.controller.delegate(to, prompt))  # síncrono no worker
        if env.state is EnvelopeState.DONE:
            return env.result or ""
        return f"[{to} retornou {env.state}] {env.note or env.result or ''}"

    def _on_term_focus(self, nid: str) -> None:
        # clicar em QUALQUER área do card foca o terminal -> selecionamos o card aqui (borda
        # azul). O clique no corpo (VTE) é consumido pelo terminal e não chega ao _pan_begin,
        # então o foco é o sinal confiável p/ selecionar clicando fora do cabeçalho.
        self._focused_nid = nid
        self._select(("node", nid))

    def _on_term_unfocus(self, nid: str) -> None:
        if self._focused_nid == nid:
            self._focused_nid = None

    def _term_text(self, term) -> str:
        """Texto renderizado da tela do VTE (sem ANSI). Main thread."""
        try:
            res = term.get_text_format(Vte.Format.TEXT)
        except Exception:
            return ""
        if isinstance(res, str):
            return res
        try:
            return res[0] or ""  # algumas bindings devolvem (texto, ...)
        except (TypeError, IndexError):
            return ""

    def _ask_live(self, to: str, prompt: str) -> str | None:
        """(thread worker) injeta no terminal VIVO do B e captura a resposta. None = não deu
        (sem terminal, B focado, timeout ou captura vazia) -> o chamador cai no headless."""
        fr = self.frames.get(to)
        term = getattr(fr, "_term", None) if fr is not None else None
        if term is None or to == self._focused_nid:
            return None  # sem terminal vivo, ou B sob controle manual (focado) — igual Maestri
        result: dict = {}
        done = threading.Event()
        GLib.idle_add(self._live_ask_start, term, prompt, result, done)
        done.wait(timeout=LIVE_WAIT_S)
        return result.get("answer")

    def _feed_child(self, term, text: str) -> None:
        """Escreve no stdin do agente (como se digitado). VTE 3.91 espera bytes."""
        try:
            term.feed_child(text.encode())
        except TypeError:
            term.feed_child(text)

    def _live_ask_start(self, term, prompt, result, done) -> bool:
        """(main thread) DIGITA o prompt no terminal vivo; o ENTER vai SEPARADO depois (ver
        _live_submit). A detecção de quiescência só começa após o envio."""
        oneline = " ".join(prompt.split())  # frame multi-linha -> 1 linha (não quebra a caixa)
        st = {
            "term": term, "prompt": oneline, "result": result, "done": done,
            "before": self._term_text(term), "handler": None, "submitted": False,
            "submit_id": None, "quiet_id": None, "cap_id": None, "finished": False,
        }
        self._feed_child(term, oneline)  # 1) digita o texto (SEM Enter)
        st["handler"] = term.connect("contents-changed", self._live_on_change, st)
        st["cap_id"] = GLib.timeout_add(LIVE_CAP_MS, self._live_finish, st, True)  # teto duro
        st["submit_id"] = GLib.timeout_add(LIVE_SUBMIT_MS, self._live_submit, st)  # 2) Enter
        return False

    def _live_submit(self, st) -> bool:
        """(main thread) manda o ENTER (C-m = \\r) SEPARADO e liga a detecção de fim de turno."""
        st["submit_id"] = None
        if st["finished"]:
            return False
        self._feed_child(st["term"], "\r")  # Enter como transmissão própria -> envia de verdade
        st["submitted"] = True
        st["quiet_id"] = GLib.timeout_add(LIVE_QUIET_MS, self._live_quiet, st)
        return False

    def _live_on_change(self, _term, st) -> None:
        if st["finished"] or not st["submitted"]:
            return  # ignora as mudanças do próprio texto digitado (antes do Enter)
        if st["quiet_id"]:
            GLib.source_remove(st["quiet_id"])  # novo output -> rearma a quiescência
        st["quiet_id"] = GLib.timeout_add(LIVE_QUIET_MS, self._live_quiet, st)

    def _live_quiet(self, st) -> bool:
        st["quiet_id"] = None
        if st["finished"]:
            return False
        if tui_busy(self._term_text(st["term"])):  # ainda trabalhando (pausa de "pensar")
            st["quiet_id"] = GLib.timeout_add(LIVE_QUIET_MS, self._live_quiet, st)
            return False
        self._live_finish(st, False)  # silêncio + não-ocupado = terminou o turno
        return False

    def _live_finish(self, st, timed_out) -> bool:
        if st["finished"]:
            return False
        st["finished"] = True
        term = st["term"]
        if st["handler"]:
            try:
                term.disconnect(st["handler"])
            except Exception:
                pass
        for k in ("submit_id", "quiet_id", "cap_id"):
            if st.get(k):
                GLib.source_remove(st[k])
                st[k] = None
        if not timed_out:  # no timeout deixa vazio -> chamador cai no headless
            ans = clean_capture(st["before"], self._term_text(term), st["prompt"])
            if ans:
                st["result"]["answer"] = ans
        st["done"].set()
        return False

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
        # No modo live o prompt já aparece DIGITADO no terminal do B (feed_child) e o B
        # responde lá — não duplicamos com linha cosmética (era o que confundia). A cor do
        # cabo indica sucesso/falha.
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

    # -- grid de pontos no fundo do canvas (C3) — só na viewport (leve no ARM) --
    def _cairo_bounds(self):
        """Bbox (coords-tela) do conteúdo cairo (grupos + cabos entre nós), com folga.
        Dimensiona a superfície do snapshot pra cobrir tudo (sem clipar ao rolar) sem
        alocar o plano inteiro. None se não há nada."""
        z = self.model.zoom()
        rects = []
        for nid, (bx, by) in self._base_pos.items():
            nw, nh = self._node_size.get(nid, (BASE_W, BASE_H))
            dx, dy = to_display((bx, by), z)
            rects.append((dx, dy, dx + nw * z, dy + nh * z))
        for gid in self._group_base:
            gx, gy, gw, gh = self._group_disp_rect(gid)
            rects.append((gx, gy, gx + gw, gy + gh))
        if not rects:
            return None
        x0 = min(r[0] for r in rects)
        y0 = min(r[1] for r in rects)
        x1 = max(r[2] for r in rects)
        y1 = max(r[3] for r in rects)
        pad = 60.0
        return (x0 - pad, y0 - pad, (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad)

    # -- cabos (handoffs): desenhados no snapshot do _Plane --
    def _draw_cables_cr(self, cr):
        z = self.model.zoom()
        # grid agora é background CSS (GPU), não cairo — ver _apply_grid()
        self._draw_groups_cr(cr)  # C2: grupos/áreas, atrás dos cabos e dos nós

        def box(nid):  # (x,y,w,h) no plano = base*zoom + tamanho do nó * zoom
            bx, by = to_display(self._base_pos.get(nid, (0.0, 0.0)), z)
            nw, nh = self._node_size.get(nid, (BASE_W, BASE_H))
            return (bx, by, nw * z, nh * z)

        # SÓ cabos EXPLÍCITOS do usuário (sem auto-conexão por ordem): o usuário
        # decide se/quem conectar (modo conectar). Cor azul; estado durante handoff.
        # C5: curva tipo corda (bezier) em vez de reta — leitura de direção/fluxo.
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
                x0, y0, c1x, c1y, c2x, c2y, x3, y3 = cable_bezier(box(src), box(dst))
                cr.move_to(x0, y0)
                cr.curve_to(c1x, c1y, c2x, c2y, x3, y3)
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
        self.model.add_to_roster(nid, "shell", None)  # persiste -> volta ao reabrir
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
        self.model.add_to_roster(nid, "agent", base)  # persiste -> volta ao reabrir
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
        head._drag_ft = fid  # arrasto via gesto do PLANO (estável) — ver _pan_*
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
        self._mm_refresh()
        self._autofit_all_groups()  # C2

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

    def _close_file_tree(self, fid: str) -> None:
        frame = self._ft_frames.pop(fid, None)
        if frame is None:
            return
        self._ft_base.pop(fid, None)
        self.plane.remove(frame)
        self.plane.queue_draw()
        self._mm_refresh()

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
        # cabeçalho compacto: o cabeçalho INTEIRO arrasta (sem grip "≡"); cor/pin/apagar ficam na
        # pílula de contexto (estilo Maestri). Aqui só título + fechar minimalista.
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        head.add_css_class("notehead")
        head.add_css_class("notehead-min")
        title = Gtk.Entry()
        title.add_css_class("note-title")  # flat: sem caixa, negrito, transparente
        title.set_text(note_title_display(note) if note.title else "Nota")
        title.set_hexpand(True)
        head.append(title)
        nclose = Gtk.Button(label="✕")
        nclose.set_has_frame(False)
        nclose.add_css_class("note-close")  # pequeno e redondo
        nclose.set_tooltip_text("apagar esta nota")
        nclose.connect("clicked", lambda _b, fr=frame: self._close_note(fr))
        head.append(nclose)
        head._drag_note = note.id  # arrasto via gesto do PLANO (estável) — ver _pan_*
        frame._note_head = head
        # corpo (markdown editável) — na MESMA cor pastel (sticky-note inteira)
        body = Gtk.TextView()
        body.set_wrap_mode(Gtk.WrapMode.WORD)
        body.get_buffer().set_text(note.body)
        body.set_size_request(200, 110)
        frame._body_view = body
        self._apply_note_color(frame, note.color)  # aplica a cor salva (frame + head + corpo)
        # salvar ao perder foco (GTK4: EventControllerFocus)
        for w in (title, body):
            fc = Gtk.EventControllerFocus()
            fc.connect("leave", lambda _c, fr=frame: self._save_note(fr))
            w.add_controller(fc)
        frame._title_entry = title
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
        self._mm_refresh()
        self._autofit_all_groups()  # C2

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
        # cor/pin já persistem nos seus handlers; preserva-os (get traz do store)
        self.notes.save(note)
        return False

    # -- C4: cor da nota (sticky-note: colore frame + cabeçalho + corpo) --
    def _apply_note_color(self, frame, color: str) -> None:
        col = color if color in NOTE_COLORS else NOTE_COLOR_DEFAULT
        head = getattr(frame, "_note_head", None)
        body = getattr(frame, "_body_view", None)
        for cname in NOTE_COLORS:
            frame.remove_css_class(f"notecol-{cname}")
            if head is not None:
                head.remove_css_class(f"notecol-{cname}")
            if body is not None:
                body.remove_css_class(f"notebody-{cname}")
        frame.add_css_class(f"notecol-{col}")  # fundo da nota inteira
        if head is not None:
            head.add_css_class(f"notecol-{col}")
        if body is not None:
            body.add_css_class(f"notebody-{col}")  # corpo (TextView) na mesma cor

    def _set_note_color(self, frame, color: str) -> None:
        if self.notes is None:
            return
        note = self.notes.get(frame._note_id)
        if note is None:
            return
        note.color = color
        self.notes.save(note)
        self._apply_note_color(frame, color)
        self._mm_refresh()

    def _toggle_note_pin(self, frame, btn) -> None:
        if self.notes is None:
            return
        note = self.notes.get(frame._note_id)
        if note is None:
            return
        note.pinned = btn.get_active()
        self.notes.save(note)
        if note.pinned:
            self._note_pinned.add(frame._note_id)
        else:
            self._note_pinned.discard(frame._note_id)
        btn.set_label("📌" if note.pinned else "📍")

    def _close_note(self, frame) -> None:
        """Apaga a nota (persistente, via Notes.delete) e remove o widget do canvas."""
        note_id = getattr(frame, "_note_id", None)
        if note_id is None:
            return
        if self.notes is not None:
            self.notes.delete(note_id)
        self.note_frames.pop(note_id, None)
        self._note_base.pop(note_id, None)
        self._note_pinned.discard(note_id)
        self.plane.remove(frame)
        self.plane.queue_draw()
        self._mm_refresh()

    # -- barra de contexto da nota (Fase 1): formatação markdown + duplicar/apagar --
    def _ctx_note_frame(self):
        """Frame da nota selecionada (ou None)."""
        if not (self._selected and self._selected[0] == "note"):
            return None
        return self.note_frames.get(self._selected[1])

    def _ctx_set_color(self, color: str) -> None:
        frame = self._ctx_note_frame()
        if frame is not None:
            self._set_note_color(frame, color)

    def _note_wrap(self, left: str, right: str) -> None:
        """Envolve a seleção (ou o cursor) do corpo da nota com marcadores markdown."""
        frame = self._ctx_note_frame()
        if frame is None:
            return
        buf = frame._body_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        bounds = buf.get_selection_bounds()  # PyGObject: () se vazia, (start, end) se há seleção
        if bounds:
            s, e = bounds[0].get_offset(), bounds[1].get_offset()
        else:
            s = e = buf.get_iter_at_mark(buf.get_insert()).get_offset()
        new, cs, ce = md_wrap(text, s, e, left, right)
        buf.set_text(new)
        buf.select_range(buf.get_iter_at_offset(cs), buf.get_iter_at_offset(ce))
        frame._body_view.grab_focus()
        self._save_note(frame)

    def _note_line_prefix(self, prefix: str) -> None:
        """Prefixa a linha do cursor do corpo da nota (heading/checklist/lista)."""
        frame = self._ctx_note_frame()
        if frame is None:
            return
        buf = frame._body_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        cur = buf.get_iter_at_mark(buf.get_insert()).get_offset()
        new, ncur = md_line_prefix(text, cur, prefix)
        buf.set_text(new)
        buf.place_cursor(buf.get_iter_at_offset(ncur))
        frame._body_view.grab_focus()
        self._save_note(frame)

    def _note_duplicate(self) -> None:
        """Cria uma cópia da nota selecionada (título/corpo/cor), deslocada."""
        if self.notes is None:
            return
        frame = self._ctx_note_frame()
        if frame is None:
            return
        src = self.notes.get(frame._note_id)
        if src is None:
            return
        bx, by = self._note_base.get(frame._note_id, (src.x, src.y))
        dup = self.notes.create(src.title, src.body, x=bx + 30, y=by + 30)
        dup.color = src.color
        self.notes.save(dup)
        self._add_note_widget(dup)

    def _note_delete(self) -> None:
        frame = self._ctx_note_frame()
        if frame is not None:
            self._close_note(frame)
            self._select(None)  # limpa seleção -> esconde a pílula de contexto

    # -- grupos/áreas (C2): desenhados via cairo (atrás dos nós) + hit-test --
    def _load_group(self, g) -> None:
        self._group_manual[g.id] = (g.x, g.y, g.w, g.h)  # piso persistido (manual)
        self._group_color[g.id] = g.color
        self._group_title[g.id] = g.title
        self._group_base[g.id] = (g.x, g.y)  # exibido (refinado pelo auto-fit)
        self._group_size[g.id] = (g.w, g.h)
        # o retângulo salvo é a posição/tamanho que o usuário deixou -> tratar como PISO ao
        # reabrir (senão o auto-fit encolhe o grupo pra abraçar só os nós e ele "não volta").
        self._group_user_sized.add(g.id)
        self._autofit_group(g.id)

    def _create_group(self) -> None:
        if self.groups is None:
            return
        x, y = self._next_node_default()
        g = self.groups.create(x=float(x), y=float(y))
        self._load_group(g)
        self._resize_plane()
        self.plane.queue_draw()
        self._mm_refresh()

    def _autofit_group(self, gid) -> None:
        """Tamanho EXIBIDO: ABRAÇA o conteúdo justinho, com margem (GROUP_PAD) em todos os
        lados — cresce E encolhe. Se o usuário redimensionou de propósito, esse tamanho
        vira piso (não encolhe abaixo dele). Vazio = volta ao tamanho manual/default."""
        if gid not in self._group_manual:
            return
        if self._loading:  # startup: não auto-fitar -> grupo fica no tamanho/posição EXATOS salvos
            return
        mx, my, mw, mh = self._group_manual[gid]
        members = self._group_members(gid)
        if not members:  # vazio: usa o manual/default
            self._group_base[gid] = (mx, my)
            self._group_size[gid] = (max(GROUP_MIN_W, mw), max(GROUP_MIN_H, mh))
            return
        left = top = right = bottom = None
        for (kind, iid), (bx, by) in members.items():  # bbox dos itens + margem
            nw, nh = self._item_size(kind, iid)
            ml, mt = bx - GROUP_PAD, by - GROUP_PAD - GROUP_TITLE_H  # topo: espaço p/ título
            mr, mb = bx + nw + GROUP_PAD, by + nh + GROUP_PAD_BOTTOM  # base: margem maior
            left = ml if left is None else min(left, ml)
            top = mt if top is None else min(top, mt)
            right = mr if right is None else max(right, mr)
            bottom = mb if bottom is None else max(bottom, mb)
        if gid in self._group_user_sized:  # piso manual só se redimensionou de propósito
            left, top = min(left, mx), min(top, my)
            right, bottom = max(right, mx + mw), max(bottom, my + mh)
        self._group_base[gid] = (left, top)
        self._group_size[gid] = (max(GROUP_MIN_W, right - left), max(GROUP_MIN_H, bottom - top))

    def _persist_group(self, gid) -> None:
        """Persiste o retângulo EXIBIDO do grupo (base+size pós auto-fit) — WYSIWYG: o que
        está na tela é o que reabre. Antes salvava só o 'manual', que diferia do exibido."""
        if self.groups is None or gid not in self._group_base:
            return
        bx, by = self._group_base[gid]
        gw, gh = self._group_size[gid]
        self.groups.set_rect(gid, bx, by, gw, gh)

    def _autofit_all_groups(self) -> None:
        if not self._group_base:
            return
        for gid in list(self._group_base):
            self._autofit_group(gid)
        if not self._loading:  # persiste o tamanho EXIBIDO após abraçar o conteúdo
            for gid in list(self._group_base):
                self._persist_group(gid)
        self._resize_plane()
        self.plane.queue_draw()
        self._mm_refresh()

    def _group_disp_rect(self, gid):
        """Retângulo do grupo em coords de TELA (plano): base*zoom + tamanho*zoom."""
        z = self.model.zoom()
        gx, gy = to_display(self._group_base.get(gid, (0.0, 0.0)), z)
        gw, gh = self._group_size.get(gid, (600.0, 360.0))
        return (gx, gy, gw * z, gh * z)

    def _draw_groups_cr(self, cr):
        z = self.model.zoom()
        for gid in self._group_base:
            x, y, w, h = self._group_disp_rect(gid)
            c = _rgba(NOTE_COLORS.get(self._group_color.get(gid, "blue"), NOTE_COLORS["blue"]))
            cr.set_source_rgba(c.red, c.green, c.blue, 0.10)  # corpo translúcido
            cr.rectangle(x, y, w, h)
            cr.fill()
            cr.set_source_rgba(c.red, c.green, c.blue, 0.70)  # borda
            cr.set_line_width(1.5)
            cr.rectangle(x, y, w, h)
            cr.stroke()
            band = GROUP_TITLE_H * z  # faixa do título
            cr.set_source_rgba(c.red, c.green, c.blue, 0.85)
            cr.rectangle(x, y, w, band)
            cr.fill()
            cr.set_source_rgb(0.12, 0.12, 0.18)  # texto do título
            cr.select_font_face("sans-serif")
            cr.set_font_size(max(9.0, 13.0 * z))
            cr.move_to(x + 6, y + band - 5)
            cr.show_text(self._group_title.get(gid, "Grupo"))
            # alça de resize VISÍVEL (canto inf-direito): 3 risquinhos diagonais
            cr.set_source_rgba(c.red, c.green, c.blue, 0.95)
            cr.set_line_width(1.5)
            for d in (4, 8, 12):
                cr.move_to(x + w - d, y + h - 2)
                cr.line_to(x + w - 2, y + h - d)
            cr.stroke()

    def _group_title_band_hit(self, px, py):
        """gid do grupo cuja FAIXA DE TÍTULO contém (px,py) em coords-plano (topo p/ baixo)."""
        z = self.model.zoom()
        for gid in reversed(list(self._group_base)):
            x, y, w, _h = self._group_disp_rect(gid)
            if x <= px <= x + w and y <= py <= y + GROUP_TITLE_H * z:
                return gid
        return None

    def _group_corner_hit(self, px, py):
        """gid do grupo cujo canto inf-direito (resize) contém (px,py)."""
        for gid in reversed(list(self._group_base)):
            x, y, w, h = self._group_disp_rect(gid)
            if (x + w - GROUP_CORNER) <= px <= x + w and (y + h - GROUP_CORNER) <= py <= y + h:
                return gid
        return None

    def _item_size(self, kind, iid):
        """Tamanho-base REAL do item (frame inteiro: cabeçalho+corpo+rodapé). Mede o
        widget alocado (natural, sem zoom); cai p/ nominal antes da 1ª alocação."""
        fr = self._drag_frame(kind, iid)
        if fr is not None:
            w, h = fr.get_width(), fr.get_height()
            if w > 0 and h > 0:
                return (float(w), float(h))
        if kind == "node":
            return self._node_size.get(iid, (BASE_W, BASE_H))
        if kind == "note":
            return (240.0, 160.0)
        return (300.0, 360.0)  # ft

    def _group_members(self, gid):
        """Itens (nó/nota/árvore) que SOBREPÕEM o grupo o bastante (>=25% da área do item)
        -> contam como dentro (não precisa 100%) e movem/abraçam junto.
        Devolve dict {(kind, id): (base_x, base_y)}."""
        gx, gy = self._group_base.get(gid, (0.0, 0.0))
        gw, gh = self._group_size.get(gid, (600.0, 360.0))
        members = {}
        for kind in ("node", "note", "ft"):
            for iid, (bx, by) in self._drag_store(kind).items():
                w, h = self._item_size(kind, iid)
                ix = max(0.0, min(bx + w, gx + gw) - max(bx, gx))  # interseção em x
                iy = max(0.0, min(by + h, gy + gh) - max(by, gy))  # interseção em y
                inter = ix * iy
                if inter > 0 and inter >= GROUP_MEMBER_FRAC * (w * h):
                    if (kind, iid) in self._group_excluded:
                        continue  # destacado explicitamente (Ctrl) -> não é membro
                    members[(kind, iid)] = (bx, by)
        return members

    def _group_at_cursor(self, off_x, off_y):
        """gid do grupo cujo retângulo contém o CURSOR durante o arraste (ou None)."""
        sx, sy = self._drag.get("start", (0.0, 0.0))
        camx, camy = self._cam
        cpx, cpy = sx + off_x - camx, sy + off_y - camy  # cursor em coords-plano (base*zoom)
        for gid in reversed(list(self._group_base)):
            gx, gy, gw, gh = self._group_disp_rect(gid)
            if gx <= cpx <= gx + gw and gy <= cpy <= gy + gh:
                return gid
        return None

    def _membership_by_cursor(self, kind, tid, off_x, off_y) -> None:
        """Pertença pelo CURSOR (simétrico): ENTRA quando o cursor entra num grupo, SAI quando
        o cursor não está sobre nenhum. Evita 're-entrar rápido' só porque um pedaço do item
        ficou sobreposto — e casa com o destacar via Ctrl (que congela o auto-fit)."""
        key = (kind, tid)
        inside = self._group_at_cursor(off_x, off_y)
        if inside is not None:
            if key in self._group_excluded:
                self._group_excluded.discard(key)  # cursor ENTROU -> pode pertencer
                self._autofit_group(inside)
        elif key not in self._group_excluded:
            self._group_excluded.add(key)  # cursor FORA de qualquer grupo -> não-membro
            for gid in self._group_base:
                self._autofit_group(gid)

    def _group_dialog(self, gid):
        """Renomear / recolorir / apagar o grupo (duplo-clique na faixa do título)."""
        if self.groups is None:
            return
        g = self.groups.get(gid)
        if g is None:
            return
        dlg, box = self._dialog("Grupo")
        entry = Gtk.Entry()
        entry.set_text(g.title)
        box.append(entry)
        swatches = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        for cname in NOTE_COLORS:
            sw = Gtk.Button()
            sw.add_css_class(f"notecol-{cname}")
            sw.set_size_request(24, 24)
            sw.connect("clicked", lambda _b, c=cname: self._set_group_color(gid, c))
            swatches.append(sw)
        box.append(swatches)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        okb = Gtk.Button(label="OK")
        delb = Gtk.Button(label="🗑 apagar")

        def save(_w=None):
            self._group_title[gid] = entry.get_text().strip() or "Grupo"
            cur = self.groups.get(gid)
            if cur is not None:
                cur.title = self._group_title[gid]
                cur.color = self._group_color.get(gid, cur.color)
                self.groups.save(cur)
            self.plane.queue_draw()
            dlg.destroy()

        def remove(_w=None):
            self._close_group(gid)
            dlg.destroy()

        entry.connect("activate", save)
        okb.connect("clicked", save)
        delb.connect("clicked", remove)
        row.append(okb)
        row.append(delb)
        box.append(row)
        dlg.present()
        entry.grab_focus()

    def _set_group_color(self, gid, color):
        self._group_color[gid] = color
        g = self.groups.get(gid) if self.groups is not None else None
        if g is not None:
            g.color = color
            self.groups.save(g)
        self.plane.queue_draw()

    def _close_group(self, gid):
        if self.groups is not None:
            self.groups.delete(gid)
        for d in (self._group_base, self._group_size, self._group_color, self._group_title, self._group_manual):
            d.pop(gid, None)
        self._group_user_sized.discard(gid)
        self.plane.queue_draw()
        self._mm_refresh()

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
        # D1: AÇÕES primeiro (com atalho à direita), depois navegação por entidades.
        spec, cbmap = self._action_spec()
        self._palette_cbmap = cbmap
        actions = [(label, key, "") for label, key in spec]
        if self.edges is not None:
            actions.append(("🔌 Conectar cabo", "__connect", "Ctrl+Shift+L"))
        actions.append(("⚠ Próxima atenção", "__attn", "Ctrl+Shift+A"))
        items = build_action_items(actions)
        agents = list(self.frames.keys())
        teams = self.controller.list_teams() if self.controller is not None else []
        floors = self.floors.list() if self.floors is not None else []
        notes = self.notes.list() if self.notes is not None else []
        routines = self.routines.list() if self.routines is not None else []
        items += build_palette_items(
            agents=agents, teams=teams, floors=floors, notes=notes, routines=routines
        )
        return items

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
        cx, cy = x + (nw * z) / 2, y + (nh * z) / 2  # centro do nó escalado (base*z)
        vw = self.scrolled.get_width() or 1  # câmera leva esse centro ao meio da tela
        vh = self.scrolled.get_height() or 1
        self._cam = (vw / 2 - cx, vh / 2 - cy)
        self._reposition_all()

    def _palette_act(self, item):
        if item.kind == "action":  # D1: executa um comando do app
            if item.ref == "__connect":
                btn = getattr(self, "_connect_btn", None)
                if btn is not None:
                    btn.set_active(not btn.get_active())
            elif item.ref == "__attn":
                self._focus_next_attention()
            else:
                cb = getattr(self, "_palette_cbmap", {}).get(item.ref)
                if cb is not None:
                    cb()
            return
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
        dlg, box = self._dialog("Paleta de comandos (Ctrl-P)")
        dlg.set_default_size(440, 340)
        entry = Gtk.Entry()
        entry.set_placeholder_text("buscar ação ou agente/nota/floor/routine…")
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
                rb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
                lbl = Gtk.Label(label=it.label, xalign=0)
                lbl.set_hexpand(True)
                rb.append(lbl)
                if it.hint:  # D1: mostra o atalho à direita (ensina enquanto usa)
                    hk = Gtk.Label(label=it.hint, xalign=1)
                    hk.add_css_class("dim-label")
                    rb.append(hk)
                row.set_child(rb)
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
    from ..engine.groups import Groups
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
        model = CanvasModel(st)
        # ROSTER persistido: QUAIS terminais existem (abre igual fechou). 1ª vez = semeia
        # com os agentes instalados; depois é a fonte da verdade (inclui shells/instâncias).
        roster = model.node_roster()
        if not roster:
            roster = [{"nid": n, "kind": "agent", "base": n} for n in installed_agents()]
            if not roster:
                roster = [{"nid": "shell-1", "kind": "shell", "base": None}]
            model.set_node_roster(roster)
        nodes = []
        for spec in roster:
            nid = spec.get("nid")
            if not nid:
                continue
            if spec.get("kind") == "shell":
                nodes.append((nid, model.node_name(nid, "shell"), ["/bin/bash"]))
                continue
            base = spec.get("base") or nid
            prof = installed_agents().get(base)
            if prof is None:  # CLI base não instalado -> não dá pra recriar este card
                continue
            wsp = ws.create(nid)
            install_ask_skill(wsp, nid)  # ensina o agente a usar o maestro-ask
            if nid != base and nid not in controller.agents:  # instância extra (runtime)
                try:
                    controller.add_agent_instance(nid, base)
                except Exception:
                    controller.agents[nid] = prof  # já no registry: garante só o profile
            argv = agent_argv(prof, str(wsp), node=nid, ask_bus_dir=ask_bus_dir)
            nodes.append((nid, model.node_name(nid, nid), argv))
        if not nodes:  # tudo removido / nada instalado -> um shell de exemplo
            nodes = [("shell-1", "shell", ["/bin/bash"])]
        floors = resolve_floors(st, f"{base}/floors")
        badges = agent_badges(controller.get_team("coder-reviewer"))
        win = CanvasWindow(
            app,
            model,
            nodes,
            controller=controller,
            edges=EdgeModel(st),
            floors=floors,
            session_manager=SessionManager(st) if floors is not None else None,
            repo=str(floors.repo) if floors is not None else None,
            notes=Notes(st),
            badges=badges,
            routines=Routines(st),
            groups=Groups(st),
            store=st,
            ask_bus_dir=ask_bus_dir,
            project_dir=project_dir,
            home_base=str(base),
        )
        win.show()
        GLib.timeout_add(80, win._fit_view)  # centraliza a vista no conteúdo (viewport já com tamanho real)
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
