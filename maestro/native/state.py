"""CanvasModel — estado do canvas nativo (posições/zoom), sem GTK (V6-S2).

Separa a lógica testável da parte gráfica. Persiste via o Store da engine
(tabelas node_positions e ui_state) — reusa, não duplica.
"""

from __future__ import annotations

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


def cable_segments(
    positions: list[tuple[float, float]], w: float, h: float
) -> list[tuple[float, float, float, float]]:
    """Segmentos (x1,y1,x2,y2) ligando nós consecutivos da rota (handoffs).

    Conecta a borda direita de um nó à borda esquerda do próximo (centro vertical).
    `positions` são cantos superior-esquerdos; `w`,`h` o tamanho do nó.
    """
    segs = []
    for (ax, ay), (bx, by) in zip(positions, positions[1:], strict=False):
        segs.append((ax + w, ay + h / 2, bx, by + h / 2))
    return segs
