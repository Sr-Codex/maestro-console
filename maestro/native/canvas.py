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

import json
import logging
import math
import os
import signal
import sys
import threading
import time
import unicodedata
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gio, GLib, Graphene, Gsk, Gtk, Pango, Vte  # noqa: E402

from ..engine import budget  # noqa: E402
from ..engine.ask_bus import (  # noqa: E402
    ASK_MAX_PROMPT_BYTES,
    AskBusError,
    AskRequest,
    AskResponse,
    install_ask_skill,
    install_client,
    install_connected_notes_skill,
    install_maestri_client,
    install_maestro_skill,
    validate_req,
)
from ..engine.ask_router import AskRouter, policy_from_env  # noqa: E402
from ..engine.ask_sock import SockServer  # noqa: E402
from ..engine.attention import (  # noqa: E402
    ATTENTION_VISUAL_STATES,
    attention_items,
    attention_nids,
    notify,
)
from ..engine.envelope import EnvelopeState  # noqa: E402
from ..engine.floor_merge import merge_floor, merge_preview  # noqa: E402
from ..engine.maestro_audit import append_event, read_events  # noqa: E402
from ..engine.maestro_guard import has_cycle, spawn_anomaly  # noqa: E402
from ..engine.notes import (  # noqa: E402
    file_to_note,
    md_enter_continuation,
    md_line_prefix,
    md_spans,
    md_to_pango,
    md_wrap_toggle,
    note_to_file,
)
from ..engine.proc_ram import alert_step, parse_limit_mb, tree_ram_mb  # noqa: E402
from ..engine.roles import (  # noqa: E402
    discover_roles,
    install_role_block,
    load_role_library,
    remove_role_block,
    save_role_library,
    write_role_sidecar,
)
from ..engine.session_capture import newest_session_id  # noqa: E402
from ..engine.state.store import Store  # noqa: E402
from ..engine.team_templates import (  # noqa: E402
    BUILTIN_TEAM_TEMPLATES,
    GroupSpec,
    TeamTemplate,
    TeamTemplateValidationError,
    default_team_templates_path,
    load_team_templates,
    placeholder_names,
    render_team_template,
    save_team_templates,
    validate_team_template,
)
from ..engine.teams import Role  # noqa: E402
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
from .rope import (  # noqa: E402
    ROPE_REST_EPS,
    catenary_pts,
    make_rope,
    quad_bezier_pts,
    spring_target,
    step_rope,
)
from .routines_ui import parse_steps, routine_rows  # noqa: E402
from .state import (  # noqa: E402
    GRID,
    CanvasModel,
    EdgeModel,
    cable_anchors,
    connected_notes,
    minimap_layout,
    nodes_for_note,
    snap_point,
    snap_to_grid,
    state_activity,
    to_display,
)
from .themes import (  # noqa: E402
    DEFAULT_DARK,
    DEFAULT_LIGHT,
    get_theme,
    theme_is_dark,
    theme_names,
)
from .toolbar import action_menu_items  # noqa: E402

BASE_W, BASE_H = 420, 220
MIN_NODE_W, MIN_NODE_H = 240, 120  # piso ao redimensionar um card (arrastar a alça ⤡)
MIN_NOTE_W, MIN_NOTE_H = 160, 90  # piso ao redimensionar uma nota
NOTE_W_DEFAULT, NOTE_H_DEFAULT = 200, 110  # tamanho padrão do corpo da nota
RESIZE_BAND = 5  # faixa (px de tela) em volta da borda do card onde o cursor vira resize
CABLE_DASH_ON, CABLE_DASH_OFF = 8.0, 6.0  # tracejado do cabo "fluindo" (handoff busy)
CABLE_DASH_PERIOD = CABLE_DASH_ON + CABLE_DASH_OFF  # módulo da fase animada
CABLE_FLOW_SPEED = 0.03  # unidades de fase por ms (velocidade do fluxo correndo no cabo)
CABLE_DOT_RADIUS = 5.0  # raio (px de tela) da bolinha na ponta do cabo (aparece só após conectar)
CABLE_SETTLE_FRAMES = 30  # frames em repouso antes de dormir o tick (~0,5s a 60fps)
CATENARY_SAG = 0.18  # barriga do modo catenária (fração do vão)
SPRING_SAG = 0.10  # barriga do modo bezier+mola — mais esticado (menos sag) que a catenária
ANCHOR_EASE = 0.35  # suaviza a TROCA de âncora do ímã: o endpoint escorrega em vez de teleportar
PHYS_LABEL_FRAMES = 120  # frames que o rótulo do modo de física fica visível ao trocar (~2s)
_RESIZE_CURSOR = {  # borda -> (nome CSS moderno, nome legado X11 p/ temas incompletos)
    # alguns temas de cursor (ex.: Windows-10-Icons, sem Inherits=) NÃO têm os nomes CSS
    # (ns/ew/nwse/nesw-resize) e não herdam de um tema completo → new_from_name cai no
    # padrão (seta) e o cursor "não muda". O fallback usa os nomes legados que esses temas têm.
    "n": ("ns-resize", "v_double_arrow"), "s": ("ns-resize", "v_double_arrow"),
    "e": ("ew-resize", "h_double_arrow"), "w": ("ew-resize", "h_double_arrow"),
    "nw": ("nwse-resize", "bd_double_arrow"), "se": ("nwse-resize", "bd_double_arrow"),
    "ne": ("nesw-resize", "fd_double_arrow"), "sw": ("nesw-resize", "fd_double_arrow"),
}
PAN_SCROLL_STEP = 90.0  # px de pan por unidade de scroll (SELECT + trackball) — velocidade do pan
# estado do envelope (passo done) -> estado visual do nó
_ST_MAP = {"DONE": "done", "BLOCKED": "blocked", "FAILED": "failed", "NEEDS_INPUT": "waiting"}
# C4: cores das notas (paleta enxuta, ~5; estilo catppuccin p/ casar com o tema)
NOTE_COLORS = {
    "yellow": "#f9e2af",
    "green": "#a6e3a1",
    "blue": "#89b4fa",
    "pink": "#f5c2e7",
    "mauve": "#cba6f7",
}
NOTE_COLOR_DEFAULT = "yellow"
# C4 v2: paleta rápida das NOTAS (hex; estilo das imagens #4/#6/#7). Notas guardam HEX em
# note.color (cor custom via "Mais cores"); GRUPOS seguem usando NOTE_COLORS acima.
NOTE_PALETTE = [
    "#f7e6a8",  # creme/amarelo
    "#f5c9d8",  # rosa
    "#bcd9f5",  # azul claro
    "#c4e8bf",  # verde claro
    "#fcdcab",  # pêssego/laranja claro
    "#ddc7f0",  # lilás
    "#f5f5f5",  # branco
    "#3a3a42",  # cinza escuro
    "#3c5560",  # azul petróleo
    "#1f2db5",  # azul escuro
]
NOTE_HEX_DEFAULT = "#f7e6a8"

# Ícones do terminal (Fase 1): subconjunto Lucide (ISC) bundlado em maestro/native/icons,
# cor fixada (#cdd6f4), nomes "maestro-<n>" — espelha o grid do Maestri. Theme-independent.
TERM_ICON_NAMES = [
    "terminal", "sparkles", "brain", "settings", "message-square", "server", "globe", "hammer",
    "wrench", "zap", "cpu", "memory-stick", "laptop", "monitor", "paintbrush", "folder",
    "file-text", "box", "shield", "eye", "wand-sparkles", "rocket", "database", "clock",
]
# Emojis curados (grade própria): o Gtk.EmojiChooser fica VAZIO neste device — não há
# en.gresource p/ o locale en_US. Renderizados pelo Noto Color Emoji (instalado).
TERM_EMOJIS = [
    "🤖", "🚀", "🐳", "🐍", "🔥", "⚡", "✨", "🧠", "💻", "🖥️", "🌐", "🛠️",
    "🔧", "⚙️", "📦", "🗄️", "🔒", "🛡️", "👁️", "📁", "📝", "📊", "⏰", "🎯",
]
# blocos Unicode de emoji (picker próprio com busca — o Gtk.EmojiChooser fica vazio em en_US)
_EMOJI_BLOCKS = [
    (0x1F300, 0x1F5FF), (0x1F600, 0x1F64F), (0x1F680, 0x1F6FF), (0x1F900, 0x1F9FF),
    (0x1FA70, 0x1FAFF), (0x2600, 0x26FF), (0x2700, 0x27BF),
]
_EMOJI_CATALOG: list[tuple[str, str]] | None = None  # [(char, nome em minúsculas)] — cache


def emoji_catalog() -> list[tuple[str, str]]:
    """Catálogo (char, nome) de todos os emojis nomeados — via unicodedata (sem dado externo).
    Construído 1x e cacheado. Nome em minúsculas p/ busca por substring."""
    global _EMOJI_CATALOG
    if _EMOJI_CATALOG is None:
        cat: list[tuple[str, str]] = []
        for a, b in _EMOJI_BLOCKS:
            for cp in range(a, b + 1):
                ch = chr(cp)
                try:
                    cat.append((ch, unicodedata.name(ch).lower()))
                except ValueError:
                    pass  # codepoint sem nome/atribuição → ignora
        _EMOJI_CATALOG = cat
    return _EMOJI_CATALOG


_ICON_CATALOG: list[tuple[str, str]] | None = None  # [(nome, texto-de-busca)] — cache


def icon_catalog() -> list[tuple[str, str]]:
    """Catálogo (nome, texto-de-busca) dos ícones dev bundlados — de icons/dev-icons.json
    (nome + tags do Lucide). Cacheado. Vazio se o índice faltar (degradação suave)."""
    global _ICON_CATALOG
    if _ICON_CATALOG is None:
        p = Path(__file__).resolve().parent / "icons" / "dev-icons.json"
        try:
            _ICON_CATALOG = sorted(json.loads(p.read_text(encoding="utf-8")).items())
        except OSError:
            _ICON_CATALOG = []
    return _ICON_CATALOG


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mix(h: str, target: int, f: float) -> str:
    """Mistura a cor com `target` (0=preto, 255=branco) por fração f. f>0 escurece/clareia."""
    r, g, b = _hex_to_rgb(h)
    return "#%02x%02x%02x" % tuple(int(c + (target - c) * f) for c in (r, g, b))


def _contrast_text(h: str) -> str:
    """Cor de texto legível sobre `h`: preto em fundo claro, branco em fundo escuro."""
    r, g, b = _hex_to_rgb(h)
    lum = 0.299 * r + 0.587 * g + 0.114 * b  # luminância perceptual (0–255)
    return "#1e1e2e" if lum > 150 else "#f5f5f5"


def note_hex(color: str) -> str:
    """Resolve a cor de uma nota p/ hex: aceita hex (#rrggbb), nome antigo (NOTE_COLORS)
    ou vazio → default. Mantém compatibilidade com notas salvas antes da paleta v2."""
    if color.startswith("#") and len(color) == 7:
        return color
    if color in NOTE_COLORS:
        return NOTE_COLORS[color]
    return NOTE_HEX_DEFAULT


# C2: geometria dos grupos (coords-base; *zoom na hora de desenhar)
GROUP_TITLE_H = 22  # faixa do título (alça de arrasto)
GROUP_MIN_W, GROUP_MIN_H = 200, 140
GROUP_CORNER = 16  # quadradinho de resize no canto inf-direito (px de tela)
GROUP_PAD = 16  # respiro (margem) entre a borda do grupo e os itens contidos (auto-fit)
GROUP_PAD_BOTTOM = 50  # margem inferior maior (equilibra com o topo, que tem a faixa do título)
GROUP_MEMBER_FRAC = 0.25  # item conta como "dentro" ao sobrepor >=25% (não precisa 100%)
# estado: ÍCONE (Lucide) + cor + tooltip (acessibilidade: não depender só da cor) — UI-1.
# O dot do cabeçalho é um Gtk.Image com o ícone Lucide pré-colorido `maestro-state-<st>`
# (bundle em maestro/native/icons; cor = STATE_COLORS). Glyph unicode mantido só como
# fallback/rótulo textual (legendas/testes gi-free).
_STATE_GLYPH = {
    "idle": "●", "busy": "◐", "waiting": "⏸", "blocked": "▲", "failed": "✕", "done": "✓",
}
_STATE_ICON = {st: f"maestro-state-{st}" for st in
               ("idle", "busy", "waiting", "blocked", "failed", "done")}
_STATE_PT = {
    "idle": "ocioso",
    "busy": "ocupado",
    "waiting": "aguardando (é sua vez)",
    "blocked": "bloqueado",
    "failed": "falhou",
    "done": "concluído",
}
_log = logging.getLogger(__name__)


def _rgba(hex_color: str) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(hex_color)
    return c


def _system_color_scheme() -> int | None:
    """Preferência clara/escura do SISTEMA via portal XDG (org.freedesktop.appearance):
    0 sem pref, 1 escuro, 2 claro; None se o portal não estiver disponível (ex.: uConsole
    sem xdg-desktop-portal → o chamador cai no escuro)."""
    try:
        proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None,
            "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Settings", None)
        val = proxy.call_sync(
            "ReadOne",
            GLib.Variant("(ss)", ("org.freedesktop.appearance", "color-scheme")),
            Gio.DBusCallFlags.NONE, -1, None)
        return val.unpack()[0]
    except GLib.Error:
        return None


def _cable_rgb(state) -> tuple[float, float, float]:
    """Cor (r,g,b) do cabo: cor do estado durante handoff, senão o azul ocioso padrão."""
    if state is not None:
        c = _rgba(STATE_COLORS.get(state, STATE_COLORS["idle"]))
        return (c.red, c.green, c.blue)
    return (0.23, 0.51, 0.96)


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
    elif terminal is not None and isinstance(pid, int) and pid > 0:
        terminal._child_pid = pid  # filho DIRETO (bash ou bwrap) — usado no respawn (Fase 3/5)
        try:  # pidfd: handle À PROVA de reciclagem de PID (kernel ≥5.3) p/ sinalizar com segurança
            terminal._pidfd = os.pidfd_open(pid)
        except (OSError, AttributeError):
            terminal._pidfd = None
        terminal._respawn_state = "idle"  # spawn concluído


def _spawn_into(term: Vte.Terminal, argv: list[str], cwd: str | None = None,
                envv: list[str] | None = None) -> None:
    """Dispara argv num Vte.Terminal já existente (cria PTY novo). cwd=working_directory,
    envv=lista KEY=VALUE (None = herda). Usado por make_terminal e pelo respawn (Fase 3)."""
    term.spawn_async(
        Vte.PtyFlags.DEFAULT, cwd, argv, envv, GLib.SpawnFlags.DEFAULT,
        None, None, -1, None, _on_spawn_done, argv,
    )


def make_terminal(argv: list[str], cwd: str | None = None,
                  envv: list[str] | None = None) -> Vte.Terminal:
    term = Vte.Terminal()
    _spawn_into(term, argv, cwd, envv)
    return term


# unload (Bloco C): hint mostrado no terminal de um nó descarregado (sem processo)
UNLOADED_HINT = "[maestro] ⏏ descarregado — clique no terminal (ou ⏏) pra retomar"


