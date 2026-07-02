"""Testes de posicionamento GERAL de itens novos no canvas (nó/nota/grupo).

Regra pedida ao vivo (sessão de orquestração de equipe): NENHUM item novo pode nascer
sobreposto a um já existente — não só na materialização de equipe, mas em QUALQUER
criação (novo terminal, shell, árvore de arquivos, grupo, recrutar por cabo). A cascata
modular antiga (`_next_node_default`, mod 6) repetia posição cedo ou tarde; agora ela
(e `_place_below`, usado pelo recrutamento) verificam colisão real e caem pra uma área
genuinamente livre (`_free_region_origin`) quando a posição preferida colidiria.
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("gi")  # canvas usa PyGObject; o .venv é gi-free → roda no python do sistema
from maestro.native.canvas import BASE_H, BASE_W, CanvasWindow  # noqa: E402


def _fake_frame():
    return SimpleNamespace(get_width=lambda: 0, get_height=lambda: 0)


def _make_win():
    w = CanvasWindow.__new__(CanvasWindow)  # sem __init__ → não cria GTK
    w.frames = {}
    w.note_frames = {}
    w._ft_frames = {}
    w._base_pos = {}
    w._note_base = {}
    w._node_size = {}
    w.order = []
    w._group_base = {}
    w._group_size = {}
    w._maestro_connected = lambda nid: []  # sem recrutas por padrão
    w.model = SimpleNamespace(zoom=lambda: 1.0)
    w._cam = (0.0, 0.0)
    w.scrolled = SimpleNamespace(get_width=lambda: 1280, get_height=lambda: 720)
    return w


class _FakeModelWithPersistence:
    """Model fake que PREFERE valor persistido antigo (mesmo contrato do real
    `CanvasModel.position`/`node_size`) — pra reproduzir o id órfão/reciclado."""

    def __init__(self):
        self.positions = {}
        self.sizes = {}
        self.cfg = {}

    def position(self, nid, default):
        return self.positions.get(nid, default)

    def set_position(self, nid, x, y):
        self.positions[nid] = (x, y)

    def node_size(self, nid, default):
        return self.sizes.get(nid, default)

    def set_node_size(self, nid, w, h):
        self.sizes[nid] = (w, h)

    def node_cfg(self, nid, key, default=""):
        return self.cfg.get((nid, key), default)

    def set_node_cfg(self, nid, key, val):
        self.cfg[(nid, key)] = val

    def zoom(self):
        return 1.0

    def node_name(self, nid, default):
        return default

    def node_roster(self):
        return []

    def add_to_roster(self, nid, kind, base):
        pass


def _make_win_com_add_node_falso():
    """`_add_node` REAL cria widgets GTK de verdade (Gtk.Frame + VTE) — fronteira legítima
    pra mockar. O fake abaixo reproduz só o contrato observável que importa aqui: resolve
    posição/tamanho via `model.position`/`model.node_size` (onde mora o bug do id órfão) e
    registra em `frames`/`_base_pos`/`_node_size`/`order`, sem construir GTK de verdade."""
    w = _make_win()
    w.model = _FakeModelWithPersistence()
    w.plane = SimpleNamespace(
        queue_draw=lambda: None, put=lambda *a, **k: None,
        set_child_transform=lambda *a, **k: None,
    )
    w._cam = (0.0, 0.0)

    def fake_add_node(nid, _title, _argv, default):
        bx, by = w.model.position(nid, default)
        w._base_pos[nid] = (bx, by)
        sz = w.model.node_size(nid, (BASE_W, BASE_H))
        w._node_size[nid] = sz
        w.frames[nid] = _fake_frame()
        w.order.append(nid)

    w._add_node = fake_add_node
    w._resize_plane = lambda: None
    return w


def test_new_shell_terminal_nao_herda_posicao_e_tamanho_orfaos():
    """Regressão ao vivo: clicar '+ novo terminal' pela cápsula nascia em local antigo
    (id reciclado com posição/tamanho de um resize de sessão anterior), sobrepondo o
    que já existe agora — `model.position()/node_size()` preferem o valor persistido."""
    w = _make_win_com_add_node_falso()
    w.controller = object()
    orphan_nid = "shell-2"
    w.model.positions[orphan_nid] = (9999.0, 9999.0)
    w.model.sizes[orphan_nid] = (999.0, 999.0)
    # `_unique_nid` vai gerar exatamente "shell-2" (roster/frames/controller vazios)
    nid = CanvasWindow._new_shell_terminal(w)
    assert nid == orphan_nid
    assert w._base_pos[nid] != (9999.0, 9999.0)
    assert w._node_size[nid] == (BASE_W, BASE_H)
    assert w.model.positions[nid] == w._base_pos[nid]  # persistido sobrescrito
    assert w.model.sizes[nid] == (BASE_W, BASE_H)


def test_new_agent_terminal_nao_herda_posicao_e_tamanho_orfaos(tmp_path, monkeypatch):
    import maestro.native.canvas as canvas_mod

    w = _make_win_com_add_node_falso()
    w.controller = SimpleNamespace(add_agent_instance=lambda nid, base: None, agents={})
    w._ask_bus_dir = str(tmp_path / "bus")
    w._node_auto_approve = lambda nid: False

    monkeypatch.setattr(canvas_mod, "installed_agents", lambda: {"claude": {}})
    monkeypatch.setattr(canvas_mod, "agent_argv", lambda *a, **k: ["claude"])
    monkeypatch.setattr(canvas_mod, "install_ask_skill", lambda *a, **k: None)

    orphan_nid = "claude-2"
    w.model.positions[orphan_nid] = (9999.0, 9999.0)
    w.model.sizes[orphan_nid] = (999.0, 999.0)
    nid = CanvasWindow._new_agent_terminal(w, "claude")
    assert nid == orphan_nid
    assert w._base_pos[nid] != (9999.0, 9999.0)
    assert w._node_size[nid] == (BASE_W, BASE_H)
    assert w.model.positions[nid] == w._base_pos[nid]
    assert w.model.sizes[nid] == (BASE_W, BASE_H)


def test_rect_overlaps_any_detecta_no_existente():
    w = _make_win()
    w.frames["a"] = _fake_frame()
    w._base_pos["a"] = (100.0, 100.0)
    w._node_size["a"] = (BASE_W, BASE_H)
    assert CanvasWindow._rect_overlaps_any(w, 200.0, 150.0, BASE_W, BASE_H)  # sobrepõe "a"
    assert not CanvasWindow._rect_overlaps_any(w, 900.0, 900.0, BASE_W, BASE_H)  # longe


def test_rect_overlaps_any_detecta_nota_e_grupo():
    w = _make_win()
    w.note_frames["n"] = _fake_frame()
    w._note_base["n"] = (0.0, 0.0)
    w._group_base["g"] = (500.0, 500.0)
    w._group_size["g"] = (300.0, 200.0)
    assert CanvasWindow._rect_overlaps_any(w, 50.0, 50.0, 240.0, 160.0)  # bate na nota (240x160)
    assert CanvasWindow._rect_overlaps_any(w, 550.0, 550.0, 100.0, 100.0)  # dentro do grupo
    assert not CanvasWindow._rect_overlaps_any(w, 2000.0, 2000.0, 100.0, 100.0)


def test_next_node_default_canvas_vazio_usa_cascata_classica():
    w = _make_win()
    assert CanvasWindow._next_node_default(w) == (60, 60)


def test_next_node_default_evita_repetir_cascata_ocupada():
    """A cascata (mod 6) repetiria a MESMA posição em n=0 e n=6 — se essa posição já tem
    um item de verdade, o próximo item não pode nascer em cima."""
    w = _make_win()
    w.frames["existing"] = _fake_frame()
    w._base_pos["existing"] = (60.0, 60.0)  # exatamente a posição da cascata n=0
    w._node_size["existing"] = (BASE_W, BASE_H)
    w.order = ["existing"] * 6  # simula n=6 -> (60,60) de novo pela fórmula antiga
    ox, oy = CanvasWindow._next_node_default(w)
    assert (ox, oy) != (60, 60)  # não repete em cima do existente
    assert not CanvasWindow._rect_overlaps_any(w, float(ox), float(oy), BASE_W, BASE_H)


def test_next_node_default_livre_quando_cascata_nao_colide():
    """Continua usando a cascata (visual variado) quando ela NÃO colide com nada —
    não regride pra 'sempre embaixo de tudo' sem necessidade."""
    w = _make_win()
    w.frames["longe"] = _fake_frame()
    w._base_pos["longe"] = (2000.0, 2000.0)
    w._node_size["longe"] = (BASE_W, BASE_H)
    assert CanvasWindow._next_node_default(w) == (60, 60)  # cascata livre, sem mudança


def test_place_below_evita_sobrepor_quando_pilha_colide():
    w = _make_win()
    w.frames["mgr"] = _fake_frame()
    w._base_pos["mgr"] = (100.0, 100.0)
    w._node_size["mgr"] = (BASE_W, BASE_H)
    # algo já ocupa exatamente onde a pilha (1º recruta) cairia
    stacked_y = 100.0 + BASE_H + 40
    w.frames["obstaculo"] = _fake_frame()
    w._base_pos["obstaculo"] = (100.0, stacked_y)
    w._node_size["obstaculo"] = (BASE_W, BASE_H)
    px, py = CanvasWindow._place_below(w, "mgr")
    assert not CanvasWindow._rect_overlaps_any(w, float(px), float(py), BASE_W, BASE_H)
    assert (px, py) != (100, int(stacked_y))


def test_place_below_usa_pilha_normal_quando_livre():
    w = _make_win()
    w.frames["mgr"] = _fake_frame()
    w._base_pos["mgr"] = (100.0, 100.0)
    w._node_size["mgr"] = (BASE_W, BASE_H)
    px, py = CanvasWindow._place_below(w, "mgr")
    assert (px, py) == (100, int(100 + BASE_H + 40))


def test_next_node_default_acompanha_a_camera_quando_panorama():
    """Regressão ao vivo: "está aparecendo muito longe da vista" — se o usuário deu pan
    (câmera != (0,0)), o próximo item nasce perto de ONDE ELE ESTÁ OLHANDO, não no
    canto (0,0) absoluto do canvas infinito."""
    w = _make_win()
    w._cam = (-3000.0, -2000.0)  # câmera deslocada -> viewport atual está em (3000,2000)
    cx, cy = CanvasWindow._next_node_default(w)
    assert 2900 < cx < 3200
    assert 1900 < cy < 2200


def test_next_node_default_com_zoom_acompanha_a_camera():
    w = _make_win()
    w._cam = (-1500.0, -1000.0)
    w.model = SimpleNamespace(zoom=lambda: 2.0)
    cx, cy = CanvasWindow._next_node_default(w)
    # viewport base = -cam/z = (750, 500) no canto
    assert 700 < cx < 950
    assert 450 < cy < 700
