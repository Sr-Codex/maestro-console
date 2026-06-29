"""Testes da corda Verlet (física pura, sem GTK)."""

import math

from maestro.native.rope import (
    ROPE_SEGMENTS,
    catenary_pts,
    make_rope,
    quad_bezier_pts,
    spring_target,
    step_rope,
)


def _pt_eq(a, b):  # comparação aproximada de pontos (evita == em float, S1244)
    return math.dist(a, b) < 1e-9


def test_make_rope_reta_e_pontas():
    p0, p3 = (0.0, 0.0), (300.0, 0.0)
    r = make_rope(p0, p3)
    assert len(r["pts"]) == ROPE_SEGMENTS
    assert _pt_eq(r["pts"][0], p0) and _pt_eq(r["pts"][-1], p3)  # pontas nas âncoras
    # repouso: sem velocidade (prev == pts)
    assert all(_pt_eq(a, b) for a, b in zip(r["prev"], r["pts"], strict=True))
    mid = r["pts"][len(r["pts"]) // 2]
    assert abs(mid[1]) < 1e-9  # reta: miolo sem sag ainda


def test_step_mantem_pontas_presas():
    p0, p3 = (0.0, 0.0), (300.0, 0.0)
    r = make_rope(p0, p3)
    for _ in range(20):
        step_rope(r, p0, p3)
    assert _pt_eq(r["pts"][0], p0) and _pt_eq(r["pts"][-1], p3)  # pontas seguem fixas


def test_step_faz_o_miolo_cair_por_gravidade():
    p0, p3 = (0.0, 0.0), (300.0, 0.0)
    r = make_rope(p0, p3)
    for _ in range(30):
        step_rope(r, p0, p3)
    mid = r["pts"][len(r["pts"]) // 2]
    assert mid[1] > 5.0  # miolo afundou (y cresce p/ baixo) = sag por gravidade


def test_corda_assenta_apos_muitos_passos():
    p0, p3 = (0.0, 0.0), (300.0, 0.0)
    r = make_rope(p0, p3)
    last = 1e9
    for _ in range(400):
        last = step_rope(r, p0, p3)
    assert last < 0.5  # movimento por frame ficou pequeno = assentou


def test_pontas_acompanham_ancoras_que_se_movem():
    p0, p3 = (0.0, 0.0), (300.0, 0.0)
    r = make_rope(p0, p3)
    new0, new3 = (50.0, 20.0), (260.0, -10.0)
    step_rope(r, new0, new3)
    assert math.dist(r["pts"][0], new0) < 1e-9
    assert math.dist(r["pts"][-1], new3) < 1e-9


def test_catenaria_pontas_e_barriga():
    p0, p3 = (0.0, 0.0), (300.0, 0.0)
    pts = catenary_pts(p0, p3, sag_ratio=0.18)
    assert len(pts) == ROPE_SEGMENTS
    assert _pt_eq(pts[0], p0) and _pt_eq(pts[-1], p3)  # pontas exatas
    assert pts[len(pts) // 2][1] > 10.0  # miolo afunda (sag estático)


def test_catenaria_sag_menor_fica_mais_esticado():
    p0, p3 = (0.0, 0.0), (300.0, 0.0)
    muito = catenary_pts(p0, p3, sag_ratio=0.18)[ROPE_SEGMENTS // 2][1]
    pouco = catenary_pts(p0, p3, sag_ratio=0.10)[ROPE_SEGMENTS // 2][1]
    assert pouco < muito  # menos sag = mais esticado (modo bezier+mola)


def test_quad_bezier_passa_pelas_pontas():
    p0, ctrl, p3 = (0.0, 0.0), (150.0, 60.0), (300.0, 0.0)
    pts = quad_bezier_pts(p0, ctrl, p3)
    assert _pt_eq(pts[0], p0) and _pt_eq(pts[-1], p3)
    assert pts[len(pts) // 2][1] > 0  # caída em direção ao ctrl


def test_spring_target_fica_abaixo_do_meio():
    cx, cy = spring_target((0.0, 0.0), (300.0, 0.0), sag_ratio=0.10)
    assert math.isclose(cx, 150.0) and cy > 0.0  # meio do vão, deslocado p/ baixo
