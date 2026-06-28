"""CanvasModel — estado do canvas nativo (posições/zoom), sem GTK (V6-S2).

Separa a lógica testável da parte gráfica. Persiste via o Store da engine
(tabelas node_positions e ui_state) — reusa, não duplica.
"""

from __future__ import annotations

import json

from ..engine.state.store import Store


class CanvasModel:
    def __init__(self, store: Store):
        self._store = store

    def position(self, node_id: str, default: tuple[float, float]) -> tuple[float, float]:
        p = self._store.get_node_positions().get(node_id)
        return (p["x"], p["y"]) if p else default

    def set_position(self, node_id: str, x: float, y: float) -> None:
        self._store.set_node_position(node_id, float(x), float(y))

    def zoom(self) -> float:
        z = self._store.get_ui("native_zoom")
        return float(z) if z else 1.0

    def set_zoom(self, z: float) -> None:
        self._store.set_ui("native_zoom", max(0.3, min(3.0, float(z))))

    def node_size(
        self, node_id: str, default: tuple[float, float]
    ) -> tuple[float, float]:
        """Tamanho (w,h) do card do nó, independente do zoom; default se não salvo."""
        s = self._store.get_ui(f"nodesize_{node_id}")
        if not s:
            return default
        try:
            w, h = str(s).split(",")
            return (float(w), float(h))
        except (ValueError, AttributeError):
            return default

    def set_node_size(self, node_id: str, w: float, h: float) -> None:
        self._store.set_ui(f"nodesize_{node_id}", f"{float(w)},{float(h)}")

    def node_name(self, node_id: str, default: str) -> str:
        """Nome de exibição do terminal (renomeável); default se não salvo."""
        n = self._store.get_ui(f"nodename_{node_id}")
        return str(n) if n else default

    def set_node_name(self, node_id: str, name: str) -> None:
        self._store.set_ui(f"nodename_{node_id}", name)

    def node_roster(self) -> list[dict]:
        """Lista persistida dos terminais do canvas: [{nid, kind: agent|shell, base}].
        É a FONTE da verdade de QUAIS cards existem (recriados no startup) — antes o
        startup recriava só os agentes instalados, perdendo shells/instâncias de runtime."""
        raw = self._store.get_ui("canvas_nodes")
        if not raw:
            return []
        try:
            v = json.loads(raw)
            return v if isinstance(v, list) else []
        except (ValueError, TypeError):
            return []

    def set_node_roster(self, roster: list[dict]) -> None:
        self._store.set_ui("canvas_nodes", json.dumps(roster))

    def add_to_roster(self, nid: str, kind: str, base: str | None) -> None:
        r = self.node_roster()
        if any(s.get("nid") == nid for s in r):
            return
        r.append({"nid": nid, "kind": kind, "base": base})
        self.set_node_roster(r)

    def remove_from_roster(self, nid: str) -> None:
        self.set_node_roster([s for s in self.node_roster() if s.get("nid") != nid])

    def terminal_theme(self) -> str:
        return self._store.get_ui("terminal_theme") or "default"

    def set_terminal_theme(self, name: str) -> None:
        self._store.set_ui("terminal_theme", name)


class EdgeModel:
    """Cabos criados pelo usuário (src -> dst), persistidos no Store (V7-S1).

    Ignora self-loop (src == dst) e deduplica (a tabela tem PK composta). Sem GTK.
    """

    def __init__(self, store: Store):
        self._store = store

    def add(self, src: str, dst: str) -> bool:
        """Cria o cabo; retorna False se for self-loop (ignorado)."""
        if src == dst:
            return False
        self._store.add_edge(src, dst)
        return True

    def remove(self, src: str, dst: str) -> None:
        self._store.remove_edge(src, dst)

    def list(self) -> list[tuple[str, str]]:
        return self._store.get_edges()


# E3 — status proativo: texto curto do que o agente está fazendo agora (por estado).
STATE_ACTIVITY = {
    "idle": "",
    "busy": "trabalhando…",
    "blocked": "esperando você",
    "failed": "falhou",
    "done": "concluído",
}


def state_activity(state: str) -> str:
    """Rótulo de atividade exibido no card (E3); vazio quando ocioso/desconhecido."""
    return STATE_ACTIVITY.get(state, "")


# C3 — grid + snapping (Fase 2). Passo do grid em coords-base (independe do zoom).
GRID = 20


def snap_to_grid(value: float, grid: int = GRID) -> float:
    """Arredonda um valor pro múltiplo de `grid` mais próximo (imã do snapping)."""
    if grid <= 0:
        return value
    return round(value / grid) * grid


def snap_point(point: tuple[float, float], grid: int = GRID) -> tuple[float, float]:
    """Imanta um ponto (x, y) à grade — usado ao soltar nó/nota."""
    return (snap_to_grid(point[0], grid), snap_to_grid(point[1], grid))


