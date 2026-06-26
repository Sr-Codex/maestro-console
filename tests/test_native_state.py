"""Testes do CanvasModel (V6-S2) — persistência de posições/zoom (sem GTK)."""

from maestro.engine.state.store import Store
from maestro.native.state import (
    GRID,
    CanvasModel,
    cable_bezier,
    snap_point,
    snap_to_grid,
    state_activity,
    to_base,
    to_display,
)


def test_state_activity_por_estado():
    assert state_activity("busy") == "trabalhando…"
    assert state_activity("blocked") == "esperando você"
    assert state_activity("done") == "concluído"
    assert state_activity("idle") == ""  # ocioso não mostra nada
    assert state_activity("desconhecido") == ""  # fallback seguro


# -- C3: snapping à grade --
def test_snap_to_grid_arredonda_pro_multiplo():
    assert snap_to_grid(0, GRID) == 0
    assert snap_to_grid(9, 20) == 0  # mais perto de 0
    assert snap_to_grid(11, 20) == 20  # mais perto de 20
    assert snap_to_grid(31, 20) == 40  # 31 -> 40 (mais perto)
    assert snap_to_grid(123, 0) == 123  # grid inválido não trava


def test_snap_point_imanta_xy():
    assert snap_point((11, 9), 20) == (20, 0)


# -- C5: geometria do cabo curvo --
def test_cable_bezier_pontas_e_controles_horizontais():
    # origem 0..100 (largura 100, altura 40), destino em x=300
    x0, y0, c1x, c1y, c2x, c2y, x3, y3 = cable_bezier((0, 0, 100, 40), (300, 0, 100, 40))
    assert (x0, y0) == (100, 20)  # direita-centro da origem
    assert (x3, y3) == (300, 20)  # esquerda-centro do destino
    assert c1y == y0 and c2y == y3  # controles HORIZONTAIS (saída/entrada retas)
    assert c1x > x0 and c2x < x3  # curva "abre" pros lados


def test_cable_bezier_piso_de_curvatura_quando_proximos():
    # nós sobrepostos/colados: ainda gera curvatura mínima (piso 40)
    _x0, _y0, c1x, _c1y, c2x, _c2y, _x3, _y3 = cable_bezier((0, 0, 100, 40), (100, 0, 100, 40))
    assert c1x - 100 == 40 and 100 - c2x == 40  # piso aplicado dos dois lados


def test_position_default_e_persistencia(tmp_path):
    with Store(tmp_path / "m.db") as s:
        m = CanvasModel(s)
        assert m.position("term1", (60, 60)) == (60, 60)  # default
        m.set_position("term1", 200, 150)
        assert m.position("term1", (0, 0)) == (200.0, 150.0)


def test_zoom_default_persistencia_e_limites(tmp_path):
    with Store(tmp_path / "m.db") as s:
        m = CanvasModel(s)
        assert m.zoom() == 1.0
        m.set_zoom(1.5)
        assert m.zoom() == 1.5
        m.set_zoom(99)  # clamp superior
        assert m.zoom() == 3.0
        m.set_zoom(0.01)  # clamp inferior
        assert m.zoom() == 0.3


def test_zoom_transform_display_eh_base_vezes_zoom():
    # o zoom escala a POSIÇÃO no plano infinito (não a fonte do terminal)
    assert to_display((100.0, 200.0), 1.0) == (100, 200)
    assert to_display((100.0, 200.0), 1.5) == (150, 300)
    assert to_display((100.0, 200.0), 0.5) == (50, 100)


def test_zoom_transform_round_trip_preserva_base():
    # arrastar com zoom != 1 e converter de volta não deve mover a coord-base
    for z in (0.3, 0.5, 1.0, 1.5, 3.0):
        dx, dy = to_display((120.0, 80.0), z)
        bx, by = to_base((dx, dy), z)
        assert abs(bx - 120.0) < 1.0 and abs(by - 80.0) < 1.0


def test_to_base_zoom_zero_nao_divide_por_zero():
    assert to_base((100.0, 100.0), 0.0) == (100.0, 100.0)  # cai p/ 1.0


def test_to_base_zoom_negativo_cai_para_um():
    # P1: 'or' só pegava 0.0; zoom negativo agora também cai p/ 1.0 (sem inverter coords)
    assert to_base((100.0, 100.0), -0.5) == (100.0, 100.0)


def test_to_display_arredonda_em_vez_de_truncar():
    # P3: round() (sem viés p/ origem) em vez de int() (trunca p/ zero). 3*0.5=1.5 -> 2, não 1
    assert to_display((3.0, 3.0), 0.5) == (2, 2)


def test_node_size_default_e_persistencia(tmp_path):
    with Store(tmp_path / "m.db") as s:
        m = CanvasModel(s)
        assert m.node_size("a1", (420, 220)) == (420, 220)  # default
        m.set_node_size("a1", 600, 300)
        assert m.node_size("a1", (0, 0)) == (600.0, 300.0)


def test_node_name_default_e_persistencia(tmp_path):
    with Store(tmp_path / "m.db") as s:
        m = CanvasModel(s)
        assert m.node_name("a1", "a1") == "a1"  # default = o próprio id
        m.set_node_name("a1", "Backend")
        assert m.node_name("a1", "x") == "Backend"  # persistido


def test_persiste_entre_instancias(tmp_path):
    db = tmp_path / "m.db"
    with Store(db) as s:
        CanvasModel(s).set_position("codex", 400, 300)
    with Store(db) as s2:
        assert CanvasModel(s2).position("codex", (0, 0)) == (400.0, 300.0)