def _dead_terminal() -> Vte.Terminal:
    """Terminal SEM filho (nó descarregado nasce assim no startup — unload, Bloco C)."""
    term = Vte.Terminal()
    term.feed(f"\r\n  {UNLOADED_HINT}\r\n".encode())
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
        if controller is not None:  # F1: assina o usage_bus → atualiza o $ do nó ao vivo
            _ub = getattr(controller, "usage_bus", None)
            if _ub is not None:  # marshala p/ a main thread (emit vem do worker do delegate)
                _ub.set(lambda aid, _t: GLib.idle_add(self._on_usage_update, aid))
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
        self._connect_src: tuple[str, str] | None = None  # (kind, id) da origem do cabo
        self._connect_cursor: tuple[float, float] | None = None  # cursor p/ o cabo-fantasma
        self._connect_oneshot = False  # conexão iniciada por cápsula = 1 cabo, depois sai do modo
        # -- posicionar por clique (o usuário escolhe onde nasce, não algoritmo) --
        self._placing_spec: dict | None = None  # {"kind": "shell"} ou {"kind": "agent","base":...}
        self._placing_cursor: tuple[float, float] | None = None  # cursor p/ a prévia fantasma
        self._note_file_mtime: dict[tuple[str, str], float] = {}  # (nid,note_id)->mtime gravada
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
        self._edge_flow: dict[tuple[str, str], tuple[str, str]] = {}  # sentido ativo (frm→to)
        self._cable_anim_phase = 0.0  # fase do tracejado animado (cabo "fluindo")
        self._cable_tick_id = None  # id do add_tick_callback (física da corda + fluxo)
        self._ropes: dict[tuple[str, str], dict] = {}  # corda Verlet por cabo (pts/prev)
        self._springs: dict[tuple[str, str], tuple[float, float]] = {}  # ctrl suavizado (modo mola)
        self._anchor_sm: dict[tuple[str, str], tuple] = {}  # pontas suavizadas (troca de âncora)
        self._preview_rope: dict | None = None  # corda Verlet do cabo-fantasma (modo conectar)
        self._cable_rest = 0  # frames consecutivos em repouso (p/ dormir o tick)
        self._cable_phys = model.cable_phys()  # persistido: verlet|catenary|spring (Ctrl+Shift+P)
        self._phys_label_frames = 0  # frames restantes do rótulo do modo (flash ao trocar)
        self._active_edge: tuple[str, str] | None = None
        self._pan: tuple[float, float] | None = None
        self._focused_nid: str | None = None  # terminal em foco (p/ fechar via teclado)
        self._node_state: dict[str, str] = {}  # estado ATUAL por nó (atenção ∪ visual + minimapa)
        self._mon: dict[str, dict] = {}  # monitorar atividade por-nó (Fase 4): handler/quiet/active
        self._mon_alerted: set[str] = set()  # nós com alerta de atenção ativo (limpa ao focar)
        self._ram_alerted: set[str] = set()  # nós acima do limiar de RAM (histerese — Bloco D)
        self._ram_stop: threading.Event | None = None  # sinal de parada do ram watcher
        self._selected: tuple[str, str] | None = None  # (kind, id) selecionado (borda azul)
        self._note_editing: str | None = None  # nota em edição in-place (formata ao sair)
        self._ptr_over: tuple[str, str] | None = None  # (kind,id) sob o cursor (roteio do scroll)
        # cabos interativos (ADR-11) + Maestro mode (ADR-17): transporte por SOCKET por
        # agente (identidade por canal) + router — só com controller + edges
        self._ask_bus_dir = ask_bus_dir  # p/ criar novos terminais de agente em runtime
        self._sock_server = None  # SockServer: um listener por agente (<box>/sock)
        self._agent_nids: set[str] = set()  # nós de agente vivos (fonte do fleet-cap/kill-switch)
        self._recruited_by: dict[str, str] = {}  # linhagem: recruta -> manager (profundidade)
        self._mutate_log: dict[str, list[float]] = {}  # rate-limit por-manager (todos os cmds)
        self._maestro_clock = time.monotonic  # injetável nos testes
        self._ask_router = None
        # modo do cabo: "headless" (PADRÃO — resposta confiável+completa, com contexto via
        # resume por agente no run_in_session) ou "live" (opt-in: digita no terminal vivo do
        # B e RASPA a tela p/ você VER a interação — frágil ~70%, ADR-13/ADR-20). A pesquisa
        # (2026-07-01) confirmou: raspar TUI full-screen trunca por natureza (o próprio Maestri
        # sofre ~70%: alt-screen não vai p/ scrollback + PTY em chunks). "A resposta nunca deve
        # vir do pixel da tela; o live é telemetria, não transporte."
        self._ask_mode = os.environ.get("MAESTRO_ASK_MODE", "headless").strip().lower()
        if ask_bus_dir and controller is not None and edges is not None:
            self._sock_server = SockServer()
            self._ask_router = AskRouter(
                edge_allowed=self._ask_edge_allowed,
                delegate=self._ask_delegate,
                policy=policy_from_env(),  # limites calibráveis por ambiente
            )

        self._install_css()
        self.win = Gtk.ApplicationWindow(application=app)
        self._register_bundled_icons()  # ícones symbolic PRÓPRIOS (independem do tema do usuário)
        self.win.set_title("maestro console 🎼 — canvas (GTK4)")
        self.win.set_default_size(1000, 600)
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key)
        # CAPTURE: o atalho global (Ctrl+1.., Ctrl+Shift+W/A/L/P) é visto ANTES do VTE focado —
        # senão o terminal em foco "come" a tecla e o atalho não dispara. _on_key devolve False
        # p/ tudo que não trata, então a digitação normal segue indo pro terminal.
        key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.win.add_controller(key)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # Barra superior REMOVIDA (arquitetura): tudo migrou p/ a cápsula principal (FAB) e a
        # cápsula de zoom (rodapé). Ver _build_fab / _build_zoom_capsule e AGENTS.md.
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
        overlay.add_overlay(self._build_zoom_capsule())  # zoom — cápsula inferior-esquerda
        overlay.add_overlay(self._build_fleet_hud())  # HUD do fleet (topo-direita) — ADR-17 Etapa 4
        overlay.add_overlay(self._build_note_ctx())  # 2ª pílula: contexto da NOTA selecionada
        overlay.add_overlay(self._build_node_ctx())  # 2ª pílula: contexto do TERMINAL selecionado
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
            # F1: custo/tokens no header — mesmo padrão discreto do status
            ".node-cost { font-size: 10px; color: #9399b2; margin: 0 4px; }",
            ".node-ram { font-size: 10px; color: #9399b2; margin: 0 4px; }",
            ".node-ram-high { color: #ef4444; font-weight: bold; }",  # acima do limiar (D)
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
            ".fab-stop { color: #f38ba0; }",  # kill-switch (vermelho)
            ".fleet-hud { background: rgba(30,30,46,0.85); color: #cdd6f4; "
            "padding: 3px 10px; border-radius: 10px; font-size: 12px; }",  # HUD do fleet
            ".fleet-hud.hud-soft { color: #f9e2af; }",  # F1-D: budget perto do teto (âmbar)
            ".fleet-hud.hud-hard { color: #f38ba8; }",  # F1-D: budget estourado (vermelho)
            ".fab-attn { color: #f9e2af; font-size: 12px; padding: 0 4px; }",  # ⚠ N
            # diálogo Editar Terminal: rótulo de seção + caixa de preview da fonte
            ".editor-section { font-weight: bold; margin-top: 6px; }",
            ".term-font-preview { font-family: monospace; padding: 6px 8px; border-radius: 6px;"
            " background-color: rgba(0,0,0,0.25); }",
            ".node-icon { margin: 0 1px; }",  # ícone do terminal no cabeçalho
            ".ico-btn { padding: 4px; min-width: 30px; min-height: 30px; }",  # célula do grid
            ".ico-sel { background-color: rgba(137,180,250,0.25); border-radius: 6px; }",
            ".fab-bar combobox { min-height: 30px; }",  # combo de tema dentro da pílula
            ".zoom-cap { background-color: rgba(30,30,46,0.92); border: 1px solid #45475a;"
            " border-radius: 15px; padding: 1px 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.5); }",
            ".zoom-cap button { background: transparent; border: none; min-width: 24px;"
            " min-height: 24px; padding: 0 3px; color: #cdd6f4; font-size: 16px; }",
            ".zoom-cap button:hover { background-color: rgba(255,255,255,0.08);"
            " border-radius: 8px; }",
            ".zoom-cap label { color: #bac2de; font-size: 12px; padding: 0 5px; }",
            # 2ª pílula (contexto da nota): menor que a principal, com mais respiro
            ".note-ctx-bar { border-radius: 16px; padding: 3px 9px; }",
            ".note-ctx-btn { min-width: 26px; min-height: 26px; padding: 2px; font-size: 12px; }",
            # botão M ativo (modo "ver"): borda quadrada + leve realce; inativo = transparente
            ".note-md-on { border: 1px solid rgba(255,255,255,0.65); border-radius: 4px;"
            " background-color: rgba(255,255,255,0.14); }",
            # corpo: rola em vez de crescer; barra minimalista (direita, pontas arredondadas)
            ".note-scroll { background: transparent; }",
            ".note-scroll scrollbar { background: transparent; border: none; }",
            ".note-scroll scrollbar trough { background: transparent; border: none; }",
            ".note-scroll scrollbar slider { min-width: 5px; border-radius: 6px;"
            " background-color: rgba(30,30,46,0.40); }",
            ".note-scroll scrollbar slider:hover { background-color: rgba(30,30,46,0.70); }",
            # sticky-note: faixa fina superior p/ mover (cor vem do provider por-nota,
            # .note-h-<id>); cor/faixa/corpo/placeholder são gerados em _rebuild_note_colors.
            ".notehead-min { padding: 0; min-height: 12px; border-radius: 8px 8px 0 0; }",
            ".note-ph { margin: 6px 8px; }",  # placeholder alinhado ao texto
            # seletor de cor: popover escuro translúcido + swatches circulares + "Mais cores"
            ".note-pop > contents { background-color: rgba(30,30,46,0.97); border-radius: 16px;"
            " box-shadow: 0 8px 24px rgba(0,0,0,0.6); padding: 10px; }",
            # swatch circular: achata o botão (background-image padrão do tema esconde a cor)
            ".csw { border-radius: 50%; min-width: 26px; min-height: 26px; padding: 0;"
            " background-image: none; box-shadow: none;"
            " border: 1px solid rgba(255,255,255,0.18); }",
            ".csw:hover { border-color: rgba(255,255,255,0.7); }",
            ".csw-sel { border: 2px solid #89b4fa; }",  # swatch selecionado no editor
            ".note-curcolor { border-radius: 50%; min-width: 22px; min-height: 22px; }",
            ".note-morecolors { border-radius: 9px; color: #cdd6f4;"
            " background-color: rgba(255,255,255,0.06); padding: 6px; }",
            ".note-morecolors:hover { background-color: rgba(255,255,255,0.12); }",
            ".note-poprow-sep { background-color: rgba(255,255,255,0.10); min-height: 1px; }",
        ]
        for i, hexc in enumerate(NOTE_PALETTE):  # swatches circulares da paleta v2
            rules.append(f".palsw-{i} {{ background-color: {hexc}; }}")
        for cname, hexc in NOTE_COLORS.items():  # C4: cores dos GRUPOS (swatch do grupo)
            rules.append(f".notecol-{cname} {{ background-color: {hexc}; color: #1e1e2e; }}")
        # (o dot de estado virou Gtk.Image com ícone Lucide pré-colorido — sem CSS .dot-* de cor)
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
        # fonte por nota (seletor completo): provider próprio, reconstruído ao trocar a fonte
        self._note_fonts: dict[str, str] = {}  # note_id -> Pango desc (ex.: "Sans 12")
        self._font_provider = Gtk.CssProvider()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, self._font_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2
            )
        # cor por nota (hex; suporta cor custom de "Mais cores"): provider próprio
        self._note_colors: dict[str, str] = {}  # note_id -> hex (#rrggbb)
        self._color_provider = Gtk.CssProvider()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, self._color_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 3
            )
        # cor accent por TERMINAL (tint do cabeçalho): provider próprio (Fase 1)
        self._node_colors: dict[str, str] = {}  # node_id -> hex (#rrggbb)
        self._node_color_provider = Gtk.CssProvider()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, self._node_color_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 3
            )

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

    @staticmethod
    def _css_load(prov, css: str) -> None:
        """Carrega CSS num provider (string no GTK≥4.12; bytes nos anteriores)."""
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
            "filetree": lambda: self._start_placing({"kind": "filetree"}),
            "workspaces": self._open_workspaces_dialog,
            "run_team": self._run_team,
            "handoff": self._open_handoff_dialog,
            "note": lambda: self._start_placing({"kind": "note"}),
            "floors": self._open_floors_dialog,
            "routines": self._open_routines_dialog,
            "group": lambda: self._start_placing({"kind": "group"}),
            "team": self._open_team_dialog,
        }
        return spec, cbmap

    def _register_bundled_icons(self) -> None:
        """Adiciona os ícones PRÓPRIOS do app (maestro/native/icons) ao tema. São symbolic
        (recoloram pra cor da pílula) e não dependem do tema do usuário — isola o volátil
        (AGENTS.md): trocar o tema do sistema não derruba os ícones do app pra emoji."""
        try:
            disp = self.win.get_display() or Gdk.Display.get_default()
            if disp is None:
                return
            icons_dir = str(Path(__file__).resolve().parent / "icons")
            Gtk.IconTheme.get_for_display(disp).add_search_path(icons_dir)
        except Exception:
            pass  # sem ícone próprio cai no fallback de emoji (degradação suave)

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

    def _build_zoom_capsule(self) -> Gtk.Widget:
        """Cápsula de zoom (pílula) no rodapé-esquerdo — saiu da barra superior (arquitetura)."""
        cap = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        cap.add_css_class("zoom-cap")  # pílula COMPACTA própria (menor que a FAB)
        cap.set_halign(Gtk.Align.START)
        cap.set_valign(Gtk.Align.END)
        cap.set_margin_start(10)
        cap.set_margin_bottom(10)
        for label, dz, tip in (("−", -0.1, "diminuir zoom"), ("+", 0.1, "aumentar zoom")):
            b = Gtk.Button(label=label)
            b.set_has_frame(False)
            b.set_tooltip_text(tip)
            b.connect("clicked", lambda _b, d=dz: self._zoom(d))
            cap.append(b)
        self.zlabel = Gtk.Label(label="zoom 100%")
        cap.append(self.zlabel)
        return cap

    def _build_fab(self) -> Gtk.Widget:
        """Cápsula PRINCIPAL (pílula topo-centro): TODA config de software + criação de elementos
        (arquitetura — ver AGENTS.md). Absorveu o antigo menu '☰ ações' e a barra superior."""
        spec, cb = self._action_spec()
        avail = {k for _l, k in spec}  # quais ações estão disponíveis (controller/notes/…)
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        bar.add_css_class("fab-bar")
        bar.set_halign(Gtk.Align.CENTER)
        bar.set_valign(Gtk.Align.START)
        bar.set_margin_top(12)

        def add(icon, emoji, tip, key):
            bar.append(self._fab_button(icon, emoji, tip, cb.get(key), enabled=key in avail))

        # — orquestração + criação de elementos —
        bar.append(self._fab_button(
            "media-playback-start-symbolic", "▶", "Executar orquestrador (rodar time)",
            cb.get("run_team"), css="fab-run", enabled="run_team" in avail))
        add("utilities-terminal-symbolic", "🖥", "Novo terminal", "newterm")
        add("text-x-generic-symbolic", "📝", "Nova nota", "note")
        add("list-add-symbolic", "⬚", "Novo grupo", "group")
        add("system-run-symbolic", "🧩", "Montar equipe (Team Templates)", "team")
        add("mail-forward-symbolic", "⇄", "Disparar handoff", "handoff")
        # — conectar (toggle) —
        if self.edges is not None:
            self._connect_btn = Gtk.ToggleButton()
            self._connect_btn.set_child(self._fab_icon("maestro-connect-symbolic", "🔗"))
            self._connect_btn.set_has_frame(False)
            self._connect_btn.add_css_class("fab-btn")
            self._connect_btn.set_tooltip_text("ligar agentes por cabo (Ctrl+Shift+L)")
            self._connect_btn.connect("toggled", self._toggle_connect)
            bar.append(self._connect_btn)
        # — kill-switch do fleet (ADR-17): só quando o Maestro mode é possível —
        if self._sock_server is not None:
            bar.append(self._fab_button(
                "process-stop-symbolic", "⛔", "Parar TODOS os agentes (kill-switch)",
                self._confirm_kill_all, css="fab-stop"))
            bar.append(self._fab_button(  # F1 Bloco D: teto de gasto ($)
                "wallet-symbolic", "💰", "Limites: gasto dos agentes ($) e RAM por nó",
                self._budget_dialog))
        # — config de software / features globais —
        add("folder-symbolic", "📁", "Árvore de arquivos", "filetree")
        add("view-grid-symbolic", "🗂", "Workspaces", "workspaces")
        add("drive-harddisk-symbolic", "🧱", "Floors", "floors")
        add("alarm-symbolic", "⏰", "Routines", "routines")
        # (tema saiu da FAB — o tema GLOBAL é definido pelo editor: aba Tema → "Aplicar a TODOS")
        # paleta de comandos (Ctrl-P)
        aa = Gtk.Button(label="Aa")
        aa.set_has_frame(False)
        aa.add_css_class("fab-btn")
        aa.set_tooltip_text("Paleta de comandos (Ctrl-P)")
        aa.connect("clicked", lambda _b: self._open_palette())
        bar.append(aa)
        # atenção (status): "⚠ N" quando algo precisa de você
        self._attn_label = Gtk.Label(label="")
        self._attn_label.set_tooltip_text("precisam de você — clique p/ pular pro próximo")
        self._attn_label.add_css_class("fab-attn")
        _attn_click = Gtk.GestureClick()  # clicar no "⚠ N" pula pro próximo nó em atenção
        _attn_click.connect("released", lambda *_a: self._focus_next_attention())
        self._attn_label.add_controller(_attn_click)
        bar.append(self._attn_label)
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
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar.add_css_class("fab-bar")
        bar.add_css_class("note-ctx-bar")  # menor que a principal
        bar.set_halign(Gtk.Align.CENTER)
        bar.set_valign(Gtk.Align.START)
        bar.set_margin_top(66)  # folga clara abaixo da barra principal (margin_top=12)
        bar.set_visible(False)
        # cor — botão mostra a COR ATUAL numa bolinha; popover escuro c/ paleta circular + custom
        colorbtn = Gtk.MenuButton()
        colorbtn.set_has_frame(False)
        colorbtn.add_css_class("fab-btn")
        colorbtn.add_css_class("note-ctx-btn")
        colorbtn.set_tooltip_text("cor da nota")
        swatch = Gtk.DrawingArea()
        swatch.set_size_request(22, 22)
        swatch.set_draw_func(self._draw_cur_color)
        self._ctx_color_swatch = swatch
        colorbtn.set_child(swatch)
        cpop = Gtk.Popover()
        cpop.add_css_class("note-pop")
        cgrid = Gtk.Grid()
        cgrid.set_row_spacing(8)
        cgrid.set_column_spacing(8)
        per_row = 7
        for i, hexc in enumerate(NOTE_PALETTE):
            sw = Gtk.Button()
            sw.set_has_frame(False)  # achata: deixa o background-color (palsw) aparecer
            sw.add_css_class("csw")
            sw.add_css_class(f"palsw-{i}")
            sw.set_tooltip_text(hexc)
            sw.connect(
                "clicked",
                lambda _b, c=hexc, p=cpop: (p.popdown(), self._ctx_set_color(c)),
            )
            cgrid.attach(sw, i % per_row, i // per_row, 1, 1)
        sep = Gtk.Box()
        sep.add_css_class("note-poprow-sep")
        sep.set_margin_top(8)
        sep.set_margin_bottom(8)
        more = Gtk.Button(label="🎨 Mais cores")
        more.set_has_frame(False)
        more.add_css_class("note-morecolors")
        more.set_hexpand(True)
        more.connect("clicked", lambda _b, p=cpop: (p.popdown(), self._ctx_pick_custom_color()))
        cbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        cbox.append(cgrid)
        cbox.append(sep)
        cbox.append(more)
        cpop.set_child(cbox)
        colorbtn.set_popover(cpop)
        bar.append(colorbtn)
        # Aa — seletor de fonte (família + tamanho) da nota
        bar.append(self._ctx_btn("Aa", "Fonte da nota", self._ctx_pick_font))
        # formatação inline (envolve a seleção com markdown)
        bar.append(self._ctx_btn("B", "Negrito (**)", lambda: self._note_wrap("**", "**")))
        bar.append(self._ctx_btn("I", "Itálico (*)", lambda: self._note_wrap("*", "*")))
        bar.append(self._ctx_btn("S", "Tachado (~~)", lambda: self._note_wrap("~~", "~~")))
        bar.append(self._ctx_btn("</>", "Código inline (`)", lambda: self._note_wrap("`", "`")))
        # prefixos de linha
        bar.append(self._ctx_btn("#", "Título (heading)", lambda: self._note_line_prefix("# ")))
        bar.append(self._ctx_btn("☑", "Checklist", lambda: self._note_line_prefix("- [ ] ")))
        bar.append(self._ctx_btn("•", "Lista", lambda: self._note_line_prefix("- ")))
        # M — alterna ver (markdown formatado) ↔ editar; borda realça quando "ver" está ativo
        self._ctx_md_btn = self._ctx_btn("M", "Ver/editar (markdown)", self._note_toggle_render)
        bar.append(self._ctx_md_btn)
        # ações
        if self.edges is not None:  # 🔌 conectar — padrão de toda cápsula contextual
            bar.append(self._ctx_connect_btn())
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
        self._update_ctx_color_swatch()  # bolinha da cor atual
        self._update_md_btn()  # estado (borda) do botão M conforme o modo da nota

    def _build_node_ctx(self) -> Gtk.Widget:
        """Cápsula contextual do TERMINAL (nó) selecionado — mesmo padrão da nota
        (arquitetura: todo elemento com config tem a sua pílula). Aparece ao selecionar 1 nó."""
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar.add_css_class("fab-bar")
        bar.add_css_class("note-ctx-bar")  # mesma pílula menor da nota
        bar.set_halign(Gtk.Align.CENTER)
        bar.set_valign(Gtk.Align.START)
        bar.set_margin_top(66)  # mesmo nível da pílula da nota (só uma aparece por vez)
        bar.set_visible(False)
        # ações DAQUELE terminal — operam sobre self._selected no clique (a pílula é única)
        ren = self._fab_button(
            "document-edit-symbolic", "✏", "Renomear terminal", self._ctx_rename_node)
        ren.add_css_class("note-ctx-btn")
        bar.append(ren)
        foc = self._fab_button(
            "find-location-symbolic", "🎯", "Centralizar a vista neste terminal",
            self._ctx_focus_node)
        foc.add_css_class("note-ctx-btn")
        bar.append(foc)
        if self.edges is not None:  # 🔌 conectar — padrão de toda cápsula contextual
            bar.append(self._ctx_connect_btn())
        edt = self._fab_button(
            "emblem-system-symbolic", "⚙", "Editar terminal (Detalhes/Aparência/Agente)",
            self._ctx_edit_node)
        edt.add_css_class("note-ctx-btn")
        bar.append(edt)
        unl = self._fab_button(
            "media-eject-symbolic", "⏏",
            "Descarregar (libera a RAM; o card fica) — descarregado, retoma",
            self._ctx_unload_node)
        unl.add_css_class("note-ctx-btn")
        bar.append(unl)
        dele = self._fab_button(
            "user-trash-symbolic", "🗑", "Fechar terminal (remove do canvas)",
            self._ctx_close_node)
        dele.add_css_class("note-ctx-btn")
        bar.append(dele)
        self._node_ctx_bar = bar
        return bar

    def _ctx_edit_node(self) -> None:
        nid = self._sel_nid()
        if nid is not None:
            self._open_terminal_editor(nid)

    def _open_terminal_editor(self, nid: str) -> None:
        """Diálogo "Editar Terminal" (abas Detalhes/Aparência/Agente) — FUNDAÇÃO (Fase 0).
        Só o NOME está ligado; os demais campos são placeholders das próximas fases (ver
        docs/11-maestri-editar-terminal.md). Persistência por-nó via model.node_cfg."""
        win, box = self._dialog("Editar Terminal")
        win.set_default_size(560, 420)  # mais largo; altura cabe na tela do uConsole (480)
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        sw = Gtk.StackSwitcher()
        sw.set_stack(stack)
        sw.set_halign(Gtk.Align.CENTER)
        box.append(sw)
        # conteúdo das abas ROLA (cap de altura) — senão a janela estoura a tela pequena
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_max_content_height(320)
        scroller.set_propagate_natural_height(True)
        scroller.set_vexpand(True)
        scroller.set_child(stack)
        box.append(scroller)
        applies: list = []  # closures rodadas no Salvar (transacional por aba)

        def soon(text: str) -> Gtk.Widget:
            lb = Gtk.Label(label=f"• {text} (em breve)", xalign=0)
            lb.add_css_class("dim-label")
            lb.set_wrap(True)
            return lb

        def page(*rows: Gtk.Widget) -> Gtk.Widget:
            p = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            p.set_margin_top(10)
            for r in rows:
                p.append(r)
            return p

        # — Detalhes — (Nome ligado; resto = roadmap)
        name = Gtk.Entry()
        name.set_placeholder_text("Nome do Terminal")
        name.set_text(self.model.node_name(nid, ""))
        det = page(name)
        det.append(self._editor_detalhes_section(nid, applies))
        det.append(self._editor_monitor_section(nid, applies))
        det.append(self._editor_maestro_section(nid, applies))
        det.append(self._editor_autoapprove_section(nid, applies))
        det.append(soon("SSH Remoto — Fase 7"))
        stack.add_titled(det, "detalhes", "Detalhes")
        # — Aparência — (Fase 1: Fonte; Cor/Ícone nas próximas etapas; Tema na Fase 2)
        ap = page()
        ap.append(self._editor_font_section(nid, applies))
        ap.append(self._editor_color_section(nid, applies))
        ap.append(self._editor_icon_section(nid, applies))
        ap.append(self._editor_theme_section(nid, applies))
        stack.add_titled(ap, "aparencia", "Aparência")
        # — Agente — (Fase 5: responsabilidade/role)
        ag = page()
        ag.append(self._editor_agente_section(nid, applies))
        stack.add_titled(ag, "agente", "Agente")

        # — rodapé: Cancelar / Salvar —
        foot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        foot.set_halign(Gtk.Align.END)
        foot.set_margin_top(10)

        def do_save(_b=None):
            nm = name.get_text().strip()
            self.model.set_node_name(nid, nm or nid)  # persiste (abre igual fechou)
            fr = self.frames.get(nid)
            lbl = getattr(fr, "_title_lbl", None) if fr is not None else None
            if lbl is not None:
                lbl.set_text(f"  {nm or nid}  ")
            for fn in applies:  # aplica+persiste cada aba (Aparência etc.)
                fn()
            win.destroy()

        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda _b: win.destroy())
        save = Gtk.Button(label="Salvar")
        save.add_css_class("suggested-action")
        save.connect("clicked", do_save)
        name.connect("activate", do_save)
        foot.append(cancel)
        foot.append(save)
        box.append(foot)
        win.present()
        name.grab_focus()

    @staticmethod
    def _editor_section_label(text: str) -> Gtk.Widget:
        lb = Gtk.Label(label=text, xalign=0)
        lb.add_css_class("editor-section")
        return lb

    @staticmethod
    def _mono_font_filter() -> Gtk.Filter:
        """Filtro do FontDialog: só famílias MONOSPACE. Trata FontFamily E FontFace
        (o GTK4 avalia os dois) via Pango.FontFamily.is_monospace()."""
        def _is_mono(item):
            fam = item.get_family() if isinstance(item, Pango.FontFace) else item
            try:
                return fam.is_monospace()
            except Exception:
                return False
        return Gtk.CustomFilter.new(_is_mono)

    def _editor_font_section(self, nid: str, applies: list) -> Gtk.Widget:
        """Seção FONTE (Fase 1, Avançada): família+tamanho por terminal (FontDialog filtrado p/
        monospace), zoom de fonte (set_font_scale) e "padrão global". Transacional: aplica no
        Salvar via `applies`."""
        st = {"desc": self.model.node_cfg(nid, "font"), "scale": self._node_font_scale(nid)}
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self._editor_section_label("Fonte"))
        info = Gtk.Label(xalign=0)
        info.add_css_class("dim-label")
        preview = Gtk.Label(label="abc 012 →|←   $ ls -la", xalign=0)
        preview.add_css_class("term-font-preview")

        def refresh():
            d = st["desc"] or self.model.terminal_font()
            info.set_text(
                f"{d or 'monospace do sistema'}    ·    zoom {int(round(st['scale'] * 100))}%")
            try:  # preview na própria fonte (Pango attrs); se a API faltar, fica neutro
                attrs = Pango.AttrList()
                if d:
                    attrs.insert(Pango.attr_font_desc_new(Pango.FontDescription.from_string(d)))
                preview.set_attributes(attrs)
            except Exception:
                pass

        refresh()
        box.append(info)
        box.append(preview)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        sel = Gtk.Button(label="Selecionar…")

        def pick(_b):
            dlg = Gtk.FontDialog()
            dlg.set_filter(self._mono_font_filter())
            cur = st["desc"] or self.model.terminal_font()
            init = Pango.FontDescription.from_string(cur) if cur else None

            def done(d, res):
                try:
                    desc = d.choose_font_finish(res)
                except GLib.Error:
                    return  # cancelado
                if desc is not None:
                    st["desc"] = desc.to_string()
                    refresh()

            dlg.choose_font(self.win, init, None, done)

        sel.connect("clicked", pick)
        row.append(sel)
        reset = Gtk.Button(label="Padrão do sistema")
        reset.connect("clicked", lambda _b: (st.update(desc=""), refresh()))
        row.append(reset)

        def bump(delta):
            st["scale"] = max(self.FONT_SCALE_MIN, min(self.FONT_SCALE_MAX, st["scale"] + delta))
            refresh()

        minus = Gtk.Button(label="A−")
        minus.set_tooltip_text("diminuir fonte deste terminal")
        minus.connect("clicked", lambda _b: bump(-0.1))
        plus = Gtk.Button(label="A+")
        plus.set_tooltip_text("aumentar fonte deste terminal")
        plus.connect("clicked", lambda _b: bump(0.1))
        row.append(minus)
        row.append(plus)
        box.append(row)

        glob = Gtk.CheckButton(label="Definir como padrão global (terminais sem fonte própria)")
        box.append(glob)

        def apply():
            self.model.set_node_cfg(nid, "font", st["desc"])
            self.model.set_node_cfg(nid, "fontscale", f"{st['scale']:g}")
            if glob.get_active() and st["desc"]:
                self.model.set_terminal_font(st["desc"])
            self._apply_node_font(nid)
            if glob.get_active():
                self._apply_font_all()

        applies.append(apply)
        return box

    def _editor_color_section(self, nid: str, applies: list) -> Gtk.Widget:
        """Seção COR (Fase 1): accent por terminal (tint do cabeçalho). Reusa a paleta da nota
        (`.csw`/`.palsw-i`) + `Gtk.ColorDialog` p/ custom. Transacional: aplica no Salvar."""
        st = {"color": self.model.node_cfg(nid, "color")}
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self._editor_section_label("Cor"))
        grid = Gtk.Grid()  # Grid (não FlowBox): célula não estica o botão → swatch fica redondo
        grid.set_row_spacing(6)
        grid.set_column_spacing(6)
        per_row = 9
        swatches: list = []

        def mark():
            for b, hexc in swatches:
                if hexc == st["color"] and hexc:
                    b.add_css_class("csw-sel")
                else:
                    b.remove_css_class("csw-sel")

        def choose(hexc):
            st["color"] = hexc
            mark()

        none_b = Gtk.Button(label="∅")
        none_b.add_css_class("csw")
        none_b.set_halign(Gtk.Align.CENTER)
        none_b.set_valign(Gtk.Align.CENTER)
        none_b.set_tooltip_text("sem cor")
        none_b.connect("clicked", lambda _b: choose(""))
        swatches.append((none_b, ""))
        cells: list = [none_b]
        for i, hexc in enumerate(NOTE_PALETTE):
            sw = Gtk.Button()
            sw.set_has_frame(False)
            sw.add_css_class("csw")
            sw.add_css_class(f"palsw-{i}")
            sw.set_halign(Gtk.Align.CENTER)
            sw.set_valign(Gtk.Align.CENTER)
            sw.set_tooltip_text(hexc)
            sw.connect("clicked", lambda _b, c=hexc: choose(c))
            swatches.append((sw, hexc))
            cells.append(sw)
        for idx, w in enumerate(cells):
            grid.attach(w, idx % per_row, idx // per_row, 1, 1)
        box.append(grid)

        more = Gtk.Button(label="🎨 Mais cores…")
        more.set_halign(Gtk.Align.START)

        def pick_custom(_b):
            dlg = Gtk.ColorDialog()
            init = Gdk.RGBA()
            init.parse(st["color"] or NOTE_HEX_DEFAULT)

            def done(d, res):
                try:
                    rgba = d.choose_rgba_finish(res)
                except GLib.Error:
                    return
                if rgba is not None:
                    rr, gg, bb = (round(rgba.red * 255), round(rgba.green * 255),
                                  round(rgba.blue * 255))
                    st["color"] = f"#{rr:02x}{gg:02x}{bb:02x}"
                    mark()

            dlg.choose_rgba(self.win, init, None, done)

        more.connect("clicked", pick_custom)
        box.append(more)
        mark()

        def apply():
            self.model.set_node_cfg(nid, "color", st["color"])
            self._apply_node_color(nid, st["color"])

        applies.append(apply)
        return box

    def _search_picker(self, label, entries, render, pick) -> Gtk.Widget:
        """MenuButton com popover de BUSCA (genérico: serve ícone e emoji). `entries` = lista de
        (key, texto_busca); `render(key)` → filho do botão; `pick(key)` → ação ao clicar.
        Popula ao abrir (lazy) e ao digitar; limita o render p/ a tela pequena."""
        mb = Gtk.MenuButton(label=label)
        mb.set_halign(Gtk.Align.START)
        pop = Gtk.Popover()
        pv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        pv.set_size_request(330, -1)
        search = Gtk.SearchEntry()
        search.set_placeholder_text("buscar (em inglês: ex. rocket, git, server)")
        pv.append(search)
        scr = Gtk.ScrolledWindow()
        scr.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scr.set_min_content_height(220)
        scr.set_max_content_height(220)
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(10)
        flow.set_homogeneous(True)
        scr.set_child(flow)
        pv.append(scr)
        pop.set_child(pv)
        mb.set_popover(pop)

        def repop(*_):
            child = flow.get_first_child()
            while child is not None:
                flow.remove(child)
                child = flow.get_first_child()
            q = search.get_text().strip().lower()
            shown = 0
            for key, text in (entries() if callable(entries) else entries):  # callable = lista viva
                if q and q not in text:
                    continue
                b = Gtk.Button()
                b.add_css_class("ico-btn")
                b.set_has_frame(False)
                b.set_child(render(key))
                b.set_tooltip_text(key)
                b.connect("clicked", lambda _b, k=key: (pop.popdown(), pick(k)))
                flow.insert(b, -1)
                shown += 1
                if shown >= 250:  # limite por render (perf na tela pequena)
                    break

        search.connect("search-changed", repop)
        mb.connect("notify::active", lambda *_: repop() if mb.get_active() else None)
        return mb

    def _editor_icon_section(self, nid: str, applies: list) -> Gtk.Widget:
        """Seção ÍCONE (Fase 1): grid dos 24 ícones bundlados (Lucide) + emoji custom + sem ícone.
        Transacional: aplica no Salvar (node_cfg 'icon' = 'maestro-<n>' | 'emoji:<e>' | '')."""
        st = {"icon": self.model.node_cfg(nid, "icon")}
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self._editor_section_label("Ícone"))
        # preview "Atual:" — dá feedback do que está selecionado (ícone do grid OU emoji OU nenhum)
        prev_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        prev_box.append(Gtk.Label(label="Atual:"))
        prev_holder = Gtk.Box()
        prev_box.append(prev_holder)
        box.append(prev_box)
        grid = Gtk.Grid()
        grid.set_row_spacing(4)
        grid.set_column_spacing(4)
        per_row = 13  # janela larga: 24 ícones em ~2 linhas (menos altura)
        btns: list = []

        def set_preview():
            child = prev_holder.get_first_child()
            if child is not None:
                prev_holder.remove(child)
            v = st["icon"]
            if not v:
                w: Gtk.Widget = Gtk.Label(label="nenhum")
                w.add_css_class("dim-label")
            elif v.startswith("emoji:"):
                w = Gtk.Label(label=v[6:])
            else:
                w = Gtk.Image.new_from_icon_name(v)
                w.set_pixel_size(20)
            prev_holder.append(w)

        def mark():
            for b, val in btns:
                if val == st["icon"] and val:
                    b.add_css_class("ico-sel")
                else:
                    b.remove_css_class("ico-sel")
            set_preview()

        def choose(val):
            st["icon"] = val
            mark()

        none_b = Gtk.Button(label="∅")
        none_b.add_css_class("ico-btn")
        none_b.set_tooltip_text("sem ícone")
        none_b.connect("clicked", lambda _b: choose(""))
        cells: list = [(none_b, "")]
        for n in TERM_ICON_NAMES:
            b = Gtk.Button()
            b.set_has_frame(False)
            b.add_css_class("ico-btn")
            img = Gtk.Image.new_from_icon_name(f"maestro-{n}")
            img.set_pixel_size(20)
            b.set_child(img)
            b.set_tooltip_text(n)
            val = f"maestro-{n}"
            b.connect("clicked", lambda _b, v=val: choose(v))
            cells.append((b, val))
        for i, (b, val) in enumerate(cells):
            btns.append((b, val))
            grid.attach(b, i % per_row, i // per_row, 1, 1)
        box.append(grid)

        # 🔎 Mais ícones: busca nos 256 ícones dev bundlados (nome + tags)
        def _icon_img(n):
            im = Gtk.Image.new_from_icon_name(f"maestro-{n}")
            im.set_pixel_size(20)
            return im

        box.append(self._search_picker(
            "🔎 Mais ícones…", icon_catalog(), _icon_img,
            lambda n: choose(f"maestro-{n}")))

        # emoji custom: GRADE PRÓPRIA (o Gtk.EmojiChooser abre vazio neste device — sem
        # en.gresource p/ en_US). Cada emoji entra em `btns` p/ o destaque do mark() valer também.
        elbl = Gtk.Label(label="Emoji:", xalign=0)
        elbl.add_css_class("dim-label")
        box.append(elbl)
        egrid = Gtk.Grid()
        egrid.set_row_spacing(4)
        egrid.set_column_spacing(4)
        for i, e in enumerate(TERM_EMOJIS):
            eb = Gtk.Button(label=e)
            eb.add_css_class("ico-btn")
            eval_ = f"emoji:{e}"
            eb.connect("clicked", lambda _b, v=eval_: choose(v))
            btns.append((eb, eval_))
            egrid.attach(eb, i % per_row, i // per_row, 1, 1)
        box.append(egrid)

        # 🔎 Mais emojis: busca em TODOS (catálogo via unicodedata)
        box.append(self._search_picker(
            "🔎 Mais emojis…", emoji_catalog(), lambda e: Gtk.Label(label=e),
            lambda e: choose(f"emoji:{e}")))
        mark()

        def apply():
            self.model.set_node_cfg(nid, "icon", st["icon"])
            self._apply_node_icon(nid, st["icon"])

        applies.append(apply)
        return box

    @staticmethod
    def _paint_theme_swatch(cr, w, h, th) -> None:
        """Desenha um swatch do tema: fundo bg + 'Ab' no fg + 6 cores ANSI."""
        bg = _rgba(th["bg"])
        cr.set_source_rgb(bg.red, bg.green, bg.blue)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        for i, c in enumerate(th["palette"][1:7]):
            rc = _rgba(c)
            cr.set_source_rgb(rc.red, rc.green, rc.blue)
            cr.rectangle(3 + i * 5, h - 6, 4, 4)
            cr.fill()
        fg = _rgba(th["fg"])
        cr.set_source_rgb(fg.red, fg.green, fg.blue)
        cr.move_to(4, 14)
        cr.set_font_size(12)
        cr.show_text("Ab")

    def _theme_swatch(self, name: str) -> Gtk.Widget:
        """DrawingArea com o swatch de um tema (usado no picker do editor e da FAB)."""
        da = Gtk.DrawingArea()
        da.set_size_request(44, 24)
        da.set_draw_func(
            lambda _a, cr, w, h, n=name: self._paint_theme_swatch(cr, w, h, get_theme(n)))
        return da

    def _theme_entries(self) -> list:
        """(nome, texto_busca) de todos os temas — busca por nome + 'dark'/'light'."""
        return [(n, n.lower() + (" dark" if theme_is_dark(n) else " light"))
                for n in theme_names()]

    @staticmethod
    def _accel_label(accel: str) -> str:
        if not accel:
            return "(nenhum)"
        ok, kv, mods = Gtk.accelerator_parse(accel)
        return Gtk.accelerator_get_label(kv, mods) if ok else accel

    def _editor_detalhes_section(self, nid: str, applies: list) -> Gtk.Widget:
        """Detalhes (Fase 3, Avançada): Comando, Diretório, Variáveis (env), Atalho + Reiniciar.
        Auto-respawn no Salvar se comando/cwd/env mudarem (respawn no mesmo widget)."""
        init = {k: self.model.node_cfg(nid, k) for k in ("command", "cwd", "env", "shortcut")}
        st = {"shortcut": init["shortcut"]}
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        box.append(self._editor_section_label("Comando"))
        cmd = Gtk.Entry()
        cmd.set_placeholder_text("vazio = shell/agente padrão (ex.: htop, python3)")
        cmd.set_text(init["command"])
        box.append(cmd)

        box.append(self._editor_section_label("Diretório de Trabalho"))
        drow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        cwd = Gtk.Entry()
        cwd.set_hexpand(True)
        cwd.set_placeholder_text("padrão (home)")
        cwd.set_text(init["cwd"])
        proc = Gtk.Button(label="Procurar…")

        def pick_dir(_b):
            dlg = Gtk.FileDialog()

            def done(d, res):
                try:
                    folder = d.select_folder_finish(res)
                except GLib.Error:
                    return
                if folder is not None and folder.get_path():
                    cwd.set_text(folder.get_path())

            dlg.select_folder(self.win, None, done)

        proc.connect("clicked", pick_dir)
        drow.append(cwd)
        drow.append(proc)
        box.append(drow)

        box.append(self._editor_section_label("Variáveis (KEY=VALUE, uma por linha)"))
        env_sc = Gtk.ScrolledWindow()
        env_sc.set_min_content_height(54)
        env_sc.set_max_content_height(90)
        env_tv = Gtk.TextView()
        env_tv.get_buffer().set_text(init["env"])
        env_sc.set_child(env_tv)
        box.append(env_sc)

        box.append(self._editor_section_label("Atalho (foco)"))
        srow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        slabel = Gtk.Label(xalign=0)
        slabel.add_css_class("dim-label")

        def refresh_sc():
            slabel.set_text(self._accel_label(st["shortcut"]))

        refresh_sc()
        sset = Gtk.Button(label="Definir…")
        sset.connect("clicked", lambda _b: self._capture_shortcut(
            lambda a: (st.update(shortcut=a), refresh_sc())))
        sclr = Gtk.Button(label="Limpar")
        sclr.connect("clicked", lambda _b: (st.update(shortcut=""), refresh_sc()))
        srow.append(slabel)
        srow.append(sset)
        srow.append(sclr)
        box.append(srow)

        def _env_text():
            b = env_tv.get_buffer()
            return b.get_text(b.get_start_iter(), b.get_end_iter(), False)

        def _persist():
            self.model.set_node_cfg(nid, "command", cmd.get_text().strip())
            self.model.set_node_cfg(nid, "cwd", cwd.get_text().strip())
            self.model.set_node_cfg(nid, "env", _env_text())
            self.model.set_node_cfg(nid, "shortcut", st["shortcut"])

        restart = Gtk.Button(label="↻ Reiniciar terminal (aplicar comando/cwd/env)")
        restart.set_halign(Gtk.Align.START)
        restart.connect("clicked", lambda _b: (_persist(), self._respawn_node(nid)))
        box.append(restart)

        def apply():
            _persist()
            if any(self.model.node_cfg(nid, k) != init[k] for k in ("command", "cwd", "env")):
                self._respawn_node(nid)  # auto-respawn se comando/cwd/env mudaram

        applies.append(apply)
        return box

    def _editor_monitor_section(self, nid: str, applies: list) -> Gtk.Widget:
        """Monitorar atividade (Fase 4): toggle + tempo de quietude. Avisa (dot + notificação +
        som) quando o terminal para de produzir output, estando fora de foco."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        chk = Gtk.CheckButton(label="Monitorar atividade")
        chk.set_active(self._monitor_default_on(nid))  # reflete o EFETIVO (padrão-ON p/ agente)
        box.append(chk)
        hint = Gtk.Label(
            label="Avisa (dot 'aguardando' + notificação) quando o terminal PARA de produzir "
                  "output, estando fora de foco. Ignora 'pensando' (TUI ocupada).", xalign=0)
        hint.add_css_class("dim-label")
        hint.set_wrap(True)
        box.append(hint)
        trow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        trow.append(Gtk.Label(label="Tempo de quietude (s):"))
        secs = Gtk.Entry()
        secs.set_max_width_chars(5)
        secs.set_text(self.model.node_cfg(nid, "monitor_ms") or "1.5")
        trow.append(secs)
        box.append(trow)
        snd = Gtk.CheckButton(label="Tocar som ao avisar (padrão: só dot visual)")
        snd.set_active(bool(self.model.node_cfg(nid, "monitor_sound")))
        box.append(snd)

        def apply():
            on = chk.get_active()
            # tri-estado: ao SALVAR vira explícito ("1"/"0") — sai do default-por-tipo
            self.model.set_node_cfg(nid, "monitor", "1" if on else "0")
            self.model.set_node_cfg(nid, "monitor_ms", secs.get_text().strip() or "1.5")
            self.model.set_node_cfg(nid, "monitor_sound", "1" if snd.get_active() else "")
            self._set_node_monitor(nid, on)

        applies.append(apply)
        return box

    def _editor_maestro_section(self, nid: str, applies: list) -> Gtk.Widget:
        """Maestro mode (Fase 6): toggle que promove o agente a MANAGER (recruta/conecta/dispensa
        via `maestri …`). Vale p/ nó-AGENTE; reinicia p/ a IA ler a manager-skill."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        chk = Gtk.CheckButton(label="Maestro mode (gerenciar uma equipe)")
        chk.set_active(bool(self.model.node_cfg(nid, "maestro")))
        box.append(chk)
        hint = Gtk.Label(
            label="Promove este AGENTE a manager: ele pode `maestri recruit/list/reassign/wire/"
                  "dismiss` p/ criar agentes conectados abaixo e atribuir papéis.", xalign=0)
        hint.add_css_class("dim-label")
        hint.set_wrap(True)
        box.append(hint)

        def apply():
            on = chk.get_active()
            was = bool(self.model.node_cfg(nid, "maestro"))
            self.model.set_node_cfg(nid, "maestro", "1" if on else "")
            self._apply_node_maestro(nid)
            if on != was and self._role_targets(nid):  # nó-agente → reinicia p/ ler a skill
                self._rebuild_agent_argv(nid)  # Fase 1: relança com/sem auto-aprovação
                self._respawn_node(nid)

        applies.append(apply)
        return box

    def _editor_autoapprove_section(self, nid: str, applies: list) -> Gtk.Widget:
        """Permissão total (Fase 2): o CLI deste agente roda comandos SEM pedir permissão a
        cada um. O confinamento REAL continua sendo o bwrap (ADR-6) — isto só remove os
        prompts. Vale p/ nó-AGENTE; reinicia p/ aplicar."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        chk = Gtk.CheckButton(label="Permissão total (não pedir permissão a cada comando)")
        chk.set_active(bool(self.model.node_cfg(nid, "autoapprove")))
        box.append(chk)
        hint = Gtk.Label(
            label="Roda o claude/codex sem os prompts de aprovação. O confinamento continua "
                  "sendo o sandbox (bwrap) — isto só tira as confirmações. Reinicia o agente.",
            xalign=0)
        hint.add_css_class("dim-label")
        hint.set_wrap(True)
        box.append(hint)

        def apply():
            on = chk.get_active()
            was = bool(self.model.node_cfg(nid, "autoapprove"))
            self.model.set_node_cfg(nid, "autoapprove", "1" if on else "")
            if on != was and self._agent_base(nid):  # nó-agente → relança com/sem as flags
                self._rebuild_agent_argv(nid)
                self._respawn_node(nid)

        applies.append(apply)
        return box

    @staticmethod
    def _fill_rect(cr, w, h, hexc) -> None:
        r, g, b = _hex_to_rgb(hexc)
        cr.set_source_rgb(r / 255, g / 255, b / 255)
        cr.rectangle(0, 0, w, h)
        cr.fill()

    def _color_picker_row(self, win, initial_hex: str) -> tuple[Gtk.Box, dict]:
        """Linha 'Cor:' com swatch + botão 'Escolher…' (`Gtk.ColorDialog`) — reusada por
        `_role_edit_dialog` e `_team_group_edit_dialog`. Devolve (row, color); `color["hex"]`
        é atualizado ao vivo pelo picker — ler no Salvar do chamador."""
        crow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        crow.append(Gtk.Label(label="Cor:"))
        color = {"hex": initial_hex}
        sw = Gtk.DrawingArea()
        sw.set_size_request(28, 20)
        sw.set_draw_func(lambda _a, cr, w, h: self._fill_rect(cr, w, h, color["hex"]))
        pick = Gtk.Button(label="Escolher…")

        def pickc(_b):
            dlg = Gtk.ColorDialog()
            init = Gdk.RGBA()
            init.parse(color["hex"])

            def done(d, res):
                try:
                    rgba = d.choose_rgba_finish(res)
                except GLib.Error:
                    return
                color["hex"] = (f"#{round(rgba.red * 255):02x}{round(rgba.green * 255):02x}"
                                f"{round(rgba.blue * 255):02x}")
                sw.queue_draw()

            dlg.choose_rgba(win, init, None, done)

        pick.connect("clicked", pickc)
        crow.append(sw)
        crow.append(pick)
        return crow, color

    def _role_edit_dialog(self, role, on_saved) -> None:
        """Cria/edita um role (name, cor, prompt) na biblioteca. role=None → novo."""
        win, box = self._dialog("Editar role" if role else "Novo role")
        win.set_default_size(440, -1)
        box.append(Gtk.Label(label="Nome", xalign=0))
        name = Gtk.Entry()
        name.set_placeholder_text("ex.: backend, reviewer…")
        if role:
            name.set_text(role.name)
        box.append(name)
        crow, color = self._color_picker_row(win, role.badge() if role else "#3b82f6")
        box.append(crow)
        box.append(Gtk.Label(label="Instruções (prompt)", xalign=0))
        psc = Gtk.ScrolledWindow()
        psc.set_min_content_height(120)
        ptv = Gtk.TextView()
        ptv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        if role:
            ptv.get_buffer().set_text(role.instruction)
        psc.set_child(ptv)
        box.append(psc)
        foot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        foot.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda _b: win.destroy())
        save = Gtk.Button(label="Salvar")
        save.add_css_class("suggested-action")

        def do_save(_b):
            nm = name.get_text().strip()
            if not nm:
                return
            b = ptv.get_buffer()
            prompt = b.get_text(b.get_start_iter(), b.get_end_iter(), False)
            roles = [r for r in self._roles() if r.name != nm]
            roles.append(Role(nm, "", prompt, color["hex"]))
            self._save_roles(roles)
            win.destroy()
            on_saved(nm)

        save.connect("clicked", do_save)
        foot.append(cancel)
        foot.append(save)
        box.append(foot)
        win.present()
        name.grab_focus()

    def _editor_agente_section(self, nid: str, applies: list) -> Gtk.Widget:
        """Aba Agente (Fase 5): atribuir/buscar role (biblioteca), criar/editar, Descobrir (varre
        o cwd), Remover. Aplica no Salvar (node_cfg 'role' + _apply_node_role)."""
        st = {"role": self.model.node_cfg(nid, "role")}
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.append(self._editor_section_label("Responsabilidade (role)"))
        cur = Gtk.Label(xalign=0)
        cur.add_css_class("dim-label")

        def refresh():
            r = next((x for x in self._roles() if x.name == st["role"]), None)
            cur.set_text(f"Atual: {r.name}" if r else "Atual: (nenhum)")

        box.append(cur)

        def role_entries():
            return [(r.name, (r.name + " " + r.instruction).lower()) for r in self._roles()]

        def role_render(name):
            r = next((x for x in self._roles() if x.name == name), None)
            col = r.badge() if r else "#888888"
            bx = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            da = Gtk.DrawingArea()
            da.set_size_request(16, 16)
            da.set_draw_func(lambda _a, cr, w, h, c=col: self._fill_rect(cr, w, h, c))
            bx.append(da)
            bx.append(Gtk.Label(label=name))
            return bx

        def assign(name):
            st["role"] = name
            refresh()

        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row1.append(self._search_picker("🔎 Atribuir…", role_entries, role_render, assign))
        rem = Gtk.Button(label="Remover")
        rem.connect("clicked", lambda _b: assign(""))
        row1.append(rem)
        box.append(row1)

        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        new = Gtk.Button(label="Novo role…")
        new.connect("clicked", lambda _b: self._role_edit_dialog(None, assign))
        edit = Gtk.Button(label="Editar…")

        def do_edit(_b):
            r = next((x for x in self._roles() if x.name == st["role"]), None)
            if r is not None:
                self._role_edit_dialog(r, assign)

        edit.connect("clicked", do_edit)
        disc = Gtk.Button(label="🔎 Descobrir")
        disc_lbl = Gtk.Label(xalign=0)
        disc_lbl.add_css_class("dim-label")

        def do_discover(_b):
            cwd = self.model.node_cfg(nid, "cwd") or str(Path.home())
            found = discover_roles(cwd)
            if found:
                lib = {r.name: r for r in self._roles()}
                for r in found:
                    lib[r.name] = r
                self._save_roles(list(lib.values()))
            disc_lbl.set_text(
                f"{len(found)} role(s) importado(s) do cwd" if found else "nenhum role no cwd")

        disc.connect("clicked", do_discover)
        row2.append(new)
        row2.append(edit)
        row2.append(disc)
        box.append(row2)
        box.append(disc_lbl)

        refresh()

        def apply():
            changed = self.model.node_cfg(nid, "role") != st["role"]
            self.model.set_node_cfg(nid, "role", st["role"])
            self._apply_node_role(nid)  # escreve os arquivos de instrução + accent
            if changed and self._role_targets(nid):  # M4: só nó-AGENTE reinicia (shell não injeta)
                self._respawn_node(nid)  # reinicia → a IA relê o role no próximo start

        applies.append(apply)
        return box

    def _editor_theme_section(self, nid: str, applies: list) -> Gtk.Widget:
        """Seção TEMA (Fase 2): seleciona um tema; o toggle GLOBAL decide o alcance — ligado =
        aplica a TODOS (vira o tema global); desligado = só ESTE terminal. "Seguir o global" tira
        o tema próprio (volta ao padrão). Busca nos ~70 esquemas. Transacional: aplica no Salvar."""
        cur = self.model.node_cfg(nid, "theme")  # "" = já segue o global
        st = {"theme": cur or self.model.terminal_theme(), "follow": cur == "", "glob": False}
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self._editor_section_label("Tema"))

        def resolved():
            base = self.model.terminal_theme() if st["follow"] else st["theme"]
            return self._resolve_theme(base)

        prow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        prow.append(Gtk.Label(label="Atual:"))
        pswatch = Gtk.DrawingArea()
        pswatch.set_size_request(42, 22)
        pswatch.set_draw_func(
            lambda _a, cr, w, h: self._paint_theme_swatch(cr, w, h, get_theme(resolved())))
        plabel = Gtk.Label(xalign=0)
        plabel.add_css_class("dim-label")
        prow.append(pswatch)
        prow.append(plabel)
        box.append(prow)

        opts = [("__follow__", "Seguir o global"), ("system", "Sistema"),
                ("dark", "Escuro"), ("light", "Claro")]
        btns: list = []
        gcheck = Gtk.CheckButton(label="Aplicar a TODOS os terminais (global)")

        def mark():
            selnow = "__follow__" if st["follow"] else (
                st["theme"] if st["theme"] in ("system", "dark", "light") else None)
            for b, val in btns:
                if val == selnow:
                    b.add_css_class("ico-sel")
                else:
                    b.remove_css_class("ico-sel")
            gcheck.set_sensitive(not st["follow"])
            if st["follow"]:
                scope = "seguindo o global"
            else:
                scope = "→ global (todos)" if st["glob"] else "só este terminal"
            disp = "Global" if st["follow"] else dict(opts).get(st["theme"], st["theme"])
            plabel.set_text(f"{disp} · {scope}  ({resolved()})")
            pswatch.queue_draw()

        def choose(v):
            if v == "__follow__":
                st["follow"] = True
            else:
                st["follow"] = False
                st["theme"] = v
            mark()

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for val, label in opts:
            b = Gtk.Button(label=label)
            b.add_css_class("ico-btn")
            b.connect("clicked", lambda _b, v=val: choose(v))
            btns.append((b, val))
            row.append(b)
        box.append(row)

        box.append(self._search_picker(
            "🔎 Mais temas…", self._theme_entries(), self._theme_swatch, choose))
        gcheck.connect("toggled", lambda b: (st.update(glob=b.get_active()), mark()))
        box.append(gcheck)
        mark()

        def apply():
            if st["follow"]:
                self.model.set_node_cfg(nid, "theme", "")  # tira o tema próprio → segue o global
                self._apply_node_theme(nid)
            elif st["glob"]:  # vira o tema GLOBAL (todos os terminais sem override)
                self.model.set_terminal_theme(self._resolve_theme(st["theme"]))
                self.model.set_node_cfg(nid, "theme", "")  # este também segue o novo global
                self._apply_theme()
            else:  # só ESTE terminal
                self.model.set_node_cfg(nid, "theme", st["theme"])
                self._apply_node_theme(nid)

        applies.append(apply)
        return box

    def _ctx_connect_btn(self) -> Gtk.Widget:
        """Botão PADRÃO de toda cápsula contextual: puxa um cabo A PARTIR do elemento
        selecionado. Ao clicar, o cabo segue o cursor; o próximo clique em qualquer área de
        outro nó/nota fecha a conexão (arquitetura: conexão é ação comum a todo elemento)."""
        b = self._fab_button(
            "maestro-connect-symbolic", "🔗",
            "Conectar: puxa um cabo deste elemento até outro", self._ctx_start_connect)
        b.add_css_class("note-ctx-btn")
        return b

    def _ctx_start_connect(self) -> None:
        """Inicia a conexão já com o elemento selecionado como ORIGEM (pula o '1º clique')."""
        sel = self._selected
        if sel is None or self.edges is None:
            return
        self._connect_mode = True
        self._connect_oneshot = True  # cápsula = uma conexão; depois volta ao normal
        btn = getattr(self, "_connect_btn", None)
        if btn is not None and not btn.get_active():
            btn.set_active(True)  # espelha no FAB (dispara _toggle_connect; mantém o src)
        self._connect_src = (sel[0], sel[1])  # ORIGEM já escolhida = o elemento da cápsula
        if sel[0] == "node":
            self.set_node_state(sel[1], "busy")  # realça a origem pendente
        self._connect_cursor = None
        self._preview_rope = None
        self._wake_cables()  # liga o tick p/ a física do cabo-fantasma rodar
        self._update_hintbar()

    def _sel_nid(self) -> str | None:
        """id do nó-terminal selecionado, ou None (helper das ações da pílula do nó)."""
        sel = self._selected
        return sel[1] if sel and sel[0] == "node" else None

    def _ctx_rename_node(self) -> None:
        nid = self._sel_nid()
        if nid is not None:
            self._rename_node(nid)

    def _ctx_focus_node(self) -> None:
        nid = self._sel_nid()
        if nid is not None:
            self._focus_node(nid)

    def _ctx_unload_node(self) -> None:
        nid = self._sel_nid()
        if nid is None:
            return
        if self._node_unloaded(nid):  # Bloco C: ⏏ num nó já descarregado = retomar
            self._reload_node(nid)
        else:
            self._confirm_unload(nid)

    def _ctx_close_node(self) -> None:
        nid = self._sel_nid()
        if nid is not None:
            self._select(None)  # limpa a seleção (esconde a pílula) antes de remover o frame
            self._close_node(nid)

    def _update_ctx(self) -> None:
        """Atualiza TODAS as pílulas contextuais conforme o elemento selecionado."""
        self._update_note_ctx()
        bar = getattr(self, "_node_ctx_bar", None)
        if bar is not None:
            bar.set_visible(bool(self._selected) and self._selected[0] == "node")

    def _draw_cur_color(self, _area, cr, w, h) -> None:
        """Desenha a bolinha da cor ATUAL no botão de cor da pílula."""
        hexc = getattr(self, "_cur_color_hex", NOTE_HEX_DEFAULT)
        r, g, b = _hex_to_rgb(hexc)
        rad = min(w, h) / 2 - 1
        cr.arc(w / 2, h / 2, rad, 0, 6.283185307179586)
        cr.set_source_rgb(r / 255, g / 255, b / 255)
        cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, 0.35)
        cr.set_line_width(1)
        cr.stroke()

    def _update_ctx_color_swatch(self) -> None:
        sw = getattr(self, "_ctx_color_swatch", None)
        if sw is None:
            return
        frame = self._ctx_note_frame()
        if frame is not None:
            self._cur_color_hex = self._note_colors.get(frame._note_id, NOTE_HEX_DEFAULT)
        sw.queue_draw()

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
        dot = Gtk.Image.new_from_icon_name(_STATE_ICON["idle"])  # estado: ÍCONE Lucide (UI-1)
        dot.set_pixel_size(13)
        dot.add_css_class("state-dot")
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
        cost = Gtk.Label(label="")  # F1: custo/tokens acumulados do agente (medidor lean)
        cost.add_css_class("node-cost")  # mesmo padrão discreto do .node-status (10px)
        head._cost = cost
        head.append(cost)
        ram = Gtk.Label(label="")  # Bloco D: RAM da árvore do nó (PSS, via worker thread)
        ram.add_css_class("node-ram")  # mesmo padrão discreto do .node-cost
        head._ram = ram
        head.append(ram)
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
        frame._base_argv = argv  # argv "natural" (shell/agente) p/ o respawn voltar a ele
        term = self._make_node_term(nid, argv)  # comando/cwd/env por-nó (Fase 3)
        frame._term = term  # ref p/ remover de self.terms ao fechar o nó
        term._respawn_state = "idle"  # state machine do respawn (hardening defensivo)
        term._respawn_pending = False
        term._respawn_force_src = None
        term._destroyed = False
        term.connect("child-exited", self._on_child_exited, nid)  # PERSISTENTE (zera o PID)
        fc = Gtk.EventControllerFocus()
        fc.connect("enter", lambda _c, n=nid: self._on_term_focus(n))  # clicar/focar = selecionar
        fc.connect("leave", lambda _c, n=nid: self._on_term_unfocus(n))  # monitorar só desfocado
        term.add_controller(fc)  # rastreia o terminal em foco (fechar via Ctrl+Shift+W)
        # unload (Bloco C): clique no TERMINAL de um nó descarregado = retomar. No terminal
        # (não no frame): o frame inclui o header de arrasto — reposicionar o card pelo
        # header não pode ressuscitar o nó. _reload_node é no-op se não estiver descarregado.
        rl = Gtk.GestureClick()
        rl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        rl.connect("pressed", lambda _g, _n, _x, _y, n=nid: self._reload_node(n))
        term.add_controller(rl)
        # seleção em QUALQUER clique no card (fase CAPTURE = antes do VTE consumir; não claima,
        # então o terminal/arraste seguem). Cobre re-clicar um card já focado (foco-enter só
        # dispara em MUDANÇA de foco, então sozinho falhava ao re-selecionar após clicar fora).
        selclick = Gtk.GestureClick()
        selclick.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        selclick.connect("pressed", self._on_frame_press, "node", nid)
        frame.add_controller(selclick)
        sz = self.model.node_size(nid, (BASE_W, BASE_H))  # tamanho por nó (persistido)
        self._node_size[nid] = sz
        term.set_hexpand(True)
        term.set_vexpand(True)
        # tamanho NATURAL (zoom é por transform); mudar isto reflui o PTY (cols/linhas)
        term.set_size_request(int(sz[0]), int(sz[1]))
        self.terms.append(term)
        self.frames[nid] = frame  # registra antes de aplicar a fonte (lookup em _apply_node_font)
        if self._node_unloaded(nid):  # nasceu descarregado (Bloco C): dot/status refletem já
            self.set_node_state(nid, "idle")  # camada de vista (idle+flag → eject)
        self._apply_node_font(nid)  # fonte por-nó/global + escala (persistido)
        ncolor = self.model.node_cfg(nid, "color")  # cor accent persistida (Fase 1)
        if ncolor:
            self._apply_node_color(nid, ncolor)
        nicon = self.model.node_cfg(nid, "icon")  # ícone persistido (Fase 1)
        if nicon:
            self._apply_node_icon(nid, nicon)
        self._apply_node_theme(nid)  # tema por-nó (override) ou global — Fase 2
        self._apply_node_role(nid)  # role (Fase 5): accent + sidecar (injeção é no spawn do agente)
        self._apply_node_maestro(nid)  # Maestro mode (Fase 6): injeta a manager-skill se ligado
        self._sock_register(nid, argv)  # ADR-17: listener do socket só p/ nó de agente (bwrap)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(head)
        box.append(term)
        # resize é detectado no nível do CANVAS (faixa em volta da borda) — sem widgets aqui
        frame.set_child(box)
        bx, by = self.model.position(nid, default)
        self._base_pos[nid] = (bx, by)
        self.plane.put(frame, 0, 0)  # posição real vem no transform (_place)
        self._place(frame, (bx, by), self.model.zoom())
        self.frames[nid] = frame
        self.order.append(nid)
        if not self.model.node_cfg(nid, "shortcut"):  # atalho automático Ctrl+<n> (editável)
            auto = self._auto_shortcut(nid)
            if auto:
                self.model.set_node_cfg(nid, "shortcut", auto)
        if self._monitor_default_on(nid):  # monitor de atividade (Fase 4): padrão-ON p/ agente
            self._set_node_monitor(nid, True)
        self._refresh_node_cost(nid)  # F1: mostra o custo/tokens acumulado do agente no header
        self._renumber_nodes()  # atualiza os números de posição (Ctrl+Shift+N) [A.2]
        self._mm_refresh()  # C1: novo nó aparece no minimapa
        self._autofit_all_groups()  # C2: se o nó nasceu dentro de um grupo, ele abraça

    def _place(self, child, base, z) -> None:
        """Posiciona+escala o child: tela = base*zoom + câmera (canvas infinito)."""
        px, py = to_display(base, z)
        camx, camy = self._cam
        self.plane.set_child_transform(child, _plane_xform(px + camx, py + camy, z))

    # (arrastar nó: agora via o gesto do PLANO — ver _pan_begin/_pan_update/_pan_end)

    # -- redimensionar nó/nota pelo CANVAS (faixa em volta da borda; estável, sem widgets) --
    def _resize_edge_at(self, x, y):
        """(kind, id, edges) se o cursor está na FAIXA (±RESIZE_BAND px) da borda do card
        SELECIONADO (nó/nota), senão None. x,y em coords do plano (= tela estável)."""
        sel = self._selected
        if sel is None or sel[0] not in ("node", "note"):
            return None
        kind, tid = sel
        frame = self.frames.get(tid) if kind == "node" else self.note_frames.get(tid)
        if frame is None:
            return None
        ok, r = frame.compute_bounds(self.plane)  # retângulo do card em coords-plano
        if not ok:
            return None
        left, top = r.origin.x, r.origin.y
        right, bottom = left + r.size.width, top + r.size.height
        b = RESIZE_BAND
        if not (left - b <= x <= right + b and top - b <= y <= bottom + b):
            return None
        edges = ""
        if abs(y - top) <= b:
            edges += "n"
        elif abs(y - bottom) <= b:
            edges += "s"
        if abs(x - left) <= b:
            edges += "w"
        elif abs(x - right) <= b:
            edges += "e"
        return (kind, tid, edges) if edges else None

    def _update_resize_cursor(self, x, y) -> None:
        """Cursor de resize quando o ponteiro entra na faixa da borda (senão limpa).
        Usa o nome CSS com fallback pro nome legado X11 (temas de cursor incompletos)."""
        rz = self._resize_edge_at(x, y)
        names = _RESIZE_CURSOR.get(rz[2]) if rz is not None else None
        if names is None:
            self.plane.set_cursor(None)
            return
        css, legacy = names
        cur = Gdk.Cursor.new_from_name(css, Gdk.Cursor.new_from_name(legacy, None))
        self.plane.set_cursor(cur)

    @staticmethod
    def _resize_rect(origin, dx, dy, edges, min_w, min_h):
        """Novo (x,y,w,h) em unidades-base ao arrastar `edges` (n/s/e/w). Borda oposta fica
        ancorada: arrastar W/N muda tamanho E posição; E/S só muda tamanho. Respeita o piso."""
        x0, y0, w0, h0 = origin
        w1 = w0 + dx if "e" in edges else (w0 - dx if "w" in edges else w0)
        h1 = h0 + dy if "s" in edges else (h0 - dy if "n" in edges else h0)
        w1 = max(min_w, w1)
        h1 = max(min_h, h1)
        x1 = x0 + (w0 - w1) if "w" in edges else x0  # ancora a borda direita
        y1 = y0 + (h0 - h1) if "n" in edges else y0  # ancora a borda inferior
        return x1, y1, w1, h1

    def _resize_min(self, kind):
        return (MIN_NODE_W, MIN_NODE_H) if kind == "node" else (MIN_NOTE_W, MIN_NOTE_H)

    def _item_resize_origin(self, kind, tid):
        """(x, y, w, h) base do card: posição + tamanho do terminal (nó) / corpo (nota)."""
        if kind == "node":
            x, y = self._base_pos.get(tid, (0.0, 0.0))
            w, h = self._node_size.get(tid, (BASE_W, BASE_H))
        else:
            frame = self.note_frames.get(tid)
            w, h = frame._body_scroll.get_size_request() if frame is not None else (0, 0)
            if w <= 0 or h <= 0:
                w, h = NOTE_W_DEFAULT, NOTE_H_DEFAULT
            x, y = self._note_base.get(tid, (0.0, 0.0))
        return (x, y, w, h)

    def _item_resize_apply(self, kind, tid, x, y, w, h) -> None:
        frame = self.frames.get(tid) if kind == "node" else self.note_frames.get(tid)
        if kind == "node":
            self._node_size[tid] = (w, h)
            self._base_pos[tid] = (x, y)
            term = getattr(frame, "_term", None) if frame is not None else None
            if term is not None:
                term.set_size_request(int(w), int(h))  # VTE reflui cols/linhas
        else:
            self._note_base[tid] = (x, y)
            if frame is not None:
                frame._body_scroll.set_size_request(int(w), int(h))
        if frame is not None:
            self._place(frame, (x, y), self.model.zoom())

    def _item_resize_persist(self, kind, tid, x, y, w, h) -> None:
        if kind == "node":
            self.model.set_node_size(tid, w, h)
            self.model.set_position(tid, x, y)
        elif self.notes is not None:
            note = self.notes.get(tid)
            if note is not None:
                note.width, note.height = float(w), float(h)
                note.x, note.y = float(x), float(y)
                self.notes.save(note)

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
        self._set_node_monitor(nid, False)  # para o monitor de atividade (Fase 4)
        self._mon_alerted.discard(nid)
        if self._sock_server is not None:  # ADR-17: fecha o listener do socket do agente
            self._sock_server.remove_node(nid)
        self._agent_nids.discard(nid)  # sai do fleet
        self._recruited_by.pop(nid, None)  # sai da linhagem
        self.model.clear_node_cfg(nid, "session")  # unload A′: id órfão não herda sessão morta
        self.model.clear_node_cfg(nid, "unloaded")  # unload B: nem a flag de descarregado
        self._ram_alerted.discard(nid)  # unload D: id reciclado não herda alerta de RAM
        base = self._agent_base(nid)  # desregistra a INSTÂNCIA do controller (libera o id)
        if self.controller is not None and base is not None and nid != base:
            try:
                self.controller.remove_agent_instance(nid)
            except Exception as exc:  # noqa: BLE001
                _log.error("remove_agent_instance(%s): %s", nid, exc)
        _t = getattr(self.frames.get(nid), "_term", None)
        if _t is not None:  # H1: invalida respawn em voo (não roda _go() em widget destruído)
            _t._destroyed = True
            _src = getattr(_t, "_respawn_force_src", None)
            if _src:
                GLib.source_remove(_src)
                _t._respawn_force_src = None
            _fd = getattr(_t, "_pidfd", None)
            if _fd is not None:
                try:
                    os.close(_fd)
                except OSError:
                    pass
                _t._pidfd = None
        frame = self.frames.pop(nid, None)
        if frame is None:
            return
        self.model.remove_from_roster(nid)  # ✕ = remoção permanente (decisão do usuário)
        if nid in self.order:
            self.order.remove(nid)
        self.heads.pop(nid, None)
        self._base_pos.pop(nid, None)
        if self._connect_src is not None and self._connect_src[1] == nid:
            self._cancel_connect()
        self._remove_edges_for(nid)  # tira cabos órfãos do store (+ hook 4b)
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

    def _auto_shortcut(self, nid: str) -> str:
        """Atalho automático Ctrl+<n> (n = 1..9): o menor dígito ainda livre entre os terminais.
        Fica salvo (node_cfg 'shortcut') → aparece na config e pode ser alterado. >9 = vazio."""
        used = {self.model.node_cfg(n, "shortcut") for n in self.frames if n != nid}
        for d in range(1, 10):
            accel = Gtk.accelerator_name(Gdk.KEY_0 + d, Gdk.ModifierType.CONTROL_MASK)
            if accel not in used:
                return accel
        return ""

    def _shortcut_target(self, keyval: int, state) -> str | None:
        """nid cujo atalho custom (node_cfg 'shortcut') bate com a combinação atual, ou None.
        Exige modificador (não rouba teclas normais). Serializa via Gtk.accelerator_name."""
        mods = state & Gtk.accelerator_get_default_mod_mask()
        if not mods:
            return None
        accel = Gtk.accelerator_name(keyval, mods)
        for nid in self.frames:
            if self.model.node_cfg(nid, "shortcut") == accel:
                return nid
        return None

    def _capture_shortcut(self, on_done) -> None:
        """Diálogo que captura a PRÓXIMA combinação (Ctrl/Alt/Shift + tecla) → accel string."""
        win, box = self._dialog("Definir atalho")
        box.append(Gtk.Label(label="Pressione a combinação (com Ctrl / Alt / Shift)…"))
        box.append(Gtk.Label(label="Esc cancela.", xalign=0))
        _mods_only = {
            Gdk.KEY_Control_L, Gdk.KEY_Control_R, Gdk.KEY_Shift_L, Gdk.KEY_Shift_R,
            Gdk.KEY_Alt_L, Gdk.KEY_Alt_R, Gdk.KEY_Super_L, Gdk.KEY_Super_R,
        }

        def pressed(_c, keyval, _kc, state):
            if keyval == Gdk.KEY_Escape:
                win.destroy()
                return True
            if keyval in _mods_only:
                return True  # espera a tecla "real"
            mods = state & Gtk.accelerator_get_default_mod_mask()
            if not mods:
                return True  # exige modificador (evita atalho de 1 tecla)
            on_done(Gtk.accelerator_name(keyval, mods))
            win.destroy()
            return True

        kc = Gtk.EventControllerKey()
        kc.connect("key-pressed", pressed)
        win.add_controller(kc)
        win.present()

    def _focus_next_attention(self) -> None:
        env = attention_items(self._store) if self._store is not None else []
        ids = attention_nids(env, self._node_state, self.frames)  # envelope ∪ visual
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

    def _on_frame_press(self, gesture, _n_press, _x, _y, kind, tid) -> None:
        """Clique em QUALQUER área do card (gesto CAPTURE no frame, antes do VTE/TextView
        consumir). No modo conectar LIGA o cabo (e claima o gesto p/ o corpo não selecionar
        texto); senão só SELECIONA (sem claimar, p/ terminal/arraste seguirem). Isto faz o
        connect funcionar clicando em qualquer parte do card, não só na barra superior."""
        if self._connect_mode:
            self._connect_pick(kind, tid)
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            return
        self._select((kind, tid))
        if kind == "note":  # clicar a nota = EDITAR in-place (texto cru); formata ao sair
            self._note_edit_inplace(tid)
        elif self._note_editing is not None:
            self._note_render(self._note_editing)  # clicou num nó → formata a nota em edição

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
        self._update_ctx()  # mostra/esconde as pílulas de contexto (nota / terminal)
        if sel is None or sel[0] not in ("node", "note"):
            self.plane.set_cursor(None)  # limpa o cursor de resize ao desmarcar

    def _on_motion(self, _c, x, y):
        """Rastreia qual elemento está sob o cursor (p/ rotear o scroll do SELECT+trackball)."""
        self._ptr_over = self._elem_at(self.plane.pick(x, y, Gtk.PickFlags.DEFAULT))
        self._update_resize_cursor(x, y)  # cursor de resize na faixa da borda do selecionado
        if self._connect_mode and self._connect_src is not None:  # cabo-fantasma segue o cursor
            self._connect_cursor = (x, y)
            self.plane.queue_draw()
        if self._placing_spec is not None:  # prévia fantasma do item a posicionar
            self._placing_cursor = (x, y)
            self.plane.queue_draw()

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
        if self._placing_spec is not None:  # modo "clique pra posicionar" tem prioridade
            camx, camy = self._cam
            z = self.model.zoom() or 1.0
            self._commit_placing((x - camx) / z, (y - camy) / z)
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            return
        self._item_resize = None
        picked = self.plane.pick(x, y, Gtk.PickFlags.DEFAULT)
        _el = self._elem_at(picked)
        if self._note_editing is not None and _el != ("note", self._note_editing):
            self._note_render(self._note_editing)  # clicar fora da nota em edição → formata
        # connect: clicar em QUALQUER área do card é tratado pelo gesto CAPTURE do frame
        # (_on_frame_press), que claima — então aqui só sobra o clique no FUNDO do plano.
        rz = self._resize_edge_at(x, y)  # faixa da borda do card SELECIONADO → resize
        if rz is not None:
            kind, tid, edges = rz
            self._item_resize = {
                "kind": kind, "id": tid, "edges": edges,
                "origin": self._item_resize_origin(kind, tid),
            }
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            return
        self._select(self._elem_at(picked))  # pressionar seleciona o nó/nota/árvore (ou limpa no fundo)
        camx, camy = self._cam
        px, py = x - camx, y - camy  # coords base*zoom (p/ hit-test de grupo)
        self._pan = None
        self._drag = None
        self._group_resize = None
        target = self._drag_handle(picked)
        if target is not None:  # alça: mover (conexão é tratada acima, no modo conectar)
            kind, tid = target
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
        self._wake_cables()  # mover/redimensionar/panar pode mexer as âncoras → física da corda
        if getattr(self, "_item_resize", None) is not None:  # resize de nó/nota pela borda
            r = self._item_resize
            mw, mh = self._resize_min(r["kind"])
            x, y, w, h = self._resize_rect(r["origin"], off_x / z, off_y / z, r["edges"], mw, mh)
            self._item_resize_apply(r["kind"], r["id"], x, y, w, h)
            self._resize_plane()
            self.plane.queue_draw()
            return
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
        if getattr(self, "_item_resize", None) is not None:  # fim do resize de nó/nota
            r = self._item_resize
            self._item_resize = None
            kind, tid, edges, o = r["kind"], r["id"], r["edges"], r["origin"]
            _x, _y, w, h = self._item_resize_origin(kind, tid)  # tamanho aplicado ao vivo
            mw, mh = self._resize_min(kind)
            w = max(mw, snap_to_grid(w, GRID))  # imanta à grade
            h = max(mh, snap_to_grid(h, GRID))
            x, y = (self._base_pos if kind == "node" else self._note_base).get(tid, (0.0, 0.0))
            if "w" in edges:  # reposiciona com o tamanho snapado mantendo a borda ancorada
                x = o[0] + (o[2] - w)
            if "n" in edges:
                y = o[1] + (o[3] - h)
            x, y = snap_point((x, y), GRID)
            self._item_resize_apply(kind, tid, x, y, w, h)
            self._item_resize_persist(kind, tid, x, y, w, h)
            self._autofit_all_groups()
            self._resize_plane()
            self.plane.queue_draw()
            self._mm_refresh()
            return
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
        self._wake_cables()  # cabos restaurados caem no sag inicial ao abrir
        return False  # one-shot (GLib)

    def _sel_base_center(self):
        """Centro (em coords-base) do elemento selecionado, ou None — p/ o zoom focar nele."""
        fr = self._frame_of(self._selected)
        if fr is None:
            return None
        ok, r = fr.compute_bounds(self.plane)
        if not ok or r.size.width <= 0:
            return None
        camx, camy = self._cam
        z = self.model.zoom() or 1.0
        sx = r.origin.x + r.size.width / 2.0
        sy = r.origin.y + r.size.height / 2.0
        return ((sx - camx) / z, (sy - camy) / z)

    def _zoom(self, dz):
        """Zoom ANCORADO: sem seleção mantém o CENTRO da tela fixo (não escorrega pro canto);
        com um nó/nota selecionado, leva ele pro centro da viewport (o zoom 'vai até o nó')."""
        z_old = self.model.zoom() or 1.0
        vw = self.scrolled.get_width() or 1
        vh = self.scrolled.get_height() or 1
        camx, camy = self._cam
        focus = self._sel_base_center()  # nó/nota selecionado tem prioridade
        if focus is None:  # senão: o ponto-base que está no centro da tela agora → fica fixo
            focus = ((vw / 2.0 - camx) / z_old, (vh / 2.0 - camy) / z_old)
        self.model.set_zoom(z_old + dz)  # clampa [0.3, 3.0] + persiste
        z_new = self.model.zoom()
        self._cam = (vw / 2.0 - focus[0] * z_new, vh / 2.0 - focus[1] * z_new)
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
            st = self._node_state.get(nid, "idle")
            if st in ATTENTION_VISUAL_STATES:  # realce: nó que precisa de você vira a cor do estado
                h = STATE_COLORS.get(st, "#f59e0b").lstrip("#")
                col = tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
            elif self._node_unloaded(nid):  # descarregado: cinza apagado (Bloco D — o
                col = (0.35, 0.37, 0.42)  # minimapa NÃO pinta por estado; branch explícito)
            else:
                col = (0.55, 0.60, 0.85)  # nós: azulado (padrão)
            items.append((bx, by, nw, nh, col))
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
    def _resolve_theme(self, name: str) -> str:
        """Resolve nomes especiais: 'system' (portal XDG; fallback escuro), 'dark', 'light'.
        Qualquer outro nome volta como está (tema nomeado do bundle/base/usuário)."""
        if name == "system":
            return DEFAULT_LIGHT if _system_color_scheme() == 2 else DEFAULT_DARK
        if name == "dark":
            return DEFAULT_DARK
        if name == "light":
            return DEFAULT_LIGHT
        return name

    def _node_theme_name(self, nid: str) -> str:
        """Tema do terminal: override por-nó → tema global (terminal_theme)."""
        return self.model.node_cfg(nid, "theme") or self.model.terminal_theme()

    def _apply_node_theme(self, nid: str) -> None:
        frame = self.frames.get(nid)
        term = getattr(frame, "_term", None) if frame is not None else None
        if term is None:
            return
        th = get_theme(self._resolve_theme(self._node_theme_name(nid)))
        term.set_colors(_rgba(th["fg"]), _rgba(th["bg"]), [_rgba(c) for c in th["palette"]])

    def _apply_theme(self, name: str | None = None) -> None:
        """Reaplica o tema a TODOS os terminais por-nó (override prevalece sobre o global)."""
        for nid in list(self.frames):
            self._apply_node_theme(nid)

    # -- comando / diretório / env por terminal + respawn (Fase 3) --
    def _effective_argv(self, nid: str, base: list[str]) -> list[str]:
        """argv do terminal: comando custom (`bash -lc '<cmd>; exec bash -i'`) ou o base."""
        cmd = self.model.node_cfg(nid, "command").strip()
        return ["/bin/bash", "-lc", f"{cmd}; exec /bin/bash -i"] if cmd else base

    def _node_argv(self, nid: str) -> list[str]:
        frame = self.frames.get(nid)
        base = getattr(frame, "_base_argv", ["/bin/bash"]) if frame is not None else ["/bin/bash"]
        return self._effective_argv(nid, base)

    def _node_auto_approve(self, nid: str) -> bool:
        """O CLI deste nó roda SEM prompts de permissão? Sim se Maestro mode (Fase 1) ou o
        toggle 'permissão total' (Fase 2) estiver ligado — o confinamento real é o bwrap (ADR-6)."""
        return bool(self.model.node_cfg(nid, "maestro") or self.model.node_cfg(nid, "autoapprove"))

    def _agent_base(self, nid: str) -> str | None:
        """Base do agente (claude/codex) do nó, a partir do roster persistido."""
        for spec in self.model.node_roster():
            if spec.get("nid") == nid:
                return spec.get("base") or nid
        return None

    def _node_is_agent(self, nid: str) -> bool:
        """True se o nó é um AGENTE de IA (não um shell) — fonte: `kind` do roster do canvas.
        Conservador: kind ausente/desconhecido = NÃO agente (shell fica opt-in, sem monitor
        marcando 'waiting' à toa num bash ocioso). Base do monitor padrão-ON (Bloco 3)."""
        for spec in self.model.node_roster():
            if spec.get("nid") == nid:
                return spec.get("kind") == "agent"
        return False

    def _monitor_default_on(self, nid: str) -> bool:
        """Estado EFETIVO do monitor de atividade, com tri-estado da cfg 'monitor':
        "1"=on · "0"=off explícito · ""=default (ON p/ nó-agente, OFF p/ shell)."""
        mon = self.model.node_cfg(nid, "monitor")
        return mon == "1" or (mon == "" and self._node_is_agent(nid))

    def _rebuild_agent_argv(self, nid: str) -> None:
        """Recomputa o argv bwrap do agente (ex.: mudou o auto_approve) e atualiza _base_argv,
        p/ o próximo respawn lançar o CLI com/sem as flags de auto-aprovação."""
        frame = self.frames.get(nid)
        base = self._agent_base(nid)
        if frame is None or base is None or not self._ask_bus_dir:
            return
        prof = installed_agents().get(base)
        if prof is None:
            return
        frame._base_argv = agent_argv(prof, str(self._node_ws(nid)), node=nid,
                                      ask_bus_dir=self._ask_bus_dir,
                                      auto_approve=self._node_auto_approve(nid))

    def _node_envv(self, nid: str) -> list[str] | None:
        """env custom (linhas KEY=VALUE em node_cfg 'env') mesclado ao ambiente; None = herda."""
        raw = self.model.node_cfg(nid, "env").strip()
        if not raw:
            return None
        env = dict(os.environ)
        for line in raw.splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
        return [f"{k}={v}" for k, v in env.items()]

    @staticmethod
    def _signal_child(term, sig) -> bool:
        """Sinaliza o filho via PIDFD (à prova de reciclagem) ou, na falta, pelo PID guardado.
        Nunca sinaliza um PID nulo (reciclado). Devolve True se enviou."""
        fd = getattr(term, "_pidfd", None)
        if fd is not None:
            try:
                signal.pidfd_send_signal(fd, sig)
                return True
            except (ProcessLookupError, OSError):
                return False
        pid = getattr(term, "_child_pid", None)
        if pid:
            try:
                os.kill(pid, sig)
                return True
            except OSError:
                return False
        return False

    def _on_child_exited(self, term, _status, nid) -> None:
        """Handler PERSISTENTE de child-exited (1x por terminal). Invalida o PID (já reapeado →
        reciclável) e, se havia um restart pendente, respawna DEFERIDO (fora do stack do sinal)."""
        fd = getattr(term, "_pidfd", None)
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        term._pidfd = None
        term._child_pid = None
        src = getattr(term, "_respawn_force_src", None)
        if src:
            GLib.source_remove(src)
            term._respawn_force_src = None
        want = term._respawn_state == "killing" or getattr(term, "_respawn_pending", False)
        term._respawn_state = "idle"
        term._respawn_pending = False
        if want and not getattr(term, "_destroyed", False) and nid in self.frames:
            GLib.idle_add(self._do_respawn, nid)  # defere: VTE ainda desmonta o filho/PTY antigos

    def _do_respawn(self, nid: str) -> bool:
        frame = self.frames.get(nid)
        term = getattr(frame, "_term", None) if frame is not None else None
        if term is None or getattr(term, "_destroyed", False):
            return False
        cwd = self.model.node_cfg(nid, "cwd") or None
        if cwd and not os.path.isdir(cwd):  # M6: cwd inválido → herda (não falha o spawn)
            cwd = None
        if nid in self._mon:  # M1: o BANNER do restart não deve virar falso "parou"
            self._mon[nid]["skip"] = True
        if self._node_unloaded(nid):  # respawnou → não está mais descarregado
            self.model.clear_node_cfg(nid, "unloaded")
            self.set_node_state(nid, self._node_state.get(nid, "idle"))  # tira a vista ⏏
        term.reset(True, True)  # limpa tela + scrollback p/ um restart limpo
        _spawn_into(term, self._node_argv(nid), cwd, self._node_envv(nid))
        return False  # idle one-shot

    def _respawn_node(self, nid: str) -> None:
        """Reinicia o terminal no MESMO widget (state machine — 1 filho por vez). Mata o filho
        DIRETO via pidfd/PID (bash no shell OU **bwrap**; o sandbox usa --unshare-pid p/ o SIGKILL
        colapsar o namespace). O respawn em si só acontece no child-exited (C1/C2/H1)."""
        frame = self.frames.get(nid)
        term = getattr(frame, "_term", None) if frame is not None else None
        if term is None or getattr(term, "_destroyed", False):
            return
        if getattr(term, "_respawn_state", "idle") == "killing":
            term._respawn_pending = True  # C1: coalesce — não dispara um 2º respawn
            return
        if not getattr(term, "_child_pid", None):  # sem filho vivo conhecido → respawn direto
            self._do_respawn(nid)
            return
        term._respawn_state = "killing"
        self._signal_child(term, signal.SIGTERM)

        def _force_kill():
            term._respawn_force_src = None
            if term._respawn_state == "killing":  # ainda não saiu → SIGKILL (com --unshare-pid
                self._signal_child(term, signal.SIGKILL)  # colapsa o namespace do bwrap)
            return False

        term._respawn_force_src = GLib.timeout_add(1500, _force_kill)

    # -- fonte por terminal (override) + default global + zoom de fonte (VTE set_font/scale) --
    FONT_SCALE_MIN, FONT_SCALE_MAX = 0.25, 4.0  # clamp do VTE (vte-private.h)

    def _effective_font(self, nid: str) -> Pango.FontDescription | None:
        """Fonte do terminal: override por-nó → default global → None (= monospace do sistema)."""
        desc_str = self.model.node_cfg(nid, "font") or self.model.terminal_font()
        return Pango.FontDescription.from_string(desc_str) if desc_str else None

    def _node_font_scale(self, nid: str) -> float:
        try:
            s = float(self.model.node_cfg(nid, "fontscale") or "1.0")
        except ValueError:
            s = 1.0
        return max(self.FONT_SCALE_MIN, min(self.FONT_SCALE_MAX, s))

    def _apply_node_font(self, nid: str) -> None:
        """Aplica fonte (set_font; None = monospace do sistema) + escala (set_font_scale)."""
        frame = self.frames.get(nid)
        term = getattr(frame, "_term", None) if frame is not None else None
        if term is None:
            return
        term.set_font(self._effective_font(nid))  # None reseta p/ a monospace do sistema
        term.set_font_scale(self._node_font_scale(nid))

    def _apply_font_all(self) -> None:
        """Reaplica a fonte a TODOS os terminais (ex.: mudou o default global)."""
        for nid in list(self.frames):
            self._apply_node_font(nid)

    # -- cor accent por terminal (tint do cabeçalho; mesmo motor de CSS-provider da nota) --
    def _rebuild_node_colors(self) -> None:
        """Regenera o CSS por-terminal a partir de self._node_colors (hex) — tint do cabeçalho."""
        rules = []
        for nid, hexc in self._node_colors.items():
            if not hexc:
                continue
            r, g, b = _hex_to_rgb(hexc)
            rules.append(
                f".ndh-{self._nid_key(nid)} {{ background-color: rgba({r},{g},{b},0.38); }}")
        self._css_load(self._node_color_provider, "\n".join(rules))

    def _apply_node_color(self, nid: str, hexc: str) -> None:
        """Tinge a faixa do cabeçalho do terminal com a cor accent (''=sem cor)."""
        self._node_colors[nid] = hexc
        self._rebuild_node_colors()
        head = self.heads.get(nid)
        if head is not None:
            cls = f"ndh-{self._nid_key(nid)}"
            if hexc:
                head.add_css_class(cls)
            else:
                head.remove_css_class(cls)

    def _apply_node_icon(self, nid: str, val: str) -> None:
        """Ícone do terminal no cabeçalho: 'maestro-<n>' (bundlado) ou 'emoji:<e>' ou '' (nenhum).
        Inserido logo após o dot de estado (espelha o Maestri)."""
        head = self.heads.get(nid)
        if head is None:
            return
        old = getattr(head, "_icon", None)
        if old is not None:
            head.remove(old)
            head._icon = None
        if not val:
            return
        if val.startswith("emoji:"):
            w: Gtk.Widget = Gtk.Label(label=val[6:])
        else:
            w = Gtk.Image.new_from_icon_name(val)
            w.set_pixel_size(16)
        w.add_css_class("node-icon")
        head.insert_child_after(w, head._dot)  # logo após o dot de estado
        head._icon = w

    @staticmethod
    def _fmt_cost(u) -> str:
        """Rótulo curto do medidor (F1): '$0.42' quando há custo; senão tokens ('12.3k tok');
        '' quando zero. Codex sem preço aparece como tokens — honesto, não chuta custo."""
        if getattr(u, "cost_usd", 0.0):
            return f"${u.cost_usd:.2f}"
        tot = getattr(u, "input_tokens", 0) + getattr(u, "output_tokens", 0)
        if tot >= 1000:
            return f"{tot / 1000:.1f}k tok"
        return f"{tot} tok" if tot else ""

    def _refresh_node_cost(self, nid: str) -> None:
        """Atualiza o $ do header do nó a partir do UsageLedger (F1). Chamado na criação e a
        cada evento do usage_bus (marshalado p/ a main thread via idle_add)."""
        ctrl = self.controller
        led = getattr(ctrl, "usage_ledger", None) if ctrl is not None else None
        head = self.heads.get(nid)
        lbl = getattr(head, "_cost", None) if head is not None else None
        if led is None or lbl is None:
            return
        u = led.get(nid)
        lbl.set_text(self._fmt_cost(u))
        lbl.set_tooltip_text(
            f"{u.input_tokens + u.output_tokens} tokens acumulados · ${u.cost_usd:.4f}")

    # -- Bloco D: RAM por nó (worker thread; docs/21 §8) --
    @staticmethod
    def _fmt_ram(pss_mb: float) -> str:
        """Rótulo curto do badge de RAM: '312 MB' / '1.2 GB'; '' quando nada medido."""
        if pss_mb <= 0:
            return ""
        if pss_mb >= 1024:
            return f"{pss_mb / 1024:.1f} GB"
        return f"{pss_mb:.0f} MB"

    def _ram_limit_mb(self) -> int:
        """Limiar de notificação de RAM (MB) persistido; 0 = desligado (default)."""
        st = getattr(self, "_store", None)
        return parse_limit_mb(st.get_ui("ram_limit_mb") if st is not None else None)

    def _set_ram_label(self, nid: str, text: str, *, high: bool,
                       tooltip: str | None = None) -> None:
        head = self.heads.get(nid)
        lbl = getattr(head, "_ram", None) if head is not None else None
        if lbl is None:
            return
        lbl.set_text(text)
        if tooltip is not None:
            lbl.set_tooltip_text(tooltip)
        if high:
            lbl.add_css_class("node-ram-high")
        else:
            lbl.remove_css_class("node-ram-high")

    def start_ram_watcher(self, interval: int = 10) -> None:
        """Worker de RAM por nó: mede a árvore de cada nó com filho vivo em THREAD
        (smaps_rollup varre as VMAs no kernel — JAMAIS na main loop do CM4; revisão do
        Fable, docs/21 §8.5) e marshala só o set_text via idle_add (padrão usage_bus).
        Relê `_child_pid` a cada passada — nunca cacheia a árvore entre ticks (respawn
        no meio do tick mede o processo novo ou nada, nunca um estranho)."""
        self._ram_stop = threading.Event()

        def _loop():
            while not self._ram_stop.wait(interval):
                try:
                    pids = {nid: getattr(getattr(f, "_term", None), "_child_pid", None)
                            for nid, f in list(self.frames.items())}
                    t0 = time.monotonic()
                    res = {nid: tree_ram_mb(pid) for nid, pid in pids.items() if pid}
                    dt = time.monotonic() - t0
                    if dt > 0.3:  # critério de aceite (b) do plano: logar quando estourar
                        _log.warning("ram watcher: medição levou %.0fms", dt * 1000)
                    GLib.idle_add(self._apply_ram, res)
                except Exception as exc:  # nunca derruba o worker
                    _log.debug("ram watcher: %s", exc)

        t = threading.Thread(target=_loop, daemon=True, name="ram-watcher")
        self._ram_thread = t
        t.start()

    def _apply_ram(self, res: dict) -> bool:
        """Aplica UMA passada de medição na UI (main thread, só set_text — <5ms).
        Limiar: css segue o limiar exato; a NOTIFICAÇÃO usa histerese 0.9×X
        (anti-flapping — docs/21 §8.3-7)."""
        limit = self._ram_limit_mb()
        for nid, (_rss, pss, private) in res.items():
            if nid not in self.frames or self._node_unloaded(nid):
                continue  # fechou/descarregou entre a medição e o apply
            high = bool(limit) and pss >= limit
            tip = (f"peso real (PSS) {pss:.0f} MB · "
                   f"liberável ao descarregar (Private) {private:.0f} MB")
            self._set_ram_label(nid, self._fmt_ram(pss), high=high, tooltip=tip)
            alerted, fire = alert_step(nid in self._ram_alerted, pss, limit)
            if alerted:
                self._ram_alerted.add(nid)
            else:
                self._ram_alerted.discard(nid)
            if fire:
                name = self.model.node_name(nid, nid)
                notify(f"maestro: {name} usando {pss:.0f} MB",
                       f"acima do limiar de {limit} MB — considere ⏏ descarregar")
        return False  # idle one-shot

    def set_node_state(self, nid: str, state: str) -> None:
        """Estado do nó vira um ÍCONE Lucide (pré-colorido) no cabeçalho — cor+forma+tooltip. UI-1.
        Rastreia o estado em `_node_state` (fonte p/ a atenção ∪ visual e o realce no minimapa) e,
        quando entra/sai de um estado de atenção, atualiza o "⚠ N" + minimapa."""
        s = state if state in STATE_COLORS else "idle"
        prev = self._node_state.get(nid, "idle")
        self._node_state[nid] = s
        head = self.heads.get(nid)
        dot = getattr(head, "_dot", None) if head is not None else None
        if dot is not None:
            # "descarregado" é CAMADA DE VISTA sobre idle+flag, NÃO estado da máquina
            # (docs/21 §8.3-3/Fable): um handoff headless num nó descarregado seta busy
            # por cima (correto — o cabo trabalha sem o PTY) e, ao voltar a idle, o
            # eject reaparece sozinho. Nada muda em STATE_COLORS/attention/web.
            if s == "idle" and self._node_unloaded(nid):
                if hasattr(dot, "set_from_icon_name"):  # Gtk.Image (produção)
                    dot.set_from_icon_name("maestro-state-unloaded")
                dot.set_tooltip_text("descarregado (clique no terminal p/ retomar)")
                st_lbl = getattr(head, "_status", None)
                if st_lbl is not None:
                    st_lbl.set_text("descarregado")
            else:
                if hasattr(dot, "set_from_icon_name"):  # Gtk.Image (produção)
                    dot.set_from_icon_name(_STATE_ICON.get(s, _STATE_ICON["idle"]))
                dot.set_tooltip_text(_STATE_PT.get(s, s))
                st_lbl = getattr(head, "_status", None)  # E3: status proativo
                if st_lbl is not None:
                    st_lbl.set_text(state_activity(s))
        # atenção ∪ visual: só recomputa quando a transição envolve um estado de atenção
        # (evita varrer o Store a cada toggle idle↔busy de handoff — barato no CM4).
        if prev in ATTENTION_VISUAL_STATES or s in ATTENTION_VISUAL_STATES:
            self._refresh_attention()

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

    def _connect_pick(self, kind: str, nid: str) -> None:
        """1º clique escolhe a origem; 2º cria (ou remove, se já existe) o cabo. Aceita
        nó ou NOTA como endpoint (edges guardam ids string)."""
        if self.edges is None:
            return
        if self._connect_src is None:
            self._connect_src = (kind, nid)
            if kind == "node":
                self.set_node_state(nid, "busy")  # realça a origem pendente (nota usa seleção)
            else:
                self._select(("note", nid))
            self._preview_rope = None
            self._wake_cables()  # cabo-fantasma segue o cursor até o 2º clique
            self._update_hintbar()  # B2: agora "clique no DESTINO"
            return
        (skind, src), (dkind, dst) = self._connect_src, (kind, nid)
        self._connect_src = None
        if skind == "node":
            self.set_node_state(src, "idle")
        self._update_hintbar()
        if src == dst:
            self._maybe_end_oneshot()  # clicou na própria origem: aborta o cabo de cápsula
            return
        pairs = set(self.edges.list())
        if (src, dst) in pairs or (dst, src) in pairs:
            # já conectados (em QUALQUER sentido) -> desconecta (toggle, sem depender da ordem)
            self.edges.remove(src, dst)
            self.edges.remove(dst, src)
            self._edge_state.pop((src, dst), None)
            self._edge_state.pop((dst, src), None)
            self._on_cable_removed(src, dst)  # hook (4b); no-op no 4a
        else:
            self.edges.add(src, dst)
            if skind == "node" and dkind == "node":
                self._ask_hint(src, dst)  # cabo IA↔IA: maestro-ask (ADR-11)
            else:
                self._on_note_cable_added(src, dst, skind, dkind)  # hook (4b); no-op no 4a
        self._wake_cables()  # cabo criado/removido: a corda precisa nascer/sumir
        self._maybe_end_oneshot()  # conexão de cápsula: 1 cabo feito → sai do modo conectar
        self.plane.queue_draw()

    def _maybe_end_oneshot(self) -> None:
        """Sai do modo conectar após a 1ª conexão, quando ela foi iniciada por uma cápsula
        (botão 🔌 contextual). O modo global (🔌 da FAB) NÃO é one-shot e permanece ligado."""
        if not self._connect_oneshot:
            return
        self._connect_oneshot = False
        self._connect_cursor = None
        self._preview_rope = None
        btn = getattr(self, "_connect_btn", None)
        if btn is not None and btn.get_active():
            btn.set_active(False)  # untoggle → _toggle_connect desliga o modo (src já é None)
        else:
            self._connect_mode = False
        self._update_hintbar()

    def _on_cable_removed(self, a: str, b: str) -> None:
        """Ao remover um cabo: rematerializa o(s) nó(s) p/ podar a nota desligada."""
        for nid in (a, b):
            if nid in self.frames:
                self._materialize_node_notes(nid)

    def _on_note_cable_added(self, src: str, dst: str, skind: str, dkind: str) -> None:
        """Ao criar cabo nota↔nó: materializa a nota no workspace do nó + avisa o agente."""
        nid = src if skind == "node" else (dst if dkind == "node" else None)
        if nid is not None:
            self._materialize_node_notes(nid)

    # -- Fase 4b: nota conectada vira arquivo no workspace do agente (ler/escrever + ciência) --
    def _node_ws(self, nid: str):
        base_home = Path(self._ask_bus_dir).parent
        return Workspace(str(base_home / "workspaces")).path(nid)

    # -- ciclo de vida da sessão do nó (unload — Bloco A′) --
    def _capture_node_session(self, nid: str) -> str | None:
        """Lê o JSONL mais novo no dir de projeto exclusivo do nó (`_node_ws`) e persiste o
        session-id capturado em `nodecfg_{nid}_session` (ui_state → sobrevive a restart).
        Chave PRÓPRIA do canvas — NÃO a tabela `sessions` do orquestrador (evita colidir com
        o medidor/budget F1). Retorna o id capturado, ou None se o nó ainda não gravou sessão."""
        sid = newest_session_id(self._node_ws(nid))
        if sid:
            self.model.set_node_cfg(nid, "session", sid)
        return sid

    def _node_session(self, nid: str) -> str:
        """Session-id persistido do nó (capturado), ou "" se nenhum. Base do reload (Bloco C)."""
        return self.model.node_cfg(nid, "session")

    def _node_unloaded(self, nid: str) -> bool:
        """True se o nó está descarregado (processo morto de propósito; card fica)."""
        return bool(self.model.node_cfg(nid, "unloaded"))

    def _make_node_term(self, nid: str, argv: list[str]):
        """Terminal do nó no `_add_node`. Nó com flag 'unloaded' NASCE SEM processo
        (Bloco C — aqui mora o maior ganho de RAM: reabrir o app não ressuscita N
        agentes; o estado persistido nunca vira mentira visual)."""
        if self._node_unloaded(nid):
            return _dead_terminal()
        return make_terminal(
            self._effective_argv(nid, argv),
            self.model.node_cfg(nid, "cwd") or None,
            self._node_envv(nid))

    def _resume_argv(self, nid: str) -> list[str] | None:
        """argv ONE-SHOT de retomada do nó, ou None se retomar não se aplica (o reload
        cai no spawn normal): comando custom manda no nó (edge do docs/21 §4-C), shell
        não tem sessão, e claude sem sessão capturada não tem o que retomar. codex
        (modo subcommand) SEMPRE retoma via picker do CLI — o humano escolhe (§5)."""
        if self.model.node_cfg(nid, "command").strip():
            return None
        base = self._agent_base(nid)
        prof = installed_agents().get(base) if base else None
        if prof is None or not self._ask_bus_dir:
            return None
        if prof.session_mode == "subcommand":
            sid = ""  # codex: `resume` sem id = picker (não há captura por-workspace)
        else:
            sid = self._node_session(nid)
            if not sid:
                return None
        return agent_argv(prof, str(self._node_ws(nid)), node=nid,
                          ask_bus_dir=self._ask_bus_dir,
                          auto_approve=self._node_auto_approve(nid),
                          resume_session=sid)

    def _reload_node(self, nid: str) -> None:
        """Retoma um nó descarregado (unload — Bloco C): respawn RESUME-aware.

        O argv de resume é ONE-SHOT — `_base_argv` NUNCA é mutado (docs/21 §3.6: o argv
        natural é reusado pelos ~8 gatilhos de respawn). Semântica decidida na story:
        **"Retomar" = resume da sessão capturada; "Reiniciar" = começar do ZERO** (o
        respawn normal segue usando o argv natural e limpa a flag)."""
        if not self._node_unloaded(nid):
            return  # no-op: o gesto de clique no terminal dispara isto em qualquer nó
        frame = self.frames.get(nid)
        term = getattr(frame, "_term", None) if frame is not None else None
        if term is None or getattr(term, "_destroyed", False):
            return
        if getattr(term, "_child_pid", None):  # flag mentiu (processo vivo): não empilha
            self.model.clear_node_cfg(nid, "unloaded")  # spawn — só corrige o estado
            return
        argv = self._resume_argv(nid)
        resumed = argv is not None
        if argv is None:  # sem sessão/custom/shell → volta do zero com o argv natural
            argv = self._node_argv(nid)
        cwd = self.model.node_cfg(nid, "cwd") or None
        if cwd and not os.path.isdir(cwd):  # espelha _do_respawn (M6)
            cwd = None
        self.model.clear_node_cfg(nid, "unloaded")
        # religa o monitor pela PREFERÊNCIA persistida (o unload só desligou o runtime)
        self._set_node_monitor(nid, self._monitor_default_on(nid))
        if nid in self._mon:
            self._mon[nid]["skip"] = True  # banner do spawn não vira falso "parou" (M1)
        term.reset(True, True)
        _spawn_into(term, argv, cwd, self._node_envv(nid))
        self.set_node_state(nid, self._node_state.get(nid, "idle"))  # tira a vista ⏏ (D)
        self._audit("reload", node=nid, resume=resumed)
        self._refresh_fleet_hud()
        self.plane.queue_draw()

    def _unload_node(self, nid: str) -> None:
        """Descarrega o nó (unload — Bloco B): captura a sessão (A′), mata o processo SEM
        respawnar e persiste a flag 'unloaded' (o card fica; retomar = Bloco C).

        SIGKILL direto (espelha _kill_all_agents), não a escalada SIGTERM→SIGKILL do
        respawn: dentro do bwrap o SIGTERM NEM CHEGA ao CLI (ADR-23) — a escalada seria
        ilusão. A conversa já está no JSONL do disco; o kill não a perde."""
        frame = self.frames.get(nid)
        term = getattr(frame, "_term", None) if frame is not None else None
        if term is None:
            return
        self._capture_node_session(nid)  # A′: persiste a sessão viva ANTES de matar
        self._set_node_monitor(nid, False)  # senão a morte vira falso "é sua vez"
        self._mon_alerted.discard(nid)
        # anti-race (revisão Fable): um respawn em voo ("killing"/pending) faria o
        # _on_child_exited RESSUSCITAR o nó logo após o unload — zera antes do kill.
        term._respawn_state = "idle"
        term._respawn_pending = False
        src = getattr(term, "_respawn_force_src", None)
        if src:
            GLib.source_remove(src)
            term._respawn_force_src = None
        killed = self._signal_child(term, signal.SIGKILL)  # bwrap colapsa a árvore
        term.feed(f"\r\n  {UNLOADED_HINT}\r\n".encode())  # ensina como retomar (Bloco C)
        self.model.set_node_cfg(nid, "unloaded", "1")  # persiste: "abre igual fechou"
        self.set_node_state(nid, "idle")  # sai de atenção; vista idle+flag → eject (D)
        self._set_ram_label(nid, "", high=False)  # zera JÁ (10s de número velho = mentira)
        self._ram_alerted.discard(nid)
        self._audit("unload", node=nid, killed=bool(killed))
        self._refresh_fleet_hud()
        self.plane.queue_draw()

    @staticmethod
    def _unload_msg(busy: bool) -> str:
        """Texto da confirmação do descarregar (puro, testável). Confirmação SEMPRE —
        `tui_busy` tem falso negativo (tela scrollada/prompt de permissão), então o
        guard reforça o aviso quando ocupado, mas nunca substitui a confirmação."""
        base = ("Mata o processo pra liberar RAM. O card fica no canvas e a\n"
                "conversa é retomada ao recarregar (a sessão já está no disco).")
        if busy:
            return ("⚠ O agente parece estar TRABALHANDO — descarregar agora\n"
                    "interrompe o turno em voo (o retomar devolve só o que já\n"
                    "foi gravado; o que o turno já fez no workspace FICA).\n\n" + base)
        return base

    def _confirm_unload(self, nid: str) -> None:
        """Confirmação do descarregar (ação destrutiva p/ o turno em voo)."""
        frame = self.frames.get(nid)
        term = getattr(frame, "_term", None) if frame is not None else None
        if term is None:
            return
        busy = tui_busy(self._term_text(term))
        name = self.model.node_name(nid, nid)
        dlg, box = self._dialog(f"⏏ Descarregar {name}")
        msg = Gtk.Label(label=self._unload_msg(busy))
        msg.set_wrap(True)
        msg.set_xalign(0.0)
        box.append(msg)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda _b: dlg.destroy())
        go = Gtk.Button(label="⏏ Descarregar")
        if busy:
            go.add_css_class("destructive-action")
        go.connect("clicked", lambda _b: (self._unload_node(nid), dlg.destroy()))
        row.append(cancel)
        row.append(go)
        box.append(row)
        dlg.present()

    # -- Responsabilidades (roles) por terminal (Fase 5) --
    @staticmethod
    def _role_lib_path() -> Path:
        return Path.home() / ".config" / "maestro-console" / "roles.json"

    def _roles(self) -> list:
        """Biblioteca de papéis (arquivo + built-in)."""
        return load_role_library(self._role_lib_path())

    def _save_roles(self, roles: list) -> None:
        save_role_library(self._role_lib_path(), roles)

    def _node_role(self, nid: str):
        """Role atribuído ao terminal, ou None. Se o nome casar com a biblioteca, usa o
        Role rico de lá; senão, monta um Role AD-HOC com o texto livre como instrução —
        assim papéis livres (ex.: vindos do `maestri recruit <ag> "papel livre"`) também
        são materializados no workspace e aparecem no `list` (antes virava None → "—")."""
        name = (self.model.node_cfg(nid, "role") or "").strip()
        if not name:
            return None
        lib = next((r for r in self._roles() if r.name == name), None)
        return lib if lib is not None else Role(name=name, agent="", instruction=name, color="")

    def _role_targets(self, nid: str) -> list[str]:
        """Onde ESCREVEMOS o bloco de role: SÓ o workspace ISOLADO do agente (nosso). NUNCA o
        AGENTS.md/CLAUDE.md do cwd do usuário (respeita o projeto — o cwd recebe só o sidecar
        .maestri/role.json). Logo: o role vale no MODO AGENTE (codex manual no projeto não pega)."""
        if self._ask_bus_dir:
            wsp = self._node_ws(nid)
            if wsp.is_dir():
                return [str(wsp)]
        return []

    def _apply_role_spec(self, nid: str, role) -> None:
        """Materializa um Role JÁ RESOLVIDO (bloco marcado + sidecar + accent). `role=None`
        desatribui. Extraído de `_apply_node_role` pra quem já tem o Role em mãos e NÃO deve
        perder a instrução na resolução por nome/biblioteca (ex.: `_materialize_team`, cujo
        `AgentSpec.instruction` já vem com placeholders interpolados — resolver por
        `_node_role`/nome perderia esse texto e escreveria só o NOME como instrução)."""
        targets = self._role_targets(nid)
        if role is None:  # desatribui: tira o bloco marcado (preserva o resto)
            for t in targets:
                try:
                    remove_role_block(t)
                except OSError:
                    pass
            return
        for t in targets:
            try:
                install_role_block(t, role)
            except OSError:
                pass
        cwd = self.model.node_cfg(nid, "cwd")
        if cwd and targets:  # M4: sidecar só p/ nó-AGENTE (não cria .maestri no repo de um shell)
            try:
                write_role_sidecar(cwd, role)
            except OSError:
                pass
        if not self.model.node_cfg(nid, "color"):  # M2: não sobrescreve o accent que o usuário pôs
            self.model.set_node_cfg(nid, "color", role.badge())
            self._apply_node_color(nid, role.badge())

    def _apply_node_role(self, nid: str) -> None:
        """Materializa o role ATRIBUÍDO por nome (`node_cfg('role')` + biblioteca/ad-hoc)."""
        self._apply_role_spec(nid, self._node_role(nid))

    def _apply_node_maestro(self, nid: str) -> None:
        """Maestro mode (Fase 6): injeta a manager-skill no workspace do agente quando o toggle
        está ligado (a IA lê no start). Off = nada (o host rejeita comandos de não-managers)."""
        if not self._ask_bus_dir or not self.model.node_cfg(nid, "maestro"):
            return
        try:
            wsp = self._node_ws(nid)
            if wsp.is_dir():
                install_maestro_skill(str(wsp), nid)
        except OSError:
            pass

    def _materialize_node_notes(self, nid: str) -> None:
        """Grava as notas ligadas ao nó como notes/<id>.md no workspace + atualiza o manifesto."""
        if self.notes is None or self.edges is None or not self._ask_bus_dir:
            return
        if nid not in self.frames:  # só nós-agente reais (têm workspace/AGENTS.md)
            return
        note_ids = connected_notes(self.edges.list(), nid, set(self.note_frames))
        nd = self._node_ws(nid) / "notes"
        manifest = []
        for note_id in note_ids:
            note = self.notes.get(note_id)
            if note is None:
                continue
            p = note_to_file(note, nd, f"{note_id}.md")  # reusa engine/notes
            self._note_file_mtime[(nid, note_id)] = p.stat().st_mtime
            manifest.append((note.title, f"notes/{note_id}.md"))
        self._prune_node_note_files(nid, note_ids)
        install_connected_notes_skill(str(self._node_ws(nid)), nid, manifest)

    def _prune_node_note_files(self, nid: str, keep_ids) -> None:
        """Remove notes/<id>.md de notas que não estão mais ligadas ao nó."""
        nd = self._node_ws(nid) / "notes"
        if not nd.is_dir():
            return
        for f in nd.glob("*.md"):
            if f.stem not in keep_ids:
                try:
                    f.unlink()
                except OSError:
                    pass
                self._note_file_mtime.pop((nid, f.stem), None)

    def _materialize_note_everywhere(self, note_id: str) -> None:
        """Reescreve o arquivo da nota em todos os nós ligados a ela (após edição no canvas)."""
        if self.edges is None:
            return
        for nid in nodes_for_note(self.edges.list(), note_id, set(self.frames)):
            self._materialize_node_notes(nid)

    def _materialize_all_connected_notes(self) -> None:
        """Startup: materializa as notas dos cabos restaurados do banco."""
        for nid in list(self.frames):
            self._materialize_node_notes(nid)

    def _note_files_tick(self) -> bool:
        """Poll (500ms): se o agente editou notes/<id>.md, sincroniza de volta na nota do canvas."""
        if self.notes is None:
            return True
        try:
            for (nid, note_id), seen in list(self._note_file_mtime.items()):
                p = self._node_ws(nid) / "notes" / f"{note_id}.md"
                if not p.exists():
                    continue
                m = p.stat().st_mtime
                if m <= seen:  # nós mesmos gravamos / sem mudança
                    continue
                self._note_file_mtime[(nid, note_id)] = m
                note = self.notes.get(note_id)
                if note is None:
                    continue
                updated = file_to_note(note, p.parent, p.name)
                if updated.body == note.body and updated.title == note.title:
                    continue
                self.notes.save(updated)
                self._refresh_note_widget(note_id, updated)
                self._materialize_note_everywhere(note_id)  # propaga p/ outros nós
        except Exception as exc:
            _log.error("note_files_tick: %s", exc)
        return True

    def _refresh_note_widget(self, note_id: str, note) -> None:
        """Reflete na UI uma nota alterada pelo agente (sem clobber se o usuário está digitando)."""
        frame = self.note_frames.get(note_id)
        if frame is None:
            return
        body = getattr(frame, "_body_view", None)
        if body is not None and body.has_focus():
            return  # usuário editando — não sobrescreve
        if body is not None:
            body.get_buffer().set_text(note.body)
        ph = getattr(frame, "_note_ph", None)
        if ph is not None:
            ph.set_visible(not note.body.strip())
        if getattr(frame, "_body_stack", None) is not None:  # re-renderiza no modo atual
            view = frame._body_stack.get_visible_child_name() == "view"
            self._set_note_view(frame, view)

    def _remove_edges_for(self, eid: str) -> None:
        """Remove do store todos os cabos que tocam `eid` (ao apagar nó/nota)."""
        if self.edges is None:
            return
        for a, b in list(self.edges.list()):
            if a == eid or b == eid:
                self.edges.remove(a, b)
                self._edge_state.pop((a, b), None)
                self._on_cable_removed(a, b)  # hook (4b); no-op no 4a

    def _cancel_connect(self) -> None:
        if self._connect_src is not None:
            if self._connect_src[0] == "node":
                self.set_node_state(self._connect_src[1], "idle")
            self._connect_src = None
        self._connect_oneshot = False
        self._preview_rope = None
        if self._connect_cursor is not None:  # apaga o cabo-fantasma
            self._connect_cursor = None
            self.plane.queue_draw()
        self._update_hintbar()

    # -- cabos interativos: maestro-ask (ADR-11, Fase 3) --
    def start_ask_watcher(self, interval_ms: int = 500) -> None:
        """Liga o poll do mailbox (host roteia os 'maestro-ask' dos agentes) + sync das notas."""
        # 4b: materializa notas dos cabos restaurados e liga o poll de sync agente→nota
        self._materialize_all_connected_notes()
        GLib.timeout_add(interval_ms, self._note_files_tick)
        if self._sock_server is None:
            return
        # os listeners por agente já foram criados em _add_node; sobe a thread de accept
        threading.Thread(
            target=self._sock_server.serve, args=(self._on_sock_request,), daemon=True
        ).start()
        self._refresh_fleet_hud()  # HUD inicial (Etapa 4)
        GLib.timeout_add_seconds(3, self._anomaly_tick)  # vigilância ativa + HUD

    def _ask_edge_allowed(self, frm: str, to: str) -> bool:
        if self.edges is None:
            return False
        pairs = set(self.edges.list())
        return (frm, to) in pairs or (to, frm) in pairs  # cabo em qualquer sentido

    def _ask_delegate(self, to: str, prompt: str) -> str:
        # PADRÃO = HEADLESS (ADR-20): a resposta vem por um canal confiável e COMPLETO, com
        # contexto contínuo por agente (run_in_session usa --resume). Só o modo "live" (opt-in
        # via MAESTRO_ASK_MODE=live) raspa o terminal vivo p/ você VER a interação — mas é frágil
        # (~70%, trunca); se raspar algo, usa; senão cai no headless mesmo assim.
        if self._ask_mode == "live":
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
        if nid in self._mon_alerted:  # você focou → limpa o alerta de atenção (Fase 4)
            self._mon_alerted.discard(nid)
            self.set_node_state(nid, "idle")

    def _on_term_unfocus(self, nid: str) -> None:
        if self._focused_nid == nid:
            self._focused_nid = None

    # -- Monitorar atividade por terminal (Fase 4): quiescência de output → dot + notificação --
    def _node_monitor_ms(self, nid: str) -> int:
        try:
            s = float(self.model.node_cfg(nid, "monitor_ms") or "1.5")
        except ValueError:
            s = 1.5
        return int(max(0.3, min(30.0, s)) * 1000)

    def _set_node_monitor(self, nid: str, on: bool) -> None:
        """Liga/desliga o monitor de atividade do terminal (conecta `contents-changed`)."""
        cur = self._mon.pop(nid, None)
        frame = self.frames.get(nid)
        term = getattr(frame, "_term", None) if frame is not None else None
        if cur is not None:  # desliga o antigo (idempotente)
            if cur.get("quiet_id"):
                GLib.source_remove(cur["quiet_id"])
            if term is not None and cur.get("handler"):
                try:
                    term.disconnect(cur["handler"])
                except (TypeError, ValueError):
                    pass
        if on and term is not None:
            st = {"handler": None, "quiet_id": None, "active": False}
            st["handler"] = term.connect("contents-changed", self._mon_on_change, nid)
            self._mon[nid] = st

    def _mon_on_change(self, _term, nid) -> None:
        st = self._mon.get(nid)
        if st is None or self._focused_nid == nid:
            return  # não monitora o terminal em FOCO (você já está olhando)
        st["active"] = True
        if st["quiet_id"]:
            GLib.source_remove(st["quiet_id"])  # novo output → rearma a quiescência
        st["quiet_id"] = GLib.timeout_add(self._node_monitor_ms(nid), self._mon_quiet, nid)

    def _mon_quiet(self, nid) -> bool:
        st = self._mon.get(nid)
        if st is None:
            return False
        st["quiet_id"] = None
        if st.pop("skip", False):  # M1: ignora a quiescência do BANNER de restart (sem falso aviso)
            st["active"] = False
            return False
        if not st["active"] or self._focused_nid == nid:
            st["active"] = False
            return False
        frame = self.frames.get(nid)
        term = getattr(frame, "_term", None) if frame is not None else None
        text = self._term_text(term) if term is not None else ""
        if tui_busy(text):  # ainda "pensando" (TUI ocupada) → espera mais
            st["quiet_id"] = GLib.timeout_add(self._node_monitor_ms(nid), self._mon_quiet, nid)
            return False
        st["active"] = False
        self.set_node_state(nid, "waiting")  # "é sua vez": entra no ⚠ N + realce no minimapa
        self._mon_alerted.add(nid)
        name = self.model.node_name(nid, nid)
        # som OFF por padrão (só dot visual); opt-in por nó via node_cfg 'monitor_sound'
        want_sound = bool(self.model.node_cfg(nid, "monitor_sound"))
        notify(f"maestro: {name} parou", self._mon_summary(text), sound=want_sound)
        return False

    @staticmethod
    def _mon_summary(text: str) -> str:
        """Resumo (estilo Ombro): as últimas linhas não-vazias do output."""
        lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
        return "\n".join(lines[-4:])

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

    def _on_sock_request(self, node: str, data: dict) -> dict:
        """Trata 1 pedido vindo do socket do agente ``node`` (roda em thread do SockServer).

        IDENTIDADE POR CANAL (ADR-17): o remetente é ``node`` (qual socket aceitou a
        conexão) — qualquer ``frm`` no payload é IGNORADO. Devolve o dict de resposta.
        """
        try:
            depth = int(data.get("depth", 0))
        except (TypeError, ValueError):
            depth = 0
        raw_args = data.get("args", [])
        req = AskRequest(
            id=(str(data.get("id", "")) or "x")[:64],
            frm=node,  # <- canal, não o payload (anti-spoofing)
            to=str(data.get("to", "")),
            prompt=str(data.get("prompt", "")),
            depth=depth,
            cmd=str(data.get("cmd", "")),
            args=[str(a) for a in raw_args] if isinstance(raw_args, list) else [],
        )
        try:
            validate_req(req)
        except AskBusError as e:
            return {"id": req.id, "ok": False, "error": f"pedido inválido: {e}"}
        if req.cmd:  # comando Maestro mode → host (main thread, com gates)
            resp = self._maestro_handle(req)
        else:  # cabo (maestro-ask) → router; pinta o cabo de busy/done na main
            GLib.idle_add(self._ask_set_edge_state, req.frm, req.to, "busy")
            GLib.idle_add(self.plane.queue_draw)
            try:
                resp = self._ask_router.handle(req)
            except Exception as exc:  # noqa: BLE001 — nunca derruba o servidor de socket
                _log.error("ask handle falhou: %s", exc)
                resp = AskResponse(req.id, False, error="erro no host")
            GLib.idle_add(self._ask_reflect, req, resp)
        return {"id": resp.id, "ok": bool(resp.ok),
                "answer": resp.answer, "error": resp.error}

    def _ask_reflect(self, req, resp) -> bool:
        ok = bool(resp and resp.ok)
        # No modo live o prompt já aparece DIGITADO no terminal do B (feed_child) e o B
        # responde lá — não duplicamos com linha cosmética (era o que confundia). A cor do
        # cabo indica sucesso/falha.
        self._ask_set_edge_state(req.frm, req.to, "done" if ok else "failed")
        self.plane.queue_draw()
        return False

    def _box_dir(self, nid: str) -> str:
        """Caixa privada do agente ``nid`` (ADR-17): ``<bus>/box/<nid>`` (bind RW isolado)."""
        return os.path.join(str(self._ask_bus_dir), "box", nid)

    def _sock_register(self, nid: str, argv) -> None:
        """Cria o listener do socket da box do agente (só nós de agente: argv via bwrap)."""
        if self._sock_server is None or not self._ask_bus_dir:
            return
        if not argv or argv[0] != "bwrap":  # shells não têm socket (não são agentes)
            return
        box = self._box_dir(nid)
        try:
            os.makedirs(box, mode=0o700, exist_ok=True)
            self._sock_server.add_node(nid, box)
            self._agent_nids.add(nid)  # entra no fleet (cap global + kill-switch)
        except OSError as exc:
            _log.error("sock_register(%s) falhou: %s", nid, exc)

    # -- Maestro mode (Fase 6): comandos do agente-manager roteados pelo host (main thread) --
    MAESTRO_MAX_RECRUITS = 6  # limite anti-loop de recrutas POR MANAGER
    MAESTRO_FLEET_CAP = 12  # teto GLOBAL de agentes vivos no fleet (ADR-17, Etapa 2)
    MAESTRO_MAX_DEPTH = 2  # profundidade máx. da ÁRVORE de recrutamento (mgr→a→b), Etapa 3
    MAESTRO_SOFT_CAP = 8  # acima disso, recrutar exige confirmação humana (HITL)
    MAESTRO_SPAWN_RATE = 5  # máx. de recrutamentos por janela (rate-limit token-bucket)
    MAESTRO_SPAWN_WINDOW = 60.0  # janela do rate-limit, em segundos

    def _fleet_count(self) -> int:
        """Total de agentes vivos no fleet (fonte do hard-cap global e do kill-switch)."""
        return len(self._agent_nids)

    def _node_depth(self, nid: str) -> int:
        """Profundidade do nó na ÁRVORE de recrutamento (host-derivada, NÃO o depth do payload).

        0 = raiz (nó posto pelo humano). Sobe pela linhagem ``_recruited_by`` com guarda
        anti-ciclo (a árvore é 1-parent, mas protege contra estado corrompido)."""
        depth, cur, seen = 0, nid, set()
        while cur in self._recruited_by and cur not in seen:
            seen.add(cur)
            cur = self._recruited_by[cur]
            depth += 1
            if depth > 64:  # cinto de segurança
                break
        return depth

    MUTATING_CMDS = ("recruit", "dismiss", "wire", "reassign", "team")  # consomem rate-limit

    def _mutate_rate_ok(self, frm: str) -> bool:
        """Token-bucket POR-MANAGER para TODOS os comandos mutadores (5d): poda a janela,
        consome 1 token se couber. Cobre o respawn/edge-DoS de wire/reassign, não só recruit."""
        now = self._maestro_clock()
        log = [t for t in self._mutate_log.get(frm, []) if now - t < self.MAESTRO_SPAWN_WINDOW]
        if len(log) >= self.MAESTRO_SPAWN_RATE:
            self._mutate_log[frm] = log
            return False
        log.append(now)
        self._mutate_log[frm] = log
        return True

    def _recruit_needs_hitl(self, frm: str) -> bool:
        """Recrutar acima do soft-cap (mas abaixo do hard-cap) pede confirmação humana."""
        return self.MAESTRO_SOFT_CAP <= self._fleet_count() < self.MAESTRO_FLEET_CAP

    def _audit(self, event: str, **fields) -> None:
        """Registra um evento na trilha append-only (ADR-17). Best-effort, nunca levanta."""
        if self._ask_bus_dir:
            append_event(self._ask_bus_dir, event, **fields)

    def _build_fleet_hud(self) -> Gtk.Widget:
        """HUD do fleet (pílula topo-direita): nº de agentes, profundidade, aviso de ciclo."""
        lbl = Gtk.Label(label="")
        lbl.add_css_class("fleet-hud")
        lbl.set_halign(Gtk.Align.END)
        lbl.set_valign(Gtk.Align.START)
        lbl.set_margin_top(12)
        lbl.set_margin_end(12)
        lbl.set_visible(False)  # só aparece quando há agentes
        self._fleet_hud = lbl
        return lbl

    def _fleet_hud_text(self) -> str:
        """Texto do HUD (puro, testável): '🤖 N/CAP · prof D · ⚠ ciclo'."""
        n = self._fleet_count()
        depth = max((self._node_depth(x) for x in self._agent_nids), default=0)
        parts = [f"🤖 {n}/{self.MAESTRO_FLEET_CAP}"]
        if depth:
            parts.append(f"prof {depth}")
        if self.edges is not None and has_cycle(self.edges.list()):
            parts.append("⚠ ciclo")
        return "  ·  ".join(parts)

    def _refresh_fleet_hud(self) -> None:
        lbl = getattr(self, "_fleet_hud", None)
        if lbl is None:
            return
        n = self._fleet_count()
        text = self._fleet_hud_text() if n > 0 else ""
        verdict = "ok"
        if self._store is not None:  # F1 Bloco D: mostra o budget ($ gasto / teto) com cor
            soft, hard = budget.budget_limits(self._store)
            if hard:
                spent = budget.counted_spend(self._store)
                seg = f"💰 ${spent:.2f}/${hard:.2f}"
                text = f"{text}  ·  {seg}" if text else seg
                verdict = budget.budget_verdict(spent, soft, hard)
        for c in ("hud-soft", "hud-hard"):
            lbl.remove_css_class(c)
        if verdict != "ok":
            lbl.add_css_class("hud-hard" if verdict == "hard" else "hud-soft")
        lbl.set_visible(bool(text))
        if text:
            lbl.set_text(text)

    # -- F1 Bloco D: budget cap (o "limitador") --
    def _on_usage_update(self, aid: str) -> bool:
        """Um evento do usage_bus: atualiza o $ do nó + o HUD do budget + avisa se cruzou o soft."""
        self._refresh_node_cost(aid)
        self._refresh_fleet_hud()
        self._budget_soft_notify()
        return False  # idle_add one-shot

    def _budget_top_spender(self) -> str | None:
        """Nó que mais gastou (mostrado no aviso — o humano decide quem dispensar)."""
        led = getattr(self.controller, "usage_ledger", None) if self.controller else None
        if led is None:
            return None
        best, best_c = None, 0.0
        for nid in self.frames:
            c = led.get(nid).cost_usd
            if c > best_c:
                best, best_c = nid, c
        return self.model.node_name(best, best) if best else None

    def _budget_soft_notify(self) -> None:
        """Aviso ÚNICO ao cruzar o soft (custo é monotônico → não repetir a cada turno). Rearma
        quando volta a 'ok' (reset). Só aviso — nunca bloqueia (o hard barra no delegate)."""
        if self._store is None:
            return
        v = budget.check(self._store)
        if v == "soft" and not getattr(self, "_budget_notified", False):
            self._budget_notified = True
            top = self._budget_top_spender()
            body = f"gasto ${budget.counted_spend(self._store):.2f}"
            notify("maestro: budget no aviso", body + (f" · maior: {top}" if top else ""),
                   sound=False)
        elif v == "ok":
            self._budget_notified = False

    def _budget_dialog(self, *_a) -> None:
        """Config dos LIMITES — teto de gasto (hard/soft $) + limiar de RAM por nó (MB) —
        e zerar. SÓ o host mexe (nunca comando de agente). Dual-persistência de
        PROPÓSITO: budget = contador no store (ADR-22, monotônico); limiar de RAM =
        `ui_state` (config de UI, "abre igual fechou") — não "unificar"."""
        if self._store is None:
            return
        dlg = Gtk.Window(title="Limites — gasto do fleet ($) e RAM por nó")
        dlg.set_modal(True)
        dlg.set_default_size(380, -1)  # sem isto, o label wrap estica a janela p/ tela cheia
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for m in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{m}")(14)
        hint = Gtk.Label(xalign=0, wrap=True, max_width_chars=44, label=(
            "Teto de gasto dos agentes (USD). Vazio = sem teto. No HARD, os runs mediados param "
            "até você zerar. SOFT (só aviso) vazio = 75% do hard. O contador só sobe — o agente "
            "não consegue baixá-lo; zere você aqui."))
        hint.add_css_class("dim-label")
        box.append(hint)

        def row(label, key, placeholder="$"):
            r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            r.append(Gtk.Label(label=label))
            e = Gtk.Entry()
            e.set_max_width_chars(8)
            e.set_placeholder_text(placeholder)
            e.set_text(self._store.get_ui(f"budget_{key}") or "")
            r.append(e)
            box.append(r)
            return e

        hard_e = row("Hard (barra):", "hard")
        soft_e = row("Soft (avisa):", "soft")
        ram_hint = Gtk.Label(xalign=0, wrap=True, max_width_chars=44, label=(
            "RAM por nó (MB): notifica quando a árvore de um nó passar do limiar — "
            "considere ⏏ descarregar. Vazio = desligado. Re-arma abaixo de 90% do limiar."))
        ram_hint.add_css_class("dim-label")
        box.append(ram_hint)
        ram_r = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ram_r.append(Gtk.Label(label="RAM por nó (avisa):"))
        ram_e = Gtk.Entry()
        ram_e.set_max_width_chars(8)
        ram_e.set_placeholder_text("MB")
        ram_e.set_text(self._store.get_ui("ram_limit_mb") or "")
        ram_r.append(ram_e)
        box.append(ram_r)
        _spent = budget.counted_spend(self._store)
        spent_lbl = Gtk.Label(xalign=0, label=f"Gasto contado agora: ${_spent:.4f}")
        spent_lbl.add_css_class("dim-label")
        box.append(spent_lbl)
        btns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END)
        zerar = Gtk.Button(label="Zerar gasto")

        def do_zerar(_b):
            budget.reset_budget(self._store)
            self._budget_notified = False
            spent_lbl.set_text("Gasto contado agora: $0.0000")
            self._refresh_fleet_hud()

        zerar.connect("clicked", do_zerar)
        salvar = Gtk.Button(label="Salvar")
        salvar.add_css_class("suggested-action")

        def do_salvar(_b):
            self._store.set_ui("budget_hard", hard_e.get_text().strip())
            self._store.set_ui("budget_soft", soft_e.get_text().strip())
            self._store.set_ui("ram_limit_mb", ram_e.get_text().strip())  # parse no uso
            self._ram_alerted.clear()  # limiar mudou → rearma os alertas de RAM
            self._budget_notified = False  # rearma o aviso
            self._refresh_fleet_hud()
            dlg.close()

        salvar.connect("clicked", do_salvar)
        btns.append(zerar)
        btns.append(salvar)
        box.append(btns)
        dlg.set_child(box)
        dlg.present()

    def _anomaly_tick(self) -> bool:
        """Vigilância ATIVA (Etapa 4): rajada de recrutamentos bloqueados → kill-switch
        AUTOMÁTICO. Tira o trail/HUD do modo passivo. Roda na main thread (GLib timeout)."""
        if self._sock_server is None:
            return True
        try:
            self._refresh_fleet_hud()
            events = read_events(self._ask_bus_dir) if self._ask_bus_dir else []
            if spawn_anomaly(events, now=time.time()) and self._fleet_count() > 0:
                self._audit("anomaly_killswitch", fleet=self._fleet_count())
                killed = self._kill_all_agents()
                _log.warning("anomalia de spawn detectada → kill-switch (%d mortos)", killed)
        except Exception as exc:  # nunca derruba o tick
            _log.error("anomaly_tick falhou: %s", exc)
        return True  # continua

    def _kill_all_agents(self) -> int:
        """KILL-SWITCH global (ADR-17): mata o processo de TODOS os agentes vivos.

        Cada agente é seu próprio bwrap (``--unshare-pid``) → o SIGKILL no filho
        COLAPSA a árvore interna (ceifa a subárvore, não só o topo). Em seguida DESARMA
        o Maestro mode de todos os nós: recrutar fica bloqueado até você religar o toggle
        (re-armar = gate humano). Devolve quantos processos foram sinalizados.
        """
        nids = list(self._agent_nids)
        killed = 0
        for nid in nids:
            term = getattr(self.frames.get(nid), "_term", None)
            if term is not None and self._signal_child(term, signal.SIGKILL):
                killed += 1
        for nid in list(self.frames):  # desarma TODOS os managers (re-armar é manual)
            if self.model.node_cfg(nid, "maestro"):
                self.model.set_node_cfg(nid, "maestro", "")
        self._audit("kill_all", killed=killed, fleet_before=len(nids))
        self._refresh_fleet_hud()
        self.plane.queue_draw()
        return killed

    def _confirm_kill_all(self) -> None:
        """Confirmação do kill-switch (ação destrutiva: para TODOS os agentes)."""
        n = self._fleet_count()
        dlg, box = self._dialog("⛔ Parar todos os agentes")
        if n == 0:
            box.append(Gtk.Label(label="Nenhum agente vivo para parar."))
            ok = Gtk.Button(label="OK")
            ok.connect("clicked", lambda _b: dlg.destroy())
            box.append(ok)
            dlg.present()
            return
        msg = Gtk.Label(
            label=f"Isso MATA o processo de {n} agente(s) e desarma o Maestro mode.\n"
                  "O trabalho em andamento é interrompido. Religue o toggle p/ recrutar de novo.")
        msg.set_wrap(True)
        msg.set_xalign(0.0)
        box.append(msg)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda _b: dlg.destroy())
        stop = Gtk.Button(label="⛔ Parar tudo")
        stop.add_css_class("destructive-action")

        def _do(_b):
            dlg.destroy()
            self._kill_all_agents()

        stop.connect("clicked", _do)
        row.append(cancel)
        row.append(stop)
        box.append(row)
        dlg.present()

    def _maestro_handle(self, req):
        """Worker thread: marshala o comando p/ a MAIN thread (idle_add) e espera a resposta."""
        result: dict = {}
        done = threading.Event()
        GLib.idle_add(self._maestro_exec, req, result, done)
        if not done.wait(timeout=50):  # folga p/ o HITL (humano confirmar); shim espera 60s
            return AskResponse(req.id, False, error="timeout no host")
        if result.get("ok"):
            return AskResponse(req.id, True, result.get("answer", "ok"))
        return AskResponse(req.id, False, error=result.get("error", "erro"))

    def _own_recruit(self, frm: str, nid: str) -> bool:
        """`nid` é recruta DIRETO de `frm`? Decisão de AUTORIDADE (ADR-17): vem da linhagem
        host-only `_recruited_by` (infalsificável) — NUNCA dos cabos, que o agente cria com
        `wire` (senão = confused deputy: wire numa vítima → dismiss/reassign nela)."""
        return bool(nid) and self._recruited_by.get(nid) == frm

    def _maestro_connected(self, nid: str) -> list:
        """Nós LIGADOS a `nid` por cabo. SÓ p/ exibição (list)/UI — NÃO p/ autoridade."""
        out = []
        for a, b in self.edges.list():
            if a == nid and b in self.frames:
                out.append(b)
            elif b == nid and a in self.frames:
                out.append(a)
        return out

    def _place_below(self, nid: str) -> tuple[int, int]:
        """Posição (base) ABAIXO do nó `nid`, empilhando por nº de recrutas — NUNCA sobrepõe
        o que já existe (se a pilha colidir com algo, cai pra uma área genuinamente livre)."""
        x, y = self._base_pos.get(nid, (60.0, 60.0))
        _w, h = self._node_size.get(nid, (BASE_W, BASE_H))
        n = len(self._maestro_connected(nid))
        cy = y + h + 40 + n * (h + 24)
        if not self._rect_overlaps_any(x, cy, BASE_W, BASE_H):
            return (int(x), int(cy))
        ox, oy = self._free_region_origin()
        return (int(ox), int(oy))

    def _maestro_exec(self, req, result: dict, done) -> bool:
        try:
            # HITL (Etapa 3): recrutar acima do soft-cap pausa e PERGUNTA ao humano. O
            # diálogo é assíncrono → `done` é setado no callback da decisão, não aqui.
            if req.cmd == "recruit" and self._recruit_needs_hitl(req.frm):
                self._hitl_recruit(req, result, done)
                return False
            # Fase B (docs/14 §6): `team` SEMPRE pede confirmação humana — NL desenha,
            # humano confirma, determinístico executa. Nunca materializa direto por
            # decisão do agente, então também não passa pelo `_maestro_dispatch` genérico.
            if req.cmd == "team":
                self._hitl_team(req, result, done)
                return False
            self._maestro_dispatch(req, result)
        except Exception as exc:
            result.update(ok=False, error=str(exc))
        done.set()
        return False  # idle one-shot

    def _apply_recruit_decision(self, approve: bool, req, result: dict, done) -> None:
        """Aplica a decisão humana do HITL (separado do GTK p/ ser testável)."""
        if approve:
            self._maestro_dispatch(req, result)
        else:
            self._audit("recruit_denied", manager=req.frm, fleet=self._fleet_count())
            result.update(ok=False, error="recrutamento negado pelo humano")
        done.set()

    def _hitl_recruit(self, req, result: dict, done) -> None:
        """Pausa-e-pergunta: o humano aprova/nega um recrutamento acima do soft-cap.

        Aprovar → roda o dispatch; negar/timeout → recusa. `done` é setado na decisão.
        Factorado p/ testes poderem sobrescrever (auto-aprovar/negar) sem GTK.
        """
        decided = {"v": False}
        dlg, box = self._dialog("Confirmar recrutamento (fleet grande)")

        def decide(approve: bool):
            if decided["v"]:
                return False
            decided["v"] = True
            dlg.destroy()  # F5: destrói o diálogo em TODOS os caminhos (inclui o timeout)
            self._apply_recruit_decision(approve, req, result, done)
            return False

        msg = Gtk.Label(
            label=f"O agente '{req.frm}' quer recrutar mais um (fleet em "
                  f"{self._fleet_count()}/{self.MAESTRO_FLEET_CAP}). Aprovar?")
        msg.set_wrap(True)
        msg.set_xalign(0.0)
        box.append(msg)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_halign(Gtk.Align.END)
        deny = Gtk.Button(label="Negar")
        deny.connect("clicked", lambda _b: decide(False))
        appr = Gtk.Button(label="Aprovar")
        appr.add_css_class("suggested-action")
        appr.connect("clicked", lambda _b: decide(True))
        row.append(deny)
        row.append(appr)
        box.append(row)
        # se o humano não decidir a tempo, nega (o agente não fica preso) + fecha o diálogo
        GLib.timeout_add_seconds(40, lambda: decide(False))
        dlg.present()

    def _hitl_team(self, req, result: dict, done) -> None:
        """`team` (Fase B, docs/14 §6): o manager manda um `TeamTemplate` em JSON; o host
        NUNCA materializa direto — só parseia/valida e abre uma confirmação humana. Os
        MESMOS gates do `_maestro_dispatch` genérico (este comando não passa por ele, já
        que a decisão é sempre assíncrona)."""
        frm, args = req.frm, req.args
        if not self.model.node_cfg(frm, "maestro"):
            result.update(ok=False, error="este terminal não está em Maestro mode")
            done.set()
            return
        if self.controller is None or not self._ask_bus_dir or self.edges is None:
            result.update(ok=False, error="orquestrador/cabos indisponíveis")
            done.set()
            return
        if not self._mutate_rate_ok(frm):
            self._audit("rate_blocked", manager=frm, cmd="team")
            result.update(ok=False, error="muitos comandos em pouco tempo; aguarde")
            done.set()
            return
        if not args or not args[0].strip():
            result.update(ok=False, error="uso: team '<json do TeamTemplate>'")
            done.set()
            return
        spec_text = args[0]
        if len(spec_text.encode("utf-8")) > ASK_MAX_PROMPT_BYTES:  # entrada não-confiável
            result.update(ok=False, error=f"spec grande demais (máx {ASK_MAX_PROMPT_BYTES} bytes)")
            done.set()
            return
        try:
            data = json.loads(spec_text)
            if not isinstance(data, dict):
                raise TypeError("spec precisa ser um objeto JSON")
            spec = TeamTemplate.from_dict(data)
            validate_team_template(spec)
        except Exception as exc:  # noqa: BLE001 — parse de entrada NÃO-CONFIÁVEL, nunca derruba
            result.update(ok=False, error=f"spec inválido: {exc}")
            done.set()
            return
        self._confirm_team_from_agent(frm, spec, result, done)

    def _apply_team_decision(self, approve: bool, frm: str, spec: TeamTemplate,
                              result: dict, done) -> None:
        """Aplica a decisão humana do `team` (separado do GTK p/ ser testável, espelha
        `_apply_recruit_decision`). Aprovar → `_materialize_team(spec, manager=frm)` — o
        manager é SEMPRE o `frm` derivado do canal (ADR-17/18: autoridade nunca vem de
        campo que o agente preenche; `spec.manager`, se vier no JSON, é ignorado)."""
        if approve:
            mat = self._materialize_team(spec, manager=frm)
            if mat["ok"]:
                msg = (f"Equipe '{spec.name}' montada: {mat['groups']} grupo(s), "
                       f"{mat['agents']} agente(s).")
                if mat["warnings"]:
                    msg += " ⚠ " + "; ".join(mat["warnings"])
                result.update(ok=True, answer=msg)
            else:
                result.update(ok=False, error=mat["error"])
        else:
            self._audit("team_denied", manager=frm, template=spec.name)
            result.update(ok=False, error="montagem da equipe negada pelo humano")
        done.set()

    def _confirm_team_from_agent(self, frm: str, spec: TeamTemplate, result: dict, done) -> None:
        """Diálogo de confirmação do `team` (assíncrono; `done` setado na decisão via
        `_apply_team_decision`)."""
        decided = {"v": False}
        dlg, box = self._dialog(f"🧩 Confirmar equipe — '{spec.name}'")
        preview = "\n".join(
            f"• {g.name}: " + ", ".join(m.name for m in g.members) for g in spec.groups
        )
        msg = Gtk.Label(
            label=f"O agente '{frm}' quer montar a equipe '{spec.name}' "
                  f"({spec.total_members} agente(s)):\n\n{preview}\n\nMontar?")
        msg.set_wrap(True)
        msg.set_xalign(0.0)
        box.append(msg)

        def decide(approve: bool):
            if decided["v"]:
                return False
            decided["v"] = True
            dlg.destroy()  # destrói em TODOS os caminhos (inclui timeout)
            self._apply_team_decision(approve, frm, spec, result, done)
            return False

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_halign(Gtk.Align.END)
        deny = Gtk.Button(label="Negar")
        deny.connect("clicked", lambda _b: decide(False))
        appr = Gtk.Button(label="Montar")
        appr.add_css_class("suggested-action")
        appr.connect("clicked", lambda _b: decide(True))
        row.append(deny)
        row.append(appr)
        box.append(row)
        # decisão maior que um recrutamento simples -> mais tempo antes de negar sozinho
        GLib.timeout_add_seconds(90, lambda: decide(False))
        dlg.present()

    def _maestro_dispatch(self, req, result: dict) -> None:
        frm, cmd, args = req.frm, req.cmd, req.args
        if not self.model.node_cfg(frm, "maestro"):
            result.update(ok=False, error="este terminal não está em Maestro mode")
            return
        if self.controller is None or not self._ask_bus_dir or self.edges is None:
            result.update(ok=False, error="orquestrador/cabos indisponíveis")
            return
        if cmd in self.MUTATING_CMDS and not self._mutate_rate_ok(frm):  # rate-limit p/ TODOS (5d)
            self._audit("rate_blocked", manager=frm, cmd=cmd)
            result.update(ok=False, error="muitos comandos em pouco tempo; aguarde")
            return
        if cmd == "recruit":
            if not args:
                result.update(ok=False, error="uso: recruit <agente> [papel]")
                return
            base, role = args[0], (args[1] if len(args) > 1 else "")
            if base not in installed_agents():
                result.update(ok=False, error=f"agente '{base}' não instalado")
                return
            if self._fleet_count() >= self.MAESTRO_FLEET_CAP:  # teto GLOBAL (ADR-17)
                self._audit("recruit_blocked", manager=frm, reason="fleet_cap",
                            fleet=self._fleet_count())
                result.update(ok=False,
                              error=f"limite GLOBAL de {self.MAESTRO_FLEET_CAP} agentes atingido")
                return
            depth = self._node_depth(frm)
            if depth >= self.MAESTRO_MAX_DEPTH:  # profundidade da árvore (Etapa 3)
                self._audit("recruit_blocked", manager=frm, reason="max_depth", depth=depth)
                result.update(ok=False, error=f"profundidade máxima ({depth} níveis) atingida")
                return
            if len(self._maestro_connected(frm)) >= self.MAESTRO_MAX_RECRUITS:
                result.update(ok=False, error=f"limite de {self.MAESTRO_MAX_RECRUITS} recrutas")
                return
            nid = self._new_agent_terminal(base, default=self._place_below(frm))
            if nid is None:
                why = getattr(self, "_last_recruit_error", "") or "verifique auth/limite do CLI"
                self._audit("recruit_blocked", manager=frm, reason="spawn_fail", detail=why)
                result.update(ok=False, error=f"falha ao criar '{base}': {why}")
                return
            self.model.set_node_cfg(nid, "maestro", "")  # recruta NASCE sem poder recrutar
            self._recruited_by[nid] = frm  # linhagem (profundidade)
            self.edges.add(frm, nid)
            if role:
                self.model.set_node_cfg(nid, "role", role)
                self._apply_node_role(nid)
                self._respawn_node(nid)  # reinicia p/ a IA já abrir com o papel
            self._ask_hint(frm, nid)
            self._wake_cables()
            self.plane.queue_draw()
            self._audit("recruit", manager=frm, node=nid, agent=base, role=role,
                        depth=self._node_depth(nid), fleet=self._fleet_count())
            self._refresh_fleet_hud()
            extra = f", papel '{role}'" if role else ""
            result.update(ok=True, answer=f"recrutado '{nid}' (agente {base}{extra}), por cabo.")
        elif cmd == "list":
            conn = self._maestro_connected(frm)
            if not conn:
                result.update(ok=True, answer="(sem recrutas conectados)")
                return
            lines = [f"- {self.model.node_name(n, n)} (papel: "
                     f"{(self._node_role(n).name if self._node_role(n) else '—')})" for n in conn]
            result.update(ok=True, answer="Recrutas conectados:\n" + "\n".join(lines))
        elif cmd == "dismiss":
            if not args or not self._own_recruit(frm, args[0]):  # autoridade = linhagem (5a)
                result.update(ok=False, error="uso: dismiss <nó> (só um recruta DIRETO seu)")
                return
            self._close_node(args[0])
            self._audit("dismiss", manager=frm, node=args[0])
            result.update(ok=True, answer=f"dispensado '{args[0]}'.")
        elif cmd == "wire":
            if not args:
                result.update(ok=False, error="uso: wire <a> [b] (b padrão = você)")
                return
            a = args[0]
            b = args[1] if len(args) > 1 else frm
            # autoridade host-only: só liga VOCÊ ou seus recrutas DIRETOS (não nós alheios)
            if not all(n == frm or self._own_recruit(frm, n) for n in (a, b)):
                result.update(ok=False, error="só liga você ou um recruta DIRETO seu")
                return
            if has_cycle(self.edges.list() + [(a, b)]):  # recusa cabo que fecha ciclo (5a/F7)
                result.update(ok=False, error="recusado: esse cabo fecharia um ciclo")
                return
            self.edges.add(a, b)
            a_node, b_node = a in self.frames, b in self.frames
            if a_node and b_node:
                self._ask_hint(a, b)
            else:
                self._on_note_cable_added(a, b, "node" if a_node else "note",
                                          "node" if b_node else "note")
            self._wake_cables()
            self.plane.queue_draw()
            self._audit("wire", manager=frm, a=a, b=b)
            result.update(ok=True, answer=f"cabo {a} ↔ {b} ligado.")
        elif cmd == "reassign":
            if len(args) < 2 or not (args[0] == frm or self._own_recruit(frm, args[0])):
                result.update(ok=False, error="uso: reassign <nó> <papel> (você ou recruta seu)")
                return
            self.model.set_node_cfg(args[0], "role", args[1])
            self._apply_node_role(args[0])
            self._respawn_node(args[0])
            self._audit("reassign", manager=frm, node=args[0], role=args[1])  # auditoria (5a)
            result.update(ok=True, answer=f"'{args[0]}' reatribuído ao papel '{args[1]}'.")
        else:
            result.update(ok=False, error=f"comando desconhecido: {cmd}")

    def _ask_set_edge_state(self, frm: str, to: str, state: str) -> None:
        if self.edges is None:
            return
        for e in self.edges.list():
            if set(e) == {frm, to}:
                self._edge_state[e] = state
                if state == "busy":
                    self._edge_flow[e] = (frm, to)  # sentido real do dado (quem envia → recebe)
                else:
                    self._edge_flow.pop(e, None)
        self._wake_cables()

    # -- animação de fluxo do cabo (só enquanto há handoff "busy": poupa bateria) --
    def _has_flowing_edge(self) -> bool:
        return any(st == "busy" for st in self._edge_state.values())

    def _wake_cables(self) -> None:
        """Acorda o tick da corda (física + fluxo). Chamar quando algo pode mexer os cabos:
        cards movendo/redimensionando, cabo criado/removido, edge virando busy, abertura."""
        self._cable_rest = 0
        if self._cable_tick_id is None:
            self._cable_tick_id = self.plane.add_tick_callback(self._cable_tick)

    def _get_rope(self, edge, p0, p3):
        """Corda Verlet do cabo (cria reta entre as âncoras na 1ª vez)."""
        r = self._ropes.get(edge)
        if r is None:
            r = make_rope(p0, p3)
            self._ropes[edge] = r
        return r

    def _cable_points(self, edge, p0, p3):
        """Pontos da curva do cabo segundo o modo de física atual (`_cable_phys`). Usa as
        PONTAS SUAVIZADAS (`_anchor_sm`, atualizadas no tick) p/ a troca de âncora do ímã não
        teleportar; cai pro magnet cru se ainda não há suavização (1º frame)."""
        e0, e3 = self._anchor_sm.get(edge, (p0, p3))
        if self._cable_phys == "catenary":
            return catenary_pts(e0, e3, sag_ratio=CATENARY_SAG)
        if self._cable_phys == "spring":
            ctrl = self._springs.get(edge) or spring_target(e0, e3, SPRING_SAG)
            return quad_bezier_pts(e0, ctrl, e3)
        return self._get_rope(edge, e0, e3)["pts"]

    def _ease_anchors(self, edge, p0, p3):
        """Escorrega as pontas guardadas até o alvo do ímã (suaviza a troca de âncora).
        Devolve (e0, e3, deslocamento). 1ª vez fixa direto (sem slide na criação)."""
        cur = self._anchor_sm.get(edge)
        if cur is None:
            self._anchor_sm[edge] = (p0, p3)
            return p0, p3, 0.0
        c0, c3 = cur
        e = ANCHOR_EASE
        n0 = (c0[0] + (p0[0] - c0[0]) * e, c0[1] + (p0[1] - c0[1]) * e)
        n3 = (c3[0] + (p3[0] - c3[0]) * e, c3[1] + (p3[1] - c3[1]) * e)
        self._anchor_sm[edge] = (n0, n3)
        return n0, n3, max(math.dist(n0, c0), math.dist(n3, c3))

    def _step_ropes(self) -> bool:
        """Avança a física do modo atual p/ todos os cabos vivos; poda os que sumiram.
        Devolve True se ALGO ainda se mexe (acima do limiar de repouso). Catenária é
        estática, mas a suavização das pontas ainda 'anda' por alguns frames."""
        if self.edges is None:
            return False
        z = self.model.zoom()
        live, max_moved = set(), 0.0
        for src, dst in self.edges.list():
            sbox, dbox = self._cable_box(src, z), self._cable_box(dst, z)
            if sbox is None or dbox is None:
                continue
            p0, p3 = cable_anchors(sbox, dbox)
            edge = (src, dst)
            live.add(edge)
            e0, e3, amoved = self._ease_anchors(edge, p0, p3)  # pontas suavizadas
            max_moved = max(max_moved, amoved)
            if self._cable_phys == "verlet":
                max_moved = max(max_moved, step_rope(self._get_rope(edge, e0, e3), e0, e3))
            elif self._cable_phys == "spring":  # mola: ctrl escorrega até o alvo (sem oscilar)
                tx, ty = spring_target(e0, e3, SPRING_SAG)
                cx, cy = self._springs.get(edge, (tx, ty))
                nx, ny = cx + (tx - cx) * 0.18, cy + (ty - cy) * 0.18
                self._springs[edge] = (nx, ny)
                max_moved = max(max_moved, math.hypot(nx - cx, ny - cy))
        for store in (self._ropes, self._springs, self._anchor_sm):
            for dead in set(store) - live:
                store.pop(dead, None)
        # cabo-fantasma (modo conectar): mesma física, ponta = cursor. No verlet a corda precisa
        # avançar por frame p/ cair/balançar igual ao cabo real; mantém o tick vivo enquanto liga.
        anc = self._preview_anchors(z)
        if anc is not None:
            p0, cur = anc
            if self._cable_phys == "verlet":
                if self._preview_rope is None:
                    self._preview_rope = make_rope(p0, cur)
                max_moved = max(max_moved, step_rope(self._preview_rope, p0, cur))
            max_moved = max(max_moved, ROPE_REST_EPS * 2.0)  # segue vivo até soltar/cancelar
        else:
            self._preview_rope = None
        return max_moved > ROPE_REST_EPS

    def _cable_tick(self, _widget, frame_clock) -> bool:  # pragma: no cover - precisa de GTK
        moving = self._step_ropes()  # física da corda (sag/balanço)
        busy = self._has_flowing_edge()
        if busy:  # avança a fase do tracejado de fluxo
            t = frame_clock.get_frame_time()  # microssegundos (monotônico)
            self._cable_anim_phase = (t / 1000.0 * CABLE_FLOW_SPEED) % CABLE_DASH_PERIOD
        label = self._phys_label_frames > 0  # flash do rótulo de modo (mantém o tick vivo)
        if label:
            self._phys_label_frames -= 1
        self.plane.queue_draw()
        if moving or busy or label:  # ainda há trabalho: segue
            self._cable_rest = 0
            return GLib.SOURCE_CONTINUE
        self._cable_rest += 1  # assentou e nada fluindo: dorme após alguns frames
        if self._cable_rest > CABLE_SETTLE_FRAMES:
            self._cable_tick_id = None
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _ask_hint(self, src: str, dst: str) -> None:
        """Avisa ambos os terminais que podem conversar pelo cabo (maestro-ask)."""
        if self._sock_server is None:
            return
        for a, b in ((src, dst), (dst, src)):
            fr = self.frames.get(a)
            term = getattr(fr, "_term", None) if fr is not None else None
            if term is not None:
                term.feed(
                    f"\r\n\x1b[2m[maestro] cabo ligado a '{b}'. Para perguntar: "
                    f'"$MAESTRO_BIN/maestro-ask" {b} "<sua pergunta>"\x1b[0m\r\n'.encode()
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
        # atalho CUSTOM por terminal (Fase 3): foca o nó cujo node_cfg 'shortcut' bate (prevalece
        # sobre o por-ordem). Captura/compara via Gtk.accelerator_name (mesma serialização).
        tgt = self._shortcut_target(keyval, state)
        if tgt is not None:
            self._focus_node(tgt)
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
        if keyval == Gdk.KEY_Escape and self._placing_spec is not None:
            self._cancel_placing()
            return True
        if keyval in (Gdk.KEY_p, Gdk.KEY_P) and ctrl and shift:
            order = ["verlet", "catenary", "spring"]  # cicla a física do cabo (gosto do usuário)
            i = order.index(self._cable_phys) if self._cable_phys in order else 0
            self._cable_phys = order[(i + 1) % len(order)]
            self.model.set_cable_phys(self._cable_phys)  # persiste (abre igual fechou)
            self._springs.clear()  # recomeça a mola limpa ao entrar no modo
            self._phys_label_frames = PHYS_LABEL_FRAMES  # flash do nome do modo
            self._wake_cables()
            self.plane.queue_draw()
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
        for note_id in self._note_base:  # notas entram no bbox (cabo até nota distante)
            nb = self._cable_box(note_id, z)
            if nb is not None:
                rects.append((nb[0], nb[1], nb[0] + nb[2], nb[1] + nb[3]))
        for gid in self._group_base:
            gx, gy, gw, gh = self._group_disp_rect(gid)
            rects.append((gx, gy, gx + gw, gy + gh))
        if self._placing_spec is not None and self._placing_cursor is not None:
            camx, camy = self._cam  # prévia fantasma também precisa de superfície pra desenhar
            px, py = self._placing_cursor[0] - camx, self._placing_cursor[1] - camy
            pw, ph = self._placing_size()
            rects.append((px, py, px + pw * z, py + ph * z))
        if not rects:
            return None
        x0 = min(r[0] for r in rects)
        y0 = min(r[1] for r in rects)
        x1 = max(r[2] for r in rects)
        y1 = max(r[3] for r in rects)
        pad = 60.0
        return (x0 - pad, y0 - pad, (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad)

    def _cable_box(self, eid, z):
        """(x,y,w,h) em coords-tela (base*zoom; o translate da câmera vem no draw) do endpoint
        de cabo (NÓ ou NOTA), ou None se ausente. Usa os limites REAIS do frame (compute_bounds
        = cabeçalho + corpo) p/ as 8 âncoras caírem nas bordas de verdade — o tamanho armazenado
        (`_node_size` = só o terminal, sem o cabeçalho) deixava as âncoras de BAIXO acima da borda.
        Fallback p/ o cálculo por tamanho armazenado quando o frame ainda não tem alocação."""
        frame = self.frames.get(eid) or self.note_frames.get(eid)
        if frame is None:
            return None
        ok, r = frame.compute_bounds(self.plane)
        if ok and r.size.width > 0 and r.size.height > 0:
            camx, camy = self._cam
            return (r.origin.x - camx, r.origin.y - camy, r.size.width, r.size.height)
        # fallback: sem alocação ainda → estima pelo tamanho armazenado
        if eid in self.frames:
            bx, by = to_display(self._base_pos.get(eid, (0.0, 0.0)), z)
            nw, nh = self._node_size.get(eid, (BASE_W, BASE_H))
            return (bx, by, nw * z, nh * z)
        bx, by = to_display(self._note_base.get(eid, (0.0, 0.0)), z)
        return (bx, by, NOTE_W_DEFAULT * z, NOTE_H_DEFAULT * z)

    # -- cabos (handoffs): desenhados no snapshot do _Plane --
    def _draw_cables_cr(self, cr):
        z = self.model.zoom()
        # grid agora é background CSS (GPU), não cairo — ver _apply_grid()
        self._draw_groups_cr(cr)  # C2: grupos/áreas, atrás dos cabos e dos nós

        # SÓ cabos EXPLÍCITOS do usuário (modo conectar). Cada cabo é uma CORDA Verlet
        # (física): pontas no ímã de 8 pontos, miolo cai/balança. Cor azul; estado no handoff.
        if self.edges is not None:
            for src, dst in self.edges.list():
                sbox, dbox = self._cable_box(src, z), self._cable_box(dst, z)
                if sbox is None or dbox is None:  # endpoint ausente (nó/nota inexistente)
                    continue
                p0, p3 = cable_anchors(sbox, dbox)
                pts = self._cable_points((src, dst), p0, p3)
                st = self._edge_state.get((src, dst))
                cr.set_source_rgb(*_cable_rgb(st))
                # handoff ativo: tracejado correndo no SENTIDO REAL do dado (quem envia → recebe),
                # não na ordem de criação do cabo (bidirecional). O path vai p0→p3; offset negativo
                # corre nesse sentido, positivo inverte. Escala c/ zoom.
                if st == "busy":
                    flow = self._edge_flow.get((src, dst))
                    forward = flow is None or flow == (src, dst)  # flow==(dst,src) → inverte
                    off = (-self._cable_anim_phase if forward else self._cable_anim_phase) * z
                    cr.set_dash([CABLE_DASH_ON * z, CABLE_DASH_OFF * z], off)
                else:
                    cr.set_dash([])
                cr.set_line_width(2.5)  # largura da corda (re-setada: o anel da bolinha usa 1.5)
                self._stroke_rope(cr, pts)
                cr.stroke()
                # bolinha em cada ponta (aparece SÓ porque o cabo existe = após conectar):
                # miolo branco p/ contraste + anel na cor do cabo. Tamanho fixo de tela.
                cr.set_dash([])
                cr.set_line_width(1.5)
                for px, py in (pts[0], pts[-1]):
                    cr.arc(px, py, CABLE_DOT_RADIUS, 0.0, 2.0 * math.pi)
                    cr.set_source_rgb(1.0, 1.0, 1.0)
                    cr.fill()
                    cr.arc(px, py, CABLE_DOT_RADIUS, 0.0, 2.0 * math.pi)
                    cr.set_source_rgb(*_cable_rgb(st))
                    cr.stroke()
            cr.set_dash([])  # reset p/ não vazar tracejado em outros desenhos do cr
        self._draw_connect_preview_cr(cr, z)  # cabo-fantasma seguindo o cursor (modo conectar)
        self._draw_placing_preview_cr(cr, z)  # prévia do item a posicionar (clique-pra-criar)
        if self._phys_label_frames > 0:  # flash do modo ao trocar (Ctrl+Shift+P); some sozinho
            self._draw_phys_label(cr)

    def _draw_placing_preview_cr(self, cr, z) -> None:
        """Contorno tracejado do item a nascer, seguindo o cursor no modo "clique pra
        posicionar" (`_start_placing`) — some ao clicar (cria ali) ou Esc (cancela)."""
        if self._placing_spec is None or self._placing_cursor is None:
            return
        camx, camy = self._cam
        x, y = self._placing_cursor[0] - camx, self._placing_cursor[1] - camy
        pw, ph = self._placing_size()
        w, h = pw * z, ph * z
        cr.save()
        cr.set_source_rgba(0.55, 0.75, 1.0, 0.6)
        cr.set_line_width(2.0)
        cr.set_dash([6.0, 4.0])
        cr.rectangle(x, y, w, h)
        cr.stroke()
        cr.restore()

    def _preview_anchors(self, z):
        """(p0, cursor) do cabo-fantasma no espaço de desenho (tela − câmera), ou None.
        p0 = âncora da origem (ímã de 8 pontos) apontada pro cursor."""
        if not (self._connect_mode and self._connect_src is not None
                and self._connect_cursor is not None):
            return None
        sbox = self._cable_box(self._connect_src[1], z)
        if sbox is None:
            return None
        # o cursor vem em coords de TELA; o espaço do desenho é "tela − câmera" (igual ao
        # _cable_box; o snapshot reaplica o translate da câmera). Sem isto o cabo fica deslocado.
        camx, camy = self._cam
        cur = (self._connect_cursor[0] - camx, self._connect_cursor[1] - camy)
        (p0, _p3) = cable_anchors(sbox, (cur[0], cur[1], 0.0, 0.0))
        return p0, cur

    def _preview_points(self, p0, cur):
        """Pontos do cabo-fantasma segundo o MESMO modo de física dos cabos reais (`_cable_phys`):
        idêntico ao cabo já conectado, só que a outra ponta é o cursor (a corda Verlet é a
        `_preview_rope`, avançada no tick — ver _step_ropes)."""
        if self._cable_phys == "catenary":
            return catenary_pts(p0, cur, sag_ratio=CATENARY_SAG)
        if self._cable_phys == "spring":
            return quad_bezier_pts(p0, spring_target(p0, cur, SPRING_SAG), cur)
        r = self._preview_rope
        return r["pts"] if r is not None else [p0, cur]

    def _draw_connect_preview_cr(self, cr, z) -> None:
        """Cabo-fantasma do modo conectar: desenhado IGUAL ao cabo real (mesma corda/cor/bolinhas),
        com a outra ponta seguindo o cursor, até o 2º clique fechar a conexão."""
        anc = self._preview_anchors(z)
        if anc is None:
            return
        p0, cur = anc
        pts = self._preview_points(p0, cur)
        r, g, b = _cable_rgb(None)  # mesma cor azul do cabo idle
        cr.save()
        cr.set_dash([])
        cr.set_source_rgb(r, g, b)
        cr.set_line_width(2.5)  # mesma largura da corda real
        self._stroke_rope(cr, pts)
        cr.stroke()
        cr.set_line_width(1.5)  # bolinhas nas duas pontas, igual ao cabo conectado
        for px, py in (pts[0], pts[-1]):
            cr.arc(px, py, CABLE_DOT_RADIUS, 0.0, 2.0 * math.pi)
            cr.set_source_rgb(1.0, 1.0, 1.0)
            cr.fill()
            cr.arc(px, py, CABLE_DOT_RADIUS, 0.0, 2.0 * math.pi)
            cr.set_source_rgb(r, g, b)
            cr.stroke()
        cr.restore()

    def _draw_phys_label(self, cr) -> None:
        """Mostra o nome do modo de física do cabo num canto por ~2s ao trocar (flash)."""
        camx, camy = self._cam
        names = {"verlet": "VERLET (balança)", "catenary": "CATENÁRIA (estática)",
                 "spring": "BEZIER+MOLA (esticado)"}
        cr.save()
        cr.set_dash([])
        cr.set_source_rgb(0.96, 0.86, 0.36)
        cr.select_font_face("monospace", 0, 1)
        cr.set_font_size(16)
        cr.move_to(16 - camx, 26 - camy)  # canto sup-esq da viewport (desfaz o translate da câmera)
        cr.show_text(f"cabo: {names.get(self._cable_phys, self._cable_phys)}   (Ctrl+Shift+P)")
        cr.restore()

    @staticmethod
    def _stroke_rope(cr, pts) -> None:
        """Traça a corda como spline suave (Catmull-Rom → cubic bezier por segmento),
        passando por todos os pontos. Path único → o tracejado de fluxo corre por cima."""
        n = len(pts)
        if n < 2:
            return
        cr.move_to(pts[0][0], pts[0][1])
        for i in range(n - 1):
            p_prev = pts[i - 1] if i > 0 else pts[0]
            p1, p2 = pts[i], pts[i + 1]
            p_next = pts[i + 2] if i + 2 < n else pts[-1]
            c1x = p1[0] + (p2[0] - p_prev[0]) / 6.0
            c1y = p1[1] + (p2[1] - p_prev[1]) / 6.0
            c2x = p2[0] - (p_next[0] - p1[0]) / 6.0
            c2y = p2[1] - (p_next[1] - p1[1]) / 6.0
            cr.curve_to(c1x, c1y, c2x, c2y, p2[0], p2[1])

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
        self._edge_flow[(src, dst)] = (src, dst)  # handoff: dado vai src→dst
        self._wake_cables()
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
                        self._edge_flow.pop((src, dst), None)
                else:  # A ou B escalou -> cabo reflete o estado
                    self._edge_state[(src, dst)] = _ST_MAP.get(sp.state, "blocked")
                    self._edge_flow.pop((src, dst), None)
        self._wake_cables()
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
        # evita colisão com TUDO que "reserva" um id: frames na tela, o registro do
        # controller (add_agent_instance recusa 'id já existe') e o roster persistido —
        # senão recruit trava quando sobra um codex-N antigo só no controller (não nos frames).
        taken = set(self.frames)
        if self.controller is not None:
            taken |= set(getattr(self.controller, "agents", {}))
        taken |= {s.get("nid") for s in self.model.node_roster()}
        i = 2
        while f"{prefix}-{i}" in taken:
            i += 1
        return f"{prefix}-{i}"

    def _rect_overlaps_any(self, x: float, y: float, w: float, h: float) -> bool:
        """True se o retângulo (x,y,w,h) se sobrepõe a QUALQUER nó/nota/grupo já existente
        no canvas — usado pra nenhum item novo nascer em cima de um já existente."""
        def _hits(bx: float, by: float, bw: float, bh: float) -> bool:
            return x < bx + bw and x + w > bx and y < by + bh and y + h > by

        for nid, (bx, by) in self._base_pos.items():
            bw, bh = self._item_size("node", nid)
            if _hits(bx, by, bw, bh):
                return True
        for nid, (bx, by) in self._note_base.items():
            bw, bh = self._item_size("note", nid)
            if _hits(bx, by, bw, bh):
                return True
        for gid, (bx, by) in self._group_base.items():
            bw, bh = self._group_size.get(gid, (0.0, 0.0))
            if _hits(bx, by, bw, bh):
                return True
        return False

    def _viewport_rect_base(self) -> tuple[float, float, float, float]:
        """Retângulo (x,y,w,h) da área VISÍVEL agora, em coords-base (mesma fórmula do
        minimap: canto = -cam/z, tamanho = tela/z). Item novo nasce perto disso, não em
        algum canto absoluto do canvas infinito (achado ao vivo: "está aparecendo muito
        longe da vista")."""
        z = self.model.zoom() or 1.0
        camx, camy = self._cam
        vw = self.scrolled.get_width() or 1
        vh = self.scrolled.get_height() or 1
        return (-camx / z, -camy / z, vw / z, vh / z)

    def _next_node_default(self) -> tuple[int, int]:
        """Próxima posição livre pra UM item novo, PERTO DA CÂMERA atual — NUNCA sobrepõe
        o que já existe (nó, nota, grupo). Tenta a cascata clássica primeiro (canto
        superior esquerdo da VIEWPORT, visual variado); só cai pra "abaixo do que está
        visível" (`_free_region_origin`) se a cascata colidir com algo — achado ao vivo:
        a cascata modular (mod 6) repete e cedo ou tarde sobrepõe um item que já está lá."""
        vx, vy, _vw, _vh = self._viewport_rect_base()
        n = len(self.order) + len(self.note_frames)
        cx, cy = vx + 60 + (n % 6) * 80, vy + 60 + (n % 6) * 70
        if not self._rect_overlaps_any(cx, cy, BASE_W, BASE_H):
            return (int(cx), int(cy))
        ox, oy = self._free_region_origin()
        return (int(ox), int(oy))

    def _open_new_terminal_dialog(self):
        dlg, box = self._dialog("➕ novo terminal")
        box.append(Gtk.Label(label="Escolha o tipo, depois clique no canvas pra posicionar."))
        bsh = Gtk.Button(label="🐚 terminal shell (/bin/bash)")
        bsh.connect(
            "clicked", lambda _b: (self._start_placing({"kind": "shell"}), dlg.destroy())
        )
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

            def do_agent(_b):
                self._start_placing({"kind": "agent", "base": combo.get_active_text()})
                dlg.destroy()

            bag.connect("clicked", do_agent)
            box.append(bag)
        dlg.present()

    def _start_placing(self, spec: dict) -> None:
        """Entra no modo "clique pra posicionar": em vez de um algoritmo escolher onde o
        item nasce, o PRÓXIMO CLIQUE no canvas escolhe (prévia fantasma segue o cursor;
        Esc cancela). Achado ao vivo: tentar adivinhar uma posição livre "boa" ficou
        frágil — deixar o humano apontar é mais simples e sempre certo."""
        self._placing_spec = spec
        self._placing_cursor = None
        self.plane.queue_draw()

    def _cancel_placing(self) -> None:
        if self._placing_spec is not None:
            self._placing_spec = None
            self._placing_cursor = None
            self.plane.queue_draw()

    def _commit_placing(self, bx: float, by: float) -> None:
        """Cria o item pendente na posição CLICADA (coords base) — sem algoritmo de
        posicionamento; o humano escolheu."""
        spec = self._placing_spec
        self._placing_spec = None
        self._placing_cursor = None
        if spec is None:
            return
        if spec["kind"] == "shell":
            self._new_shell_terminal(default=(bx, by))
        elif spec["kind"] == "agent":
            self._new_agent_terminal(spec["base"], default=(bx, by))
        elif spec["kind"] == "note":
            self._create_note(default=(bx, by))
        elif spec["kind"] == "group":
            self._create_group(default=(bx, by))
        elif spec["kind"] == "filetree":
            self._create_file_tree(default=(bx, by))
        elif spec["kind"] == "team":
            self._do_materialize_team(spec["spec"], manager=spec.get("manager"), origin=(bx, by))
        self.plane.queue_draw()

    # Regra de arquitetura do canvas (AGENTS.md): TODO elemento criado pela cápsula
    # principal nasce por clique-pra-posicionar — nunca por algoritmo adivinhando uma
    # posição livre. Tamanho da prévia fantasma por tipo de item.
    _PLACING_SIZES = {
        "shell": (BASE_W, BASE_H),
        "agent": (BASE_W, BASE_H),
        "note": (NOTE_W_DEFAULT, NOTE_H_DEFAULT),
        "group": (600.0, 360.0),  # espelha o default de Groups.create
        "filetree": (300.0, 360.0),  # espelha o fallback de _cairo_bounds/_item_size p/ "ft"
    }

    def _placing_size(self) -> tuple[float, float]:
        if not self._placing_spec:
            return (BASE_W, BASE_H)
        kind = self._placing_spec["kind"]
        if kind == "team":
            # tamanho DINÂMICO (depende do template) — não cabe no dict estático de baixo.
            return self._team_layout_size(self._placing_spec["spec"])
        return self._PLACING_SIZES.get(kind, (BASE_W, BASE_H))

    def _new_shell_terminal(self, default: tuple[float, float] | None = None) -> str | None:
        nid = self._unique_nid("shell")
        default = default or self._next_node_default()
        self._add_node(nid, "shell", ["/bin/bash"], default=default)
        # nid é NOVO pra este uso, mas `model.position()/node_size()` preferem um valor
        # persistido antigo se o número foi reciclado (id órfão de um nó fechado antes,
        # possivelmente redimensionado) — força a posição/tamanho calculados de verdade
        # (achado ao vivo: "novo terminal" nascendo em local antigo, sobrepondo o que
        # já existe agora).
        self._force_node_rect(nid, float(default[0]), float(default[1]),
                               float(BASE_W), float(BASE_H))
        self.model.add_to_roster(nid, "shell", None)  # persiste -> volta ao reabrir
        self._resize_plane()
        self.plane.queue_draw()
        return nid

    def _new_agent_terminal(self, base: str | None, default=None) -> str | None:
        self._last_recruit_error = ""  # motivo da última falha (p/ a mensagem do recruit)
        if not base or self.controller is None or not self._ask_bus_dir:
            self._last_recruit_error = "orquestrador/cabos indisponíveis"
            return None
        profiles = installed_agents()
        if base not in profiles:
            self._last_recruit_error = f"CLI '{base}' não instalado"
            return None
        nid = self._unique_nid(base)
        try:
            self.controller.add_agent_instance(nid, base)  # delegate/maestro-ask resolve nid
        except Exception as exc:
            _log.error("add_agent_instance falhou: %s", exc)
            self._last_recruit_error = str(exc)
            return None
        base_home = Path(self._ask_bus_dir).parent
        wsp = Workspace(str(base_home / "workspaces")).create(nid)
        install_ask_skill(wsp, nid)  # ensina o maestro-ask ao novo agente
        # (role recém-criado é vazio; a injeção do role acontece em _add_node → _apply_node_role)
        argv = agent_argv(profiles[base], str(wsp), node=nid, ask_bus_dir=self._ask_bus_dir,
                          auto_approve=self._node_auto_approve(nid))
        pos = default or self._next_node_default()
        self._add_node(nid, nid, argv, default=pos)
        # nid pode coincidir com um id reciclado/órfão (nó fechado antes, possivelmente
        # redimensionado) — `model.position()/node_size()` preferem esse valor velho ao
        # `default` calculado. Força a posição/tamanho de verdade (achado ao vivo: terminal
        # "novo" nascendo em local antigo, sobrepondo o que já existe agora). Quem chama com
        # um tamanho próprio (ex.: `_materialize_team`) refaz o force depois com o valor certo.
        self._force_node_rect(nid, float(pos[0]), float(pos[1]), float(BASE_W), float(BASE_H))
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

    def _create_file_tree(self, default: tuple[float, float] | None = None):
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
        default = default or self._next_node_default()
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

    def _create_note(self, default: tuple[float, float] | None = None):
        if self.notes is None:
            return
        if default is not None:
            x, y = default
        else:
            n = len(self.note_frames)
            x, y = 120 + n * 40, 320 + n * 40
        note = self.notes.create("Nota", "", x=x, y=y)
        self._add_note_widget(note)

    def _add_note_widget(self, note):
        frame = Gtk.Frame()
        frame._note_id = note.id
        frame.add_css_class("node-card")  # UI-1
        # seleciona ao clicar em QUALQUER área da nota (fase CAPTURE = antes do TextView consumir;
        # não claima, então editar/arrastar seguem) — espelha o card de nó (v0.26.1)
        selclick = Gtk.GestureClick()
        selclick.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        selclick.connect("pressed", self._on_frame_press, "note", note.id)
        frame.add_controller(selclick)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # cabeçalho = só uma FAIXA FINA (tom levemente + claro) p/ MOVER a nota (sem título,
        # sem fechar; cor/apagar ficam na pílula de contexto — estilo Maestri).
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        head.add_css_class("notehead")
        head.add_css_class("notehead-min")
        head.set_size_request(-1, 12)
        head.set_tooltip_text("arraste p/ mover a nota")
        head._drag_note = note.id  # arrasto via gesto do PLANO (estável) — ver _pan_*
        frame._note_head = head
        frame._title_entry = None  # sem título no cabeçalho (Maestri)
        # corpo (markdown editável) — na MESMA cor pastel (sticky-note inteira)
        body = Gtk.TextView()
        body.set_wrap_mode(Gtk.WrapMode.WORD)
        body.set_right_margin(14)  # respiro p/ o texto não passar por baixo da barra de scroll
        body.get_buffer().set_text(note.body)
        frame._body_view = body
        body.add_css_class(self._note_font_class(note.id))  # fonte por nota (CSS dedicado)
        if getattr(note, "font", ""):  # fonte salva: registra e aplica
            self._note_fonts[note.id] = note.font
            self._rebuild_note_fonts()
        # placeholder "Clique para editar..." (some quando há texto) — overlay clicável-através
        ph = Gtk.Label(label="Clique para editar...")
        ph.add_css_class("note-ph")
        ph.set_halign(Gtk.Align.START)
        ph.set_valign(Gtk.Align.START)
        ph.set_can_target(False)  # cliques passam p/ o TextView
        frame._note_ph = ph
        # rola em vez de crescer: corpo dentro de um ScrolledWindow de altura fixa, com
        # barra de rolagem minimalista (à direita, pontas arredondadas) — ver CSS .note-scroll
        scroller = Gtk.ScrolledWindow()
        scroller.add_css_class("note-scroll")
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        nw = max(MIN_NOTE_W, getattr(note, "width", NOTE_W_DEFAULT) or NOTE_W_DEFAULT)
        nh = max(MIN_NOTE_H, getattr(note, "height", NOTE_H_DEFAULT) or NOTE_H_DEFAULT)
        scroller.set_size_request(int(nw), int(nh))  # tamanho salvo (resize persistido)
        # corpo = Stack: "edit" (TextView) ↔ "view" (Label com markdown renderizado) — botão M
        view_lbl = Gtk.Label()
        view_lbl.set_use_markup(True)
        view_lbl.set_wrap(True)
        view_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        view_lbl.set_xalign(0.0)
        view_lbl.set_yalign(0.0)
        view_lbl.set_selectable(True)
        view_lbl.set_margin_end(14)  # mesmo respiro do TextView p/ a barra de scroll
        view_lbl.add_css_class(self._note_font_class(note.id))  # mesma fonte da nota
        frame._body_label = view_lbl
        stack = Gtk.Stack()
        stack.add_named(body, "edit")
        stack.add_named(view_lbl, "view")
        stack.set_visible_child_name("edit")
        frame._body_stack = stack
        scroller.set_child(stack)
        frame._body_scroll = scroller
        overlay = Gtk.Overlay()
        overlay.set_child(scroller)
        overlay.add_overlay(ph)
        buf = body.get_buffer()
        ph.set_visible(buf.get_char_count() == 0)
        buf.connect("changed", lambda b, lbl=ph: lbl.set_visible(b.get_char_count() == 0))
        # estilo AO VIVO no modo editar: negrito/itálico/título já aparecem (marcadores visíveis),
        # então clicar B mostra o negrito na hora. Ao SAIR, o Label some os marcadores.
        self._note_md_tags(buf)
        buf.connect("changed", lambda b: self._restyle_note(b))
        self._restyle_note(buf)
        # auto-scroll: o corpo acompanha o cursor ao digitar (não some no fim do bloco). Como o
        # ScrolledWindow rola o STACK (não o TextView), rolamos manualmente pelo vadjustment.
        buf.connect("changed", lambda b, fr=frame: GLib.idle_add(self._note_autoscroll, fr))
        # também rola ao MOVER o cursor (setas) — senão a seta sai da vista sem o scroll seguir
        buf.connect(
            "notify::cursor-position",
            lambda b, _p, fr=frame: GLib.idle_add(self._note_autoscroll, fr),
        )
        # Enter numa linha de checkbox/lista continua o próximo item (CAPTURE = antes do TextView)
        keyctl = Gtk.EventControllerKey()
        keyctl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keyctl.connect("key-pressed", self._note_body_key, frame)
        body.add_controller(keyctl)
        self._apply_note_color(frame, note.color)  # frame + faixa + corpo + placeholder
        # já abre com formatação ATIVA (modo "ver") se a nota tem conteúdo; vazia abre p/ editar
        self._set_note_view(frame, bool(note.body.strip()))
        # ao SAIR do texto (clicar fora): salva e FORMATA (volta pro modo "ver")
        fc = Gtk.EventControllerFocus()
        fc.connect("leave", lambda _c, fr=frame: self._note_blur(fr))
        body.add_controller(fc)
        box.append(head)
        box.append(overlay)
        # (removido POR ENQUANTO: linha "rodar agente com a nota" — seletor + ▶ rodar; o método
        # _run_note continua existindo p/ re-religar depois)
        # resize é detectado no nível do CANVAS (faixa em volta da borda) — sem widgets aqui
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
        note.body = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        # sem campo de título no cabeçalho: usa a 1ª linha do corpo (p/ minimapa/run)
        stripped = note.body.strip()
        note.title = stripped.splitlines()[0].strip()[:60] if stripped else ""
        note.x, note.y = self._note_base.get(frame._note_id, (0.0, 0.0))  # coords-base
        # cor/pin já persistem nos seus handlers; preserva-os (get traz do store)
        self.notes.save(note)
        self._materialize_note_everywhere(frame._note_id)  # 4b: atualiza o arquivo nos nós ligados
        return False

    # -- C4 v2: cor da nota por HEX (frame pastel + faixa clara + corpo + placeholder) --
    @staticmethod
    def _nid_key(note_id: str) -> str:
        return note_id.replace("-", "")  # sufixo de classe CSS válido

    def _rebuild_note_colors(self) -> None:
        """Regenera o CSS por-nota a partir de self._note_colors (hex)."""
        rules = []
        for nid, hexc in self._note_colors.items():
            if not hexc:
                continue
            key = self._nid_key(nid)
            r, g, b = _hex_to_rgb(hexc)
            txt = _contrast_text(hexc)  # texto legível: preto p/ claro, branco p/ escuro
            tgt = 0 if txt == "#1e1e2e" else 255  # combina com a cor: card claro→faixa + escura
            head_c = _mix(hexc, tgt, 0.16)  # faixa de mover: tom que contrasta de leve e combina
            ph_c = _mix(hexc, tgt, 0.45)  # placeholder: muted na direção do contraste
            rules += [
                f".note-c-{key} {{ background-color: rgba({r},{g},{b},0.95); }}",  # frame
                f".note-h-{key} {{ background-color: {head_c}; }}",  # faixa superior
                # cor no NÓ textview (cascateia p/ o subnó text por herança) + no subnó (robusto)
                f".note-b-{key} {{ background-color: {hexc}; color: {txt}; }}",  # corpo
                f".note-b-{key} text {{ background-color: {hexc}; color: {txt}; }}",
                f".note-p-{key} {{ color: {ph_c}; }}",  # placeholder
            ]
        self._css_load(self._color_provider, "\n".join(rules))

    def _apply_note_color(self, frame, color: str) -> None:
        nid = frame._note_id
        key = self._nid_key(nid)
        self._note_colors[nid] = note_hex(color)
        self._rebuild_note_colors()
        frame.add_css_class(f"note-c-{key}")  # classes estáveis por nota (idempotente)
        for attr, prefix in (("_note_head", "note-h-"), ("_body_view", "note-b-"),
                             ("_body_label", "note-b-"), ("_note_ph", "note-p-")):
            w = getattr(frame, attr, None)
            if w is not None:
                w.add_css_class(f"{prefix}{key}")
        self._update_ctx_color_swatch()

    def _set_note_color(self, frame, color: str) -> None:
        if self.notes is None:
            return
        note = self.notes.get(frame._note_id)
        if note is None:
            return
        note.color = note_hex(color)  # guarda HEX (paleta ou custom)
        self.notes.save(note)
        self._apply_note_color(frame, note.color)
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
        self._remove_edges_for(note_id)  # tira cabos órfãos do store (+ hook 4b)
        if self._connect_src is not None and self._connect_src[1] == note_id:
            self._cancel_connect()
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

    def _ctx_pick_custom_color(self) -> None:
        """"Mais cores": abre o seletor nativo (Gtk.ColorDialog) p/ cor custom."""
        frame = self._ctx_note_frame()
        if frame is None:
            return
        dialog = Gtk.ColorDialog()
        init = Gdk.RGBA()
        init.parse(self._note_colors.get(frame._note_id, NOTE_HEX_DEFAULT))

        def done(dlg, res):
            try:
                rgba = dlg.choose_rgba_finish(res)
            except GLib.Error:
                return  # cancelado
            if rgba is not None:
                hexc = "#%02x%02x%02x" % (
                    round(rgba.red * 255), round(rgba.green * 255), round(rgba.blue * 255)
                )
                self._set_note_color(frame, hexc)

        dialog.choose_rgba(self.win, init, None, done)

    @staticmethod
    def _note_md_tags(buf) -> None:
        """Cria (1x) as TextTags de estilo markdown ao vivo no buffer da nota."""
        if buf.get_tag_table().lookup("bold") is not None:
            return
        buf.create_tag("bold", weight=Pango.Weight.BOLD)
        buf.create_tag("italic", style=Pango.Style.ITALIC)
        buf.create_tag("strike", strikethrough=True)
        buf.create_tag("code", family="monospace")
        buf.create_tag("h1", weight=Pango.Weight.BOLD, scale=1.6)
        buf.create_tag("h2", weight=Pango.Weight.BOLD, scale=1.35)
        buf.create_tag("h3", weight=Pango.Weight.BOLD, scale=1.15)

    def _restyle_note(self, buf) -> None:
        """Aplica o estilo markdown AO VIVO (marcadores visíveis): limpa e re-aplica `md_spans`."""
        start, end = buf.get_bounds()
        for name in ("bold", "italic", "strike", "code", "h1", "h2", "h3"):
            buf.remove_tag_by_name(name, start, end)
        text = buf.get_text(start, end, False)
        for s, e, style in md_spans(text):
            buf.apply_tag_by_name(style, buf.get_iter_at_offset(s), buf.get_iter_at_offset(e))

    def _note_wrap(self, left: str, right: str) -> None:
        """Alterna a seleção (ou cursor) do corpo da nota com marcadores markdown (B = toggle)."""
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
        new, cs, ce = md_wrap_toggle(text, s, e, left, right)  # adiciona OU remove
        buf.set_text(new)  # dispara "changed" → _restyle_note (negrito aparece na hora)
        buf.select_range(buf.get_iter_at_offset(cs), buf.get_iter_at_offset(ce))
        self._set_note_view(frame, False)  # o botão renderizou; volta p/ EDITAR estilizado
        frame._body_view.grab_focus()
        self._note_editing = frame._note_id
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
        self._set_note_view(frame, False)  # volta p/ EDITAR estilizado (o botão tinha renderizado)
        frame._body_view.grab_focus()
        self._note_editing = frame._note_id
        self._save_note(frame)

    def _note_edit_inplace(self, note_id: str) -> None:
        """Clicar a nota: entra no modo EDITAR (texto cru) e foca o cursor — edição in-place."""
        if self._note_editing is not None and self._note_editing != note_id:
            self._note_render(self._note_editing)  # formata a nota anterior
        frame = self.note_frames.get(note_id)
        if frame is None:
            return
        self._set_note_view(frame, False)  # mostra o TextView (markdown cru)
        frame._body_view.grab_focus()
        self._note_editing = note_id

    def _note_render(self, note_id: str) -> None:
        """Formata a nota `note_id`: salva e volta pro modo ver (markdown renderizado)."""
        frame = self.note_frames.get(note_id)
        if frame is None:
            self._note_editing = None
            return
        self._save_note(frame)
        if frame._body_view.get_buffer().get_char_count() > 0:
            self._set_note_view(frame, True)  # renderiza; vazia continua em editar
        if self._note_editing == note_id:
            self._note_editing = None

    def _note_blur(self, frame) -> None:
        """Saiu do texto (perdeu foco p/ outro widget): formata."""
        self._note_render(frame._note_id)

    def _note_autoscroll(self, frame) -> bool:
        """Rola o ScrolledWindow da nota p/ manter a linha do cursor visível (o TextView fica
        dentro de um Stack, então scroll_mark_onscreen não basta — mexemos no vadjustment)."""
        tv = getattr(frame, "_body_view", None)
        sc = getattr(frame, "_body_scroll", None)
        if tv is None or sc is None:
            return False
        buf = tv.get_buffer()
        rect = tv.get_iter_location(buf.get_iter_at_mark(buf.get_insert()))  # coords-buffer
        vadj = sc.get_vadjustment()
        margin = 10.0  # respiro embaixo do cursor
        top = rect.y + tv.get_top_margin()
        bottom = top + rect.height
        if bottom + margin > vadj.get_value() + vadj.get_page_size():
            vadj.set_value(bottom + margin - vadj.get_page_size())  # deixa 10px abaixo do cursor
        elif top < vadj.get_value():
            vadj.set_value(top)
        return False  # one-shot (idle)

    def _note_body_key(self, _ctrl, keyval, _kc, state, frame) -> bool:
        """Enter numa linha de checkbox/lista cria o próximo item (ou sai, se vazio)."""
        if keyval not in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            return False
        if state & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK):
            return False  # Shift/Ctrl+Enter = quebra normal
        buf = frame._body_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        cur = buf.get_iter_at_mark(buf.get_insert()).get_offset()
        res = md_enter_continuation(text, cur)
        if res is None:
            return False  # linha não é lista → Enter normal
        new, ncur = res
        buf.set_text(new)  # dispara "changed" → re-estiliza + auto-scroll
        buf.place_cursor(buf.get_iter_at_offset(ncur))
        return True  # consumido (não insere a quebra padrão)

    def _set_note_view(self, frame, view: bool) -> None:
        """Põe a nota em VER (markdown formatado) ou EDITAR (TextView)."""
        stack = getattr(frame, "_body_stack", None) if frame is not None else None
        if stack is None:
            return
        ph = getattr(frame, "_note_ph", None)
        buf = frame._body_view.get_buffer()
        if view:  # renderiza o buffer atual no Label
            text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
            frame._body_label.set_markup(md_to_pango(text))
            if ph is not None:
                ph.set_visible(False)  # placeholder só faz sentido editando
            stack.set_visible_child_name("view")
        else:
            stack.set_visible_child_name("edit")
            if ph is not None:
                ph.set_visible(buf.get_char_count() == 0)
        self._update_md_btn()

    def _update_md_btn(self) -> None:
        """Realça o botão M (borda quadrada) quando a nota selecionada está em modo "ver"."""
        btn = getattr(self, "_ctx_md_btn", None)
        if btn is None:
            return
        frame = self._ctx_note_frame()
        stack = getattr(frame, "_body_stack", None) if frame is not None else None
        on = stack is not None and stack.get_visible_child_name() == "view"
        (btn.add_css_class if on else btn.remove_css_class)("note-md-on")

    def _note_toggle_render(self) -> None:
        """Alterna a nota entre EDITAR (TextView) e VER (markdown formatado no Label)."""
        frame = self._ctx_note_frame()
        stack = getattr(frame, "_body_stack", None) if frame is not None else None
        if stack is None:
            return
        self._set_note_view(frame, stack.get_visible_child_name() != "view")

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
        dup.font = src.font
        dup.width, dup.height = src.width, src.height
        self.notes.save(dup)
        self._add_note_widget(dup)

    def _note_delete(self) -> None:
        frame = self._ctx_note_frame()
        if frame is not None:
            self._close_note(frame)
            self._select(None)  # limpa seleção -> esconde a pílula de contexto

    # -- fonte por nota (seletor completo: Gtk.FontDialog) --
    @staticmethod
    def _note_font_class(note_id: str) -> str:
        return "nf-" + note_id.replace("-", "")  # classe CSS válida (não começa com dígito)

    def _rebuild_note_fonts(self) -> None:
        """Regenera o CSS do provider de fontes a partir de self._note_fonts."""
        styles = {Pango.Style.NORMAL: "normal", Pango.Style.OBLIQUE: "oblique",
                  Pango.Style.ITALIC: "italic"}
        rules = []
        for nid, desc_str in self._note_fonts.items():
            if not desc_str:
                continue
            d = Pango.FontDescription.from_string(desc_str)
            fam = d.get_family() or "sans-serif"
            size = d.get_size() / Pango.SCALE
            size_css = f"{size:g}px" if d.get_size_is_absolute() else f"{size:g}pt"
            weight = int(d.get_weight())
            style = styles.get(d.get_style(), "normal")
            rules.append(
                f'.{self._note_font_class(nid)} {{ font-family: "{fam}"; font-size: {size_css};'
                f" font-weight: {weight}; font-style: {style}; }}"
            )
        self._css_load(self._font_provider, "\n".join(rules))

    def _apply_note_font(self, frame, desc_str: str) -> None:
        nid = frame._note_id
        self._note_fonts[nid] = desc_str
        self._rebuild_note_fonts()
        body = getattr(frame, "_body_view", None)
        if body is not None:
            body.add_css_class(self._note_font_class(nid))
        if self.notes is not None:
            note = self.notes.get(nid)
            if note is not None:
                note.font = desc_str
                self.notes.save(note)

    def _ctx_pick_font(self) -> None:
        """Abre o seletor nativo de fonte e aplica à nota selecionada."""
        frame = self._ctx_note_frame()
        if frame is None:
            return
        dialog = Gtk.FontDialog()
        init = self._note_fonts.get(frame._note_id)
        init_desc = Pango.FontDescription.from_string(init) if init else None

        def done(dlg, res):
            try:
                desc = dlg.choose_font_finish(res)
            except GLib.Error:
                return  # cancelado/erro: mantém a fonte atual
            if desc is not None:
                self._apply_note_font(frame, desc.to_string())

        dialog.choose_font(self.win, init_desc, None, done)

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

    def _create_group(self, default: tuple[float, float] | None = None) -> None:
        if self.groups is None:
            return
        x, y = default if default is not None else self._next_node_default()
        g = self.groups.create(x=float(x), y=float(y))
        self._load_group(g)
        self._resize_plane()
        self.plane.queue_draw()
        self._mm_refresh()

    # -- Orquestração de equipe (Fase A, docs/14): materializa um TeamTemplate inteiro --
    MAESTRO_TEAM_GROUP_HARD_CAP = 8  # anti "agentes demais" por grupo (§8, mesmo teto do HITL)
    MAESTRO_TEAM_GROUP_WARN = 5  # acima disso, avisar (não bloquear) — recomendado é 3-4
    # tamanho do card no grid da equipe — maior que o BASE_W×BASE_H genérico (420×220):
    # nesse tamanho dava pra ver o card, mas não pra ler o conteúdo do terminal (achado ao
    # vivo). Calibrado no tamanho que o usuário validou (terminal nº8 da sessão de teste).
    MAESTRO_TEAM_CARD_W = 500.0
    MAESTRO_TEAM_CARD_H = 520.0

    @staticmethod
    def _team_templates_path() -> Path:
        return default_team_templates_path()

    def _team_templates(self) -> list[TeamTemplate]:
        """Built-ins + salvos (salvo de mesmo nome sobrepõe o built-in) — sempre os dois
        juntos na lista, nunca só um OU outro (diferente do fallback-semente do roles.py)."""
        by_name = dict(BUILTIN_TEAM_TEMPLATES)
        for t in load_team_templates(self._team_templates_path()):
            by_name[t.name] = t
        return list(by_name.values())

    def _save_team_templates(self, templates: list[TeamTemplate]) -> None:
        # só persiste os CUSTOM (built-in não precisa virar arquivo do usuário)
        custom = [t for t in templates if t.name not in BUILTIN_TEAM_TEMPLATES]
        save_team_templates(self._team_templates_path(), custom)

    def _save_team_from_staging(
        self, staging: dict, original_name: str | None
    ) -> tuple[bool, str]:
        """Constrói um `TeamTemplate` a partir do rascunho editável (mesmo shape de
        `to_dict()`), valida e persiste (Fase C, docs/14 §11). `original_name` = nome
        anterior do template (edição, inclusive com rename) ou `None` (novo/duplicado).
        Devolve (ok, mensagem-de-erro) — nunca levanta, pra UI mostrar inline."""
        try:
            tpl = TeamTemplate.from_dict(staging)
            validate_team_template(tpl)
        except (KeyError, TypeError, ValueError) as exc:  # TeamTemplateValidationError < ValueError
            return False, str(exc)
        skip = {n for n in (original_name, tpl.name) if n}
        updated = [t for t in self._team_templates() if t.name not in skip]
        updated.append(tpl)
        self._save_team_templates(updated)
        return True, ""

    def _free_region_origin(self) -> tuple[float, float]:
        """Origem livre pra nascer uma leva de itens SEM sobrepor nada — abaixo do que está
        VISÍVEL agora (não "abaixo de tudo que existe no canvas inteiro": um canvas com
        conteúdo espalhado longe faria o item novo nascer longe da câmera — achado ao vivo,
        "está aparecendo muito longe da vista"). Só conta itens que se sobrepõem à viewport
        atual; canvas vazio (ou nada visível) começa no topo-esquerdo da própria viewport.
        Usada por `_materialize_team` (leva inteira) e como FALLBACK de `_next_node_default`/
        `_place_below` quando a posição preferida (cascata/pilha) colidiria com algo."""
        vx, vy, vw, vh = self._viewport_rect_base()

        def _in_view(bx: float, by: float, bw: float, bh: float) -> bool:
            return bx < vx + vw and bx + bw > vx and by < vy + vh and by + bh > vy

        xs: list[float] = [vx]
        bottoms: list[float] = [vy]
        for nid, (x, y) in self._base_pos.items():
            w, h = self._item_size("node", nid)
            if _in_view(x, y, w, h):
                xs.append(x)
                bottoms.append(y + h)
        for nid, (x, y) in self._note_base.items():
            w, h = self._item_size("note", nid)
            if _in_view(x, y, w, h):
                xs.append(x)
                bottoms.append(y + h)
        for gid, (x, y) in self._group_base.items():
            w, h = self._group_size.get(gid, (0.0, 0.0))
            if _in_view(x, y, w, h):
                xs.append(x)
                bottoms.append(y + h)
        return (min(xs), max(bottoms) + GROUP_PAD * 2)

    def _force_node_rect(self, nid: str, x: float, y: float, w: float, h: float) -> None:
        """Aplica a posição+tamanho CALCULADOS no nó recém-criado, sobrescrevendo qualquer
        posição/tamanho persistido antigo. `model.position()`/`node_size()` preferem o que já
        está salvo pro id — um id reciclado/órfão (ex.: um nó fechado antes, redimensionado
        manualmente, cujo id voltou a ser usado) faria o card "nascer" longe do grid E/OU MUITO
        maior que o nominal, estourando o grupo e sobrepondo os vizinhos (achado ao vivo:
        `nodesize_*` órfão bem maior que `BASE_W×BASE_H`). Reusa a mecânica REAL do resize
        manual (`_item_resize_apply`/`_item_resize_persist`) em vez de duplicar a lógica."""
        self._item_resize_apply("node", nid, x, y, w, h)
        self._item_resize_persist("node", nid, x, y, w, h)

    def _team_group_footprint(self, group: GroupSpec) -> tuple[float, float, int, int]:
        """(gw, gh, cols, rows) que o retângulo do grupo vai ocupar pra materializar `group` —
        mesmo grid usado por `_materialize_team` e pela prévia fantasma de "Montar equipe"
        (clique-pra-posicionar, AGENTS.md § Cápsulas de UI, item 5)."""
        card_w, card_h = self.MAESTRO_TEAM_CARD_W, self.MAESTRO_TEAM_CARD_H
        cols = min(3, max(1, len(group.members)))
        rows = -(-len(group.members) // cols)  # ceil sem importar math
        gw = max(GROUP_MIN_W, GROUP_PAD * 2 + cols * card_w + (cols - 1) * GROUP_PAD)
        gh_content = (
            GROUP_PAD + GROUP_TITLE_H + rows * card_h
            + (rows - 1) * GROUP_PAD + GROUP_PAD_BOTTOM
        )
        gh = max(GROUP_MIN_H, gh_content)
        return (gw, gh, cols, rows)

    def _team_layout_size(self, spec: TeamTemplate) -> tuple[float, float]:
        """Tamanho TOTAL (w,h) do bloco que `_materialize_team` vai ocupar pra este spec —
        usado pra dimensionar a prévia fantasma do modo "clique pra posicionar"."""
        gap = GROUP_PAD * 2
        total_w = 0.0
        max_h = 0.0
        for group in spec.groups:
            gw, gh, _cols, _rows = self._team_group_footprint(group)
            total_w += gw + gap
            max_h = max(max_h, gh)
        if total_w > 0:
            total_w -= gap  # sem gap sobrando depois do último grupo
        return (total_w, max_h)

    def _materialize_team(self, spec: TeamTemplate, *, manager: str | None = None,
                           origin: tuple[float, float] | None = None) -> dict:
        """Cria os Grupos do canvas + recruta os membros DENTRO de cada grupo, com papéis e
        cabos (docs/14 §5.A2). Ação do HUMANO via FAB (ou já confirmada pelo humano na Fase B)
        -> NÃO passa pelo rate-limit de agente. `origin`, se dado, é a posição CLICADA pelo
        humano (clique-pra-posicionar); sem `origin`, cai no cálculo automático de área livre
        (usado pela Fase B, que não tem um clique humano de posicionamento). Devolve um
        resultado compacto (nunca levanta)."""
        empty = {"ok": False, "groups": 0, "agents": 0, "warnings": []}
        if self.groups is None or self.controller is None or not self._ask_bus_dir:
            return {**empty, "error": "orquestrador/grupos indisponíveis"}
        try:
            validate_team_template(spec)
        except TeamTemplateValidationError as exc:
            return {**empty, "error": str(exc)}
        need = spec.total_members
        room = self.MAESTRO_FLEET_CAP - self._fleet_count()
        if need > room:
            self._audit("team_materialize_blocked", template=spec.name, reason="fleet_cap",
                        need=need, room=room)
            return {**empty, "error": f"time precisa de {need} agentes, só cabem {room} "
                                       f"(teto global {self.MAESTRO_FLEET_CAP})"}
        hard_cap = self.MAESTRO_TEAM_GROUP_HARD_CAP
        oversized = [g.name for g in spec.groups if len(g.members) > hard_cap]
        if oversized:
            self._audit("team_materialize_blocked", template=spec.name, reason="group_too_big",
                        groups=oversized)
            return {**empty, "error": f"grupo(s) {', '.join(oversized)} passam de "
                                       f"{hard_cap} agentes (máx. por grupo)"}
        warnings = [
            f"grupo {g.name!r} tem {len(g.members)} agentes (recomendado: 3-4)"
            for g in spec.groups
            if len(g.members) > self.MAESTRO_TEAM_GROUP_WARN
        ]

        if origin is not None:
            gx, gy = float(origin[0]), float(origin[1])
        else:
            ox, oy = self._free_region_origin()
            gx, gy = float(ox), float(oy)
        gap = GROUP_PAD * 2
        groups_created = agents_created = 0
        card_w, card_h = self.MAESTRO_TEAM_CARD_W, self.MAESTRO_TEAM_CARD_H
        for group in spec.groups:
            gw, gh, cols, _rows = self._team_group_footprint(group)
            g = self.groups.create(title=group.name, color=group.color or "blue",
                                    x=gx, y=gy, w=float(gw), h=float(gh))
            self._load_group(g)
            groups_created += 1
            member_nids: dict[str, str] = {}  # nome do papel -> nid, DENTRO deste grupo
            for i, member in enumerate(group.members):
                col, row = i % cols, i // cols
                px = gx + GROUP_PAD + col * (card_w + GROUP_PAD)
                py = gy + GROUP_PAD + GROUP_TITLE_H + row * (card_h + GROUP_PAD)
                nid = self._new_agent_terminal(member.agent, default=(px, py))
                if nid is None:
                    self._audit("team_materialize_partial", template=spec.name, group=group.name,
                                member=member.name, reason=getattr(self, "_last_recruit_error", ""))
                    continue
                agents_created += 1
                # nunca herda posição/tamanho persistido antigo (id reciclado/órfão)
                self._force_node_rect(nid, px, py, card_w, card_h)
                self.model.set_node_cfg(nid, "role", member.name)  # nome p/ display/badge/HUD
                self._apply_role_spec(nid, member)  # instrução REAL do template (não a lib)
                member_nids[member.name] = nid
                self._respawn_node(nid)
            # Fiação de cabos (Fase D, docs/14 §12): grupo COM líder vira caixa-preta — o
            # líder é o único ponto de conexão pra fora (orquestrador/T1 ↔ líder ↔ os demais
            # membros do grupo). Grupo SEM líder: comportamento anterior inalterado (todos
            # conectam direto no orquestrador/T1) — retrocompatível.
            #
            # `_recruited_by` é AUTORIDADE (ADR-17/18: dismiss/reassign/wire via `_own_recruit`),
            # NÃO fiação visual — `edges` é só exibição/UI (`_maestro_connected`). O líder recebe
            # o cabo dos colegas (fiação), mas a autoridade sobre eles continua com quem já a
            # tinha antes da Fase D (o `manager`, se houver; ninguém, se for materialização
            # top-level via FAB). Sem isso, `_own_recruit(líder, colega)` viraria True e o líder
            # ganharia dismiss/reassign sobre o grupo de graça — poder de comando que a Fase D
            # nunca pretendeu dar (achado por revisão adversarial pós-merge, 2026-07-02).
            leader_nid = member_nids.get(group.leader) if group.leader else None
            if leader_nid is not None:
                if manager:
                    self._recruited_by[leader_nid] = manager
                    self.edges.add(manager, leader_nid)
                for nid in member_nids.values():
                    if nid == leader_nid:
                        continue
                    if manager:
                        self._recruited_by[nid] = manager  # autoridade: manager, nunca o líder
                    self.edges.add(leader_nid, nid)  # fiação: conecta no líder (só visual)
            elif manager:
                for nid in member_nids.values():
                    self._recruited_by[nid] = manager
                    self.edges.add(manager, nid)
            self._autofit_group(g.id)
            self._persist_group(g.id)  # WYSIWYG: reabre igual fechou
            gx += gw + gap
        self._resize_plane()
        self.plane.queue_draw()
        self._refresh_fleet_hud()
        self._mm_refresh()
        self._audit("team_materialize", template=spec.name, groups=groups_created,
                    agents=agents_created, manager=manager or "")
        return {"ok": True, "groups": groups_created, "agents": agents_created,
                "warnings": warnings, "error": None}

    def _team_result_dialog(self, message: str) -> None:
        dlg, box = self._dialog("🧩 Montar equipe")
        lbl = Gtk.Label(label=message, xalign=0)
        lbl.set_wrap(True)
        box.append(lbl)
        ok = Gtk.Button(label="OK")
        ok.connect("clicked", lambda _b: dlg.destroy())
        box.append(ok)
        dlg.present()

    def _do_materialize_team(self, spec: TeamTemplate, *, manager: str | None = None,
                              origin: tuple[float, float] | None = None) -> None:
        result = self._materialize_team(spec, manager=manager, origin=origin)
        if not result["ok"]:
            self._team_result_dialog(f"Não deu pra montar: {result['error']}")
            return
        msg = (f"Equipe '{spec.name}' montada: {result['groups']} grupo(s), "
               f"{result['agents']} agente(s).")
        if manager:
            msg += f"\nConectada ao orquestrador '{manager}'."
        if result["warnings"]:
            msg += "\n⚠ " + "; ".join(result["warnings"])
        self._team_result_dialog(msg)

    def _agent_node_choices(self) -> list[tuple[str, str]]:
        """(nid, nome de exibição) dos nós-AGENTE vivos no canvas — candidatos a orquestrador
        pra ligar a equipe recém-montada (opção "criar equipe com orquestrador")."""
        kind_by_nid = {s.get("nid"): s.get("kind") for s in self.model.node_roster()}
        return [
            (nid, self.model.node_name(nid, nid))
            for nid in self.order
            if nid in self.frames and kind_by_nid.get(nid) == "agent"
        ]

    def _confirm_materialize_team(self, parent_win, tpl: TeamTemplate) -> None:
        """Pede valores de placeholder (se houver) + deixa escolher um orquestrador
        (agente já no canvas) pra ligar a equipe — ou nível principal (nenhum), o default."""
        win, box = self._dialog(f"Montar — {tpl.name}")
        names = placeholder_names(tpl)
        entries = {}
        for n in names:
            box.append(Gtk.Label(label=f"{{{n}}}", xalign=0))
            entry = Gtk.Entry()
            entries[n] = entry
            box.append(entry)
        box.append(Gtk.Label(label="Conectar ao orquestrador (opcional)", xalign=0))
        mgr_combo = Gtk.ComboBoxText()
        mgr_combo.append_text("(nenhum — nível principal)")
        choices = self._agent_node_choices()
        for nid, label in choices:
            mgr_combo.append_text(f"{label} ({nid})")
        mgr_combo.set_active(0)
        box.append(mgr_combo)
        foot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        foot.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda _b: win.destroy())
        montar = Gtk.Button(label="Montar")
        montar.add_css_class("suggested-action")

        def do_montar(_b):
            values = {n: e.get_text().strip() for n, e in entries.items()}
            rendered = render_team_template(tpl, **values) if names else tpl
            idx = mgr_combo.get_active()
            manager = choices[idx - 1][0] if idx > 0 else None
            win.destroy()
            parent_win.destroy()
            # clique-pra-posicionar (AGENTS.md § Cápsulas de UI, item 5): humano escolhe
            # onde o BLOCO inteiro da equipe nasce, em vez de um algoritmo decidir.
            self._start_placing({"kind": "team", "spec": rendered, "manager": manager})

        montar.connect("clicked", do_montar)
        foot.append(cancel)
        foot.append(montar)
        box.append(foot)
        win.present()

    def _team_group_edit_dialog(self, group_state: dict, on_group_saved) -> None:
        """Editor de UM grupo (nome/cor/líder/membros) — Fase C, docs/14 §11. Chamado de
        dentro de `_team_edit_dialog`; ao Salvar, devolve o grupo atualizado via callback
        (não toca o disco — só o template inteiro persiste, no Salvar de fora)."""
        NO_LEADER = "(nenhum)"
        win, box = self._dialog(f"Grupo — {group_state.get('name') or 'novo'}")
        win.set_default_size(460, -1)

        box.append(Gtk.Label(label="Nome do grupo", xalign=0))
        name_e = Gtk.Entry()
        name_e.set_text(group_state.get("name", ""))
        box.append(name_e)

        crow, color = self._color_picker_row(win, group_state.get("color") or "#3b82f6")
        box.append(crow)

        box.append(Gtk.Label(label="Líder (opcional)", xalign=0))
        leader_combo = Gtk.ComboBoxText()
        box.append(leader_combo)

        box.append(Gtk.Label(label="Membros", xalign=0))
        members_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(members_box)

        member_widgets: list[tuple] = []  # (name_entry, agent_combo, instr_textview, color)

        def refresh_leader_combo():
            leader_combo.remove_all()
            leader_combo.append_text(NO_LEADER)
            names = [w[0].get_text().strip() for w in member_widgets]
            for n in names:
                if n:
                    leader_combo.append_text(n)
            cur = group_state.get("leader")
            idx = names.index(cur) + 1 if cur and cur in names else 0
            leader_combo.set_active(idx)

        def add_member_row(m: dict | None = None):
            m = m or {"name": "", "agent": "claude", "instruction": "", "color": ""}
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            name_ent = Gtk.Entry()
            name_ent.set_placeholder_text("papel (ex.: coder)")
            name_ent.set_text(m["name"])
            name_ent.set_hexpand(True)
            top.append(name_ent)
            agent_combo = Gtk.ComboBoxText()
            for a in ("claude", "codex"):
                agent_combo.append_text(a)
            agent_combo.set_active(1 if m.get("agent") == "codex" else 0)
            top.append(agent_combo)
            remb = Gtk.Button(label="✕")
            top.append(remb)
            row.append(top)
            instr_tv = Gtk.TextView()
            instr_tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            instr_tv.get_buffer().set_text(m.get("instruction", ""))
            instr_sc = Gtk.ScrolledWindow()
            instr_sc.set_min_content_height(50)
            instr_sc.set_child(instr_tv)
            row.append(instr_sc)
            members_box.append(row)
            entry = (name_ent, agent_combo, instr_tv, m.get("color", ""))
            member_widgets.append(entry)
            name_ent.connect("changed", lambda _e: refresh_leader_combo())

            def do_remove(_b):
                member_widgets.remove(entry)
                members_box.remove(row)
                refresh_leader_combo()

            remb.connect("clicked", do_remove)

        for m in group_state.get("members", []):
            add_member_row(m)
        refresh_leader_combo()

        addm = Gtk.Button(label="+ Membro")
        addm.connect("clicked", lambda _b: (add_member_row(), refresh_leader_combo()))
        box.append(addm)

        foot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        foot.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda _b: win.destroy())
        save = Gtk.Button(label="Salvar")
        save.add_css_class("suggested-action")

        def do_save(_b):
            members = []
            for name_ent, agent_combo, instr_tv, mcolor in member_widgets:
                buf = instr_tv.get_buffer()
                instruction = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
                members.append({
                    "name": name_ent.get_text().strip(),
                    "agent": agent_combo.get_active_text() or "claude",
                    "instruction": instruction,
                    "color": mcolor,
                })
            leader_text = leader_combo.get_active_text()
            leader = leader_text if leader_text and leader_text != NO_LEADER else None
            updated = {
                "name": name_e.get_text().strip(),
                "color": color["hex"],
                "leader": leader,
                "members": members,
            }
            win.destroy()
            on_group_saved(updated)

        save.connect("clicked", do_save)
        foot.append(cancel)
        foot.append(save)
        box.append(foot)
        win.present()
        name_e.grab_focus()

    def _team_edit_dialog(self, staging: dict, original_name: str | None, on_saved) -> None:
        """Cria/edita um `TeamTemplate` inteiro (Fase C, docs/14 §11). `staging` é um dict
        no shape de `TeamTemplate.to_dict()` (rascunho editável); `original_name` = nome
        anterior (edição/rename) ou `None` (novo/duplicado de um built-in)."""
        win, box = self._dialog("Editar equipe" if original_name else "Nova equipe (template)")
        win.set_default_size(460, -1)

        box.append(Gtk.Label(label="Nome", xalign=0))
        name_e = Gtk.Entry()
        name_e.set_text(staging.get("name", ""))
        box.append(name_e)

        box.append(Gtk.Label(label="Descrição", xalign=0))
        desc_e = Gtk.Entry()
        desc_e.set_text(staging.get("description", ""))
        box.append(desc_e)

        box.append(Gtk.Label(label="Grupos", xalign=0))
        groups_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.append(groups_box)

        err_lbl = Gtk.Label(label="", xalign=0)
        err_lbl.set_wrap(True)

        def refresh_groups():
            child = groups_box.get_first_child()
            while child is not None:
                nxt = child.get_next_sibling()
                groups_box.remove(child)
                child = nxt
            for i, g in enumerate(staging.get("groups", [])):
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                lbl = Gtk.Label(
                    label=f"{g.get('name') or '(sem nome)'} ({len(g.get('members', []))} "
                          "membro(s))",
                    xalign=0,
                )
                lbl.set_hexpand(True)
                row.append(lbl)
                editb = Gtk.Button(label="Editar")
                editb.connect("clicked", lambda _b, idx=i: open_group_editor(idx))
                row.append(editb)
                remg = Gtk.Button(label="Remover")

                def do_remove_group(_b, idx=i):
                    staging["groups"].pop(idx)
                    refresh_groups()

                remg.connect("clicked", do_remove_group)
                row.append(remg)
                groups_box.append(row)

        def open_group_editor(idx: int):
            def on_group_saved(updated_group):
                staging["groups"][idx] = updated_group
                refresh_groups()

            self._team_group_edit_dialog(staging["groups"][idx], on_group_saved)

        def add_group(_b):
            staging.setdefault("groups", []).append(
                {"name": "Grupo", "color": "", "leader": None, "members": []}
            )
            refresh_groups()
            open_group_editor(len(staging["groups"]) - 1)

        refresh_groups()
        addg = Gtk.Button(label="+ Grupo")
        addg.connect("clicked", add_group)
        box.append(addg)
        box.append(err_lbl)

        foot = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        foot.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Cancelar")
        cancel.connect("clicked", lambda _b: win.destroy())
        save = Gtk.Button(label="Salvar")
        save.add_css_class("suggested-action")

        def do_save(_b):
            staging["name"] = name_e.get_text().strip()
            staging["description"] = desc_e.get_text().strip()
            ok, msg = self._save_team_from_staging(staging, original_name)
            if not ok:
                err_lbl.set_text(f"⚠ {msg}")
                return
            win.destroy()
            on_saved()

        save.connect("clicked", do_save)
        foot.append(cancel)
        foot.append(save)
        box.append(foot)
        win.present()
        name_e.grab_focus()

    def _open_team_dialog(self) -> None:
        """FAB '🧩 Montar equipe' (docs/14 §5.A3): lista TeamTemplates (built-in + salvos),
        preview de grupos/papéis, botão Montar. Criar/editar/duplicar pela UI (Fase C, §11)."""
        win, box = self._dialog("🧩 Montar equipe")
        win.set_default_size(480, -1)

        def reabrir():
            win.destroy()
            self._open_team_dialog()

        novo = Gtk.Button(label="+ Novo template")
        novo.connect(
            "clicked",
            lambda _b: self._team_edit_dialog(
                {"name": "", "description": "", "manager": None, "groups": []},
                None,
                reabrir,
            ),
        )
        box.append(novo)
        box.append(Gtk.Separator())

        templates = self._team_templates()
        if not templates:
            box.append(Gtk.Label(label="(nenhum template disponível)"))
        for tpl in templates:
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            head = Gtk.Label(label=tpl.name, xalign=0)
            head.add_css_class("team-template-name")
            row.append(head)
            if tpl.description:
                desc = Gtk.Label(label=tpl.description, xalign=0)
                desc.set_wrap(True)
                desc.add_css_class("dim-label")
                row.append(desc)
            preview = " · ".join(
                f"{g.name}: {', '.join(m.name for m in g.members)}" for g in tpl.groups
            )
            prev_lbl = Gtk.Label(label=preview, xalign=0)
            prev_lbl.set_wrap(True)
            prev_lbl.add_css_class("dim-label")
            row.append(prev_lbl)
            actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            montar = Gtk.Button(label="Montar")
            montar.add_css_class("suggested-action")
            montar.connect("clicked", lambda _b, t=tpl: self._confirm_materialize_team(win, t))
            actions.append(montar)
            if tpl.name not in BUILTIN_TEAM_TEMPLATES:
                editar = Gtk.Button(label="Editar")
                editar.connect(
                    "clicked",
                    lambda _b, t=tpl: self._team_edit_dialog(t.to_dict(), t.name, reabrir),
                )
                actions.append(editar)
                excluir = Gtk.Button(label="Excluir")

                def do_excluir(_b, name=tpl.name):
                    restantes = [t for t in self._team_templates() if t.name != name]
                    self._save_team_templates(restantes)
                    win.destroy()
                    self._open_team_dialog()

                excluir.connect("clicked", do_excluir)
                actions.append(excluir)
            else:
                duplicar = Gtk.Button(label="Duplicar")

                def do_duplicar(_b, t=tpl):
                    staging = t.to_dict()
                    staging["name"] = f"{t.name}-copia"
                    self._team_edit_dialog(staging, None, reabrir)

                duplicar.connect("clicked", do_duplicar)
                actions.append(duplicar)
            row.append(actions)
            box.append(row)
            box.append(Gtk.Separator())
        win.present()

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
        if frame._title_entry is not None:
            frame._title_entry.set_text(f"{note_title_display(note)} · rodando {agent}…")

        def done(env, updated, updated_note):
            def apply():
                fresh = self.notes.get(frame._note_id)
                if fresh is not None:
                    frame._body_view.get_buffer().set_text(fresh.body)
                    if frame._title_entry is not None:
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
        if getattr(self, "_refreshing_attn", False):
            return True  # reentrância (set_node_state chamou de volta): ignora e evita recursão
        self._refreshing_attn = True
        try:
            items = attention_items(self._store)
            current: set = set()
            for it in items:
                self.set_node_state(it.agent, _ST_MAP.get(it.state, "blocked"))  # realça o nó
                key = (it.agent, it.state)
                current.add(key)
                if key not in self._notified:  # notifica só o que é novo
                    notify(f"maestro: {it.agent} precisa de você", it.state)
            self._notified = current  # poda p/ os atuais: sem leak; re-notifica se voltar
            # "⚠ N" = UNIÃO envelope ∪ estado visual (ex.: monitor de quietude → "waiting")
            nids = attention_nids(items, self._node_state, self.frames)
            self._attn_label.set_text(f"⚠ {len(nids)}" if nids else "")
        finally:
            self._refreshing_attn = False
        self._mm_refresh()  # minimapa realça os nós em atenção (cor do estado)
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
        install_maestri_client(ask_bus_dir)  # instala o `maestri` (Maestro mode, Fase 6)
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
            # (a injeção do role é feita em _add_node → _apply_node_role, na ordem correta)
            if nid != base and nid not in controller.agents:  # instância extra (runtime)
                try:
                    controller.add_agent_instance(nid, base)
                except Exception:
                    controller.agents[nid] = prof  # já no registry: garante só o profile
            # restaura o auto-aprovar persistido (Maestro mode / toggle permissão total)
            auto = bool(model.node_cfg(nid, "maestro") or model.node_cfg(nid, "autoapprove"))
            argv = agent_argv(prof, str(wsp), node=nid, ask_bus_dir=ask_bus_dir, auto_approve=auto)
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
        win.start_ram_watcher()  # badge de RAM por nó em worker thread (unload — Bloco D)
        # tick in-app do scheduler: dispara routines vencidas enquanto aberto (V10-S4)
        GLib.timeout_add_seconds(30, win._routines_tick)
        # attention: realça/notifica o que precisa de você (V11-S1)
        GLib.timeout_add_seconds(10, win._refresh_attention)
        win._refresh_attention()

    def on_shutdown(_a):
        win = state.get("win")  # F7: encerra o servidor de socket (fecha listeners, unlink)
        if win is not None and getattr(win, "_sock_server", None) is not None:
            win._sock_server.stop()
        if win is not None and getattr(win, "_ram_stop", None) is not None:
            win._ram_stop.set()  # encerra o worker de RAM (daemon; set é só higiene)
        st = state.get("store")
        if st is not None:
            st.close()

    app.connect("activate", on_activate)
    app.connect("shutdown", on_shutdown)
    app.run([])