def cable_bezier(src_box, dst_box):
    """Curva tipo corda (C5) entre dois nós: cubic bezier que SAI/ENTRA pela borda
    mais próxima do outro endpoint (não mais fixo direita→esquerda).

    Escolhe o eixo dominante pela distância entre os CENTROS: se |Δx| ≥ |Δy| o cabo
    sai pela esquerda/direita (controles horizontais); senão pela cima/baixo (controles
    verticais). Assim o destino atrás/acima da origem não gera a "volta" feia.

    Recebe boxes `(x, y, w, h)` (já em coords de tela/escaladas) e devolve
    `(x0, y0, c1x, c1y, c2x, c2y, x3, y3)` p/ `cr.move_to`+`cr.curve_to`.
    """
    ax, ay, aw, ah = src_box
    bx, by, bw, bh = dst_box
    acx, acy = ax + aw / 2.0, ay + ah / 2.0  # centro da origem
    bcx, bcy = bx + bw / 2.0, by + bh / 2.0  # centro do destino
    dx, dy = bcx - acx, bcy - acy
    if abs(dx) >= abs(dy):  # eixo HORIZONTAL domina: sai pela esquerda/direita
        if dx >= 0:  # destino à direita
            x0, y0, x3, y3 = ax + aw, acy, bx, bcy
        else:  # destino à esquerda
            x0, y0, x3, y3 = ax, acy, bx + bw, bcy
        # curvatura = metade da distância horizontal, com piso p/ nós próximos/sobrepostos
        k = max(abs(x3 - x0) * 0.5, 40.0)
        s = 1.0 if x3 >= x0 else -1.0
        return (x0, y0, x0 + s * k, y0, x3 - s * k, y3, x3, y3)
    # eixo VERTICAL domina: sai por cima/baixo (controles verticais)
    if dy >= 0:  # destino abaixo
        x0, y0, x3, y3 = acx, ay + ah, bcx, by
    else:  # destino acima
        x0, y0, x3, y3 = acx, ay, bcx, by + bh
    k = max(abs(y3 - y0) * 0.5, 40.0)
    s = 1.0 if y3 >= y0 else -1.0
    return (x0, y0, x0, y0 + s * k, x3, y3 - s * k, x3, y3)


def minimap_layout(rects, mm_w: float, mm_h: float, pad: float = 4.0):
    """Escala+offset pra encaixar o 'mundo' (lista de rects (x,y,w,h) em coords-base)
    dentro do minimapa mm_w×mm_h, centralizado. Devolve (scale, offx, offy) tal que
    um ponto-mundo (x,y) vira (offx + x*scale, offy + y*scale). None se vazio (C1)."""
    rects = [r for r in rects if r is not None]
    if not rects:
        return None
    xs0 = min(r[0] for r in rects)
    ys0 = min(r[1] for r in rects)
    xs1 = max(r[0] + r[2] for r in rects)
    ys1 = max(r[1] + r[3] for r in rects)
    ww = max(xs1 - xs0, 1.0)
    wh = max(ys1 - ys0, 1.0)
    avail_w = max(mm_w - 2 * pad, 1.0)
    avail_h = max(mm_h - 2 * pad, 1.0)
    scale = min(avail_w / ww, avail_h / wh)
    offx = pad + (avail_w - ww * scale) / 2 - xs0 * scale
    offy = pad + (avail_h - wh * scale) / 2 - ys0 * scale
    return (scale, offx, offy)


def to_display(base: tuple[float, float], zoom: float) -> tuple[int, int]:
    """Coordenada-base (independente do zoom) -> posição no plano: display = base * zoom."""
    return (round(base[0] * zoom), round(base[1] * zoom))


def to_base(display: tuple[float, float], zoom: float) -> tuple[float, float]:
    """Posição no plano -> coordenada-base: base = display / zoom (zoom<=0 cai p/ 1.0)."""
    z = zoom if zoom and zoom > 0 else 1.0  # 'or' deixava passar negativos
    return (display[0] / z, display[1] / z)


def connected_notes(edges, node_id: str, note_ids) -> set:
    """Ids de NOTAS ligadas por cabo a `node_id`. `edges` = lista (src,dst); `note_ids` =
    conjunto de ids de nota conhecidos. Sem GTK (testável)."""
    out = set()
    for a, b in edges:
        if a == node_id and b in note_ids:
            out.add(b)
        elif b == node_id and a in note_ids:
            out.add(a)
    return out


def nodes_for_note(edges, note_id: str, node_ids) -> set:
    """Ids de NÓS ligados por cabo a `note_id`."""
    out = set()
    for a, b in edges:
        if a == note_id and b in node_ids:
            out.add(b)
        elif b == note_id and a in node_ids:
            out.add(a)
    return out
