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


def to_display(base: tuple[float, float], zoom: float) -> tuple[int, int]:
    """Coordenada-base (independente do zoom) -> posição no plano: display = base * zoom."""
    return (round(base[0] * zoom), round(base[1] * zoom))


def to_base(display: tuple[float, float], zoom: float) -> tuple[float, float]:
    """Posição no plano -> coordenada-base: base = display / zoom (zoom<=0 cai p/ 1.0)."""
    z = zoom if zoom and zoom > 0 else 1.0  # 'or' deixava passar negativos
    return (display[0] / z, display[1] / z)
