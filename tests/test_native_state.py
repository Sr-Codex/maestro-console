"""Testes do CanvasModel (V6-S2) — persistência de posições/zoom (sem GTK)."""

from maestro.engine.state.store import Store
from maestro.native.state import CanvasModel


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


def test_persiste_entre_instancias(tmp_path):
    db = tmp_path / "m.db"
    with Store(db) as s:
        CanvasModel(s).set_position("codex", 400, 300)
    with Store(db) as s2:
        assert CanvasModel(s2).position("codex", (0, 0)) == (400.0, 300.0)
