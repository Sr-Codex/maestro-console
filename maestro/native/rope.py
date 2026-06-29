"""Corda Verlet — física de cabo orgânico, pura (sem GTK), testável.

Cadeia de pontos com integração de Verlet + restrições de distância (Jakobsen,
*Advanced Character Physics*, GDC 2001): as pontas ficam fixas nas âncoras e o
miolo cai por gravidade e balança com inércia, assentando num sag tipo catenária.

Passo de tempo FIXO (estável p/ Verlet) — as constantes são "por frame" a ~60fps,
não dependem do dt real (frame lento só desacelera a sim, sem explodir).
"""

from __future__ import annotations

import math

ROPE_SEGMENTS = 16  # nº de pontos da corda (mais = mais suave, mais custo)
ROPE_GRAVITY = 0.55  # ganho de velocidade p/ baixo por frame (sag)
ROPE_DAMPING = 0.97  # atrito do ar (assenta o balanço; <1)
ROPE_SLACK = 1.18  # folga: comprimento de repouso = distância × isto (>1 ⇒ sag)
ROPE_ITERS = 4  # iterações de restrição por passo (estabilidade)
ROPE_REST_EPS = 0.06  # deslocamento (px/frame) abaixo disto ⇒ ponto em repouso


def make_rope(p0, p3, n=ROPE_SEGMENTS):
    """Corda RETA entre p0 e p3, em repouso (velocidade zero: prev == pts)."""
    pts = [
        (p0[0] + (p3[0] - p0[0]) * i / (n - 1), p0[1] + (p3[1] - p0[1]) * i / (n - 1))
        for i in range(n)
    ]
    return {"pts": pts, "prev": list(pts)}


def catenary_pts(p0, p3, n=ROPE_SEGMENTS, sag_ratio=0.18):
    """Cabo pendurado ESTÁTICO (parábola ≈ catenária): barriga proporcional ao vão, sem
    física. Acompanha os nós na hora; nunca balança. `sag_ratio` = quanto afunda no meio."""
    dx, dy = p3[0] - p0[0], p3[1] - p0[1]
    sag = math.hypot(dx, dy) * sag_ratio
    return [
        (p0[0] + dx * t, p0[1] + dy * t + sag * 4.0 * t * (1.0 - t))
        for t in (i / (n - 1) for i in range(n))
    ]


def spring_target(p0, p3, sag_ratio=0.18):
    """Ponto de controle ALVO (meio do vão + caída) da bezier com mola."""
    sag = math.dist(p0, p3) * sag_ratio
    return ((p0[0] + p3[0]) / 2.0, (p0[1] + p3[1]) / 2.0 + sag)


def quad_bezier_pts(p0, ctrl, p3, n=ROPE_SEGMENTS):
    """Amostra uma bezier quadrática p0→ctrl→p3 em n pontos (p/ o modo mola)."""
    out = []
    for i in range(n):
        t = i / (n - 1)
        u = 1.0 - t
        out.append(
            (
                u * u * p0[0] + 2 * u * t * ctrl[0] + t * t * p3[0],
                u * u * p0[1] + 2 * u * t * ctrl[1] + t * t * p3[1],
            )
        )
    return out


def step_rope(
    rope,
    p0,
    p3,
    *,
    gravity=ROPE_GRAVITY,
    damping=ROPE_DAMPING,
    slack=ROPE_SLACK,
    iters=ROPE_ITERS,
):
    """Avança um passo de física: fixa as pontas em p0/p3, integra Verlet com
    gravidade e resolve as restrições de comprimento. Devolve o MAIOR deslocamento
    de um ponto neste passo (px) — o caller usa p/ saber quando a corda 'assentou'."""
    pts, prev = rope["pts"], rope["prev"]
    n = len(pts)
    # integração de Verlet: nova_pos = pos + (pos - prev)*damping + gravidade
    # (pontas livres aqui; serão fixadas dentro das restrições)
    nxt = []
    for i in range(n):
        x, y = pts[i]
        px, py = prev[i]
        nxt.append((x + (x - px) * damping, y + (y - py) * damping + gravity))
    old = pts  # as posições ANTES da integração viram o prev do próximo passo
    # restrições: pontas presas + cada segmento ~ comprimento de repouso (com folga)
    seg = (math.dist(p0, p3) * slack) / (n - 1)
    for _ in range(iters):
        nxt[0] = p0
        nxt[-1] = p3
        for i in range(n - 1):
            ax, ay = nxt[i]
            bx, by = nxt[i + 1]
            dx, dy = bx - ax, by - ay
            d = math.hypot(dx, dy) or 1e-9
            k = (d - seg) / d * 0.5  # metade da correção p/ cada ponta do segmento
            ox, oy = dx * k, dy * k
            if i != 0:  # ponta 0 fica presa
                nxt[i] = (ax + ox, ay + oy)
            if i + 1 != n - 1:  # ponta n-1 fica presa
                nxt[i + 1] = (bx - ox, by - oy)
    nxt[0] = p0
    nxt[-1] = p3
    moved = 0.0
    for i in range(n):
        moved = max(moved, math.dist(nxt[i], old[i]))
    rope["pts"], rope["prev"] = nxt, old
    return moved
