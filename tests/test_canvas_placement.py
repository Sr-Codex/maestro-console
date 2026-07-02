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
    return w


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
