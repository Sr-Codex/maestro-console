"""Unload — Bloco D no canvas: badge de RAM, camada de vista "descarregado" e limiar.

Padrão dos blocos anteriores: métodos REAIS sob teste; só widgets GTK viram fakes
que registram chamadas (set_text/set_from_icon_name/css).
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("gi")  # canvas usa PyGObject; o .venv é gi-free → python do sistema
from maestro.engine.state.store import Store  # noqa: E402
from maestro.native.canvas import CanvasWindow  # noqa: E402
from maestro.native.state import CanvasModel  # noqa: E402


class _Lbl:
    def __init__(self):
        self.text = ""
        self.tip = None
        self.classes = set()
        self.visible = True

    def set_text(self, t):
        self.text = t

    def set_visible(self, v):
        self.visible = bool(v)

    def set_tooltip_text(self, t):
        self.tip = t

    def add_css_class(self, c):
        self.classes.add(c)

    def remove_css_class(self, c):
        self.classes.discard(c)


class _Dot(_Lbl):
    def __init__(self):
        super().__init__()
        self.icon = None

    def set_from_icon_name(self, name):
        self.icon = name


def _win(store, tmp_path, nid):
    w = CanvasWindow.__new__(CanvasWindow)
    w.model = CanvasModel(store)
    w._store = store
    w._ask_bus_dir = str(tmp_path / "askbus")
    (tmp_path / "askbus").mkdir(exist_ok=True)
    w.frames = {nid: SimpleNamespace(_term=SimpleNamespace(_child_pid=None),
                                     _base_argv=["/bin/bash"])}
    w.heads = {nid: SimpleNamespace(_dot=_Dot(), _status=_Lbl(), _ram=_Lbl())}
    w._node_state = {}
    w._ram_alerted = set()
    w._mon = {}
    w._mon_alerted = set()
    w.plane = SimpleNamespace(queue_draw=lambda: None)
    return w


def test_fmt_ram():
    assert CanvasWindow._fmt_ram(0) == ""
    assert CanvasWindow._fmt_ram(312.4) == "312 MB"
    assert CanvasWindow._fmt_ram(2048) == "2.0 GB"


def test_vista_descarregado_no_dot_sem_estado_novo(tmp_path):
    """Camada de VISTA (Fable, docs/21 §8.3-3): idle+flag → eject/'descarregado';
    busy (handoff headless num nó descarregado) mostra busy NORMAL — a máquina de
    estados não conhece 'unloaded'; ao voltar a idle o eject reaparece sozinho."""
    nid = "term1"
    with Store(tmp_path / "m.db") as store:
        w = _win(store, tmp_path, nid)
        dot = w.heads[nid]._dot
        st = w.heads[nid]._status
        w.model.set_node_cfg(nid, "unloaded", "1")

        w.set_node_state(nid, "idle")
        assert dot.icon == "maestro-state-unloaded"
        assert st.text == "descarregado"
        assert w._node_state[nid] == "idle"  # máquina intocada: estado É idle

        w.set_node_state(nid, "busy")  # cabo trabalhando headless por cima
        assert dot.icon == "maestro-state-busy"  # busy real aparece (correto)

        w.set_node_state(nid, "idle")  # turno acabou → eject volta sozinho
        assert dot.icon == "maestro-state-unloaded"

        w.model.clear_node_cfg(nid, "unloaded")  # retomou (reload limpa a flag)
        w.set_node_state(nid, "idle")
        assert dot.icon == "maestro-state-idle"
        assert st.text != "descarregado"


def test_apply_ram_atualiza_badge_e_notifica_com_histerese(tmp_path, monkeypatch):
    """_apply_ram: badge + tooltip (PSS/Private), css no limiar exato, notificação 1x
    por cruzamento com re-arme só abaixo de 0.9×X (histerese de verdade, fluxo real)."""
    nid = "term1"
    fired = []
    monkeypatch.setattr("maestro.native.canvas.notify",
                        lambda title, body, **_k: fired.append(title))
    with Store(tmp_path / "m.db") as store:
        w = _win(store, tmp_path, nid)
        store.set_ui("ram_limit_mb", "500")
        lbl = w.heads[nid]._ram

        w._apply_ram({nid: (600.0, 520.0, 400.0)})  # cruzou (PSS 520 ≥ 500)
        assert lbl.text == "520 MB"
        assert "peso real (PSS) 520 MB" in lbl.tip and "Private) 400 MB" in lbl.tip
        assert "node-ram-high" in lbl.classes
        assert len(fired) == 1  # notificou no cruzamento

        w._apply_ram({nid: (560.0, 480.0, 380.0)})  # oscilou p/ baixo (480 > 450)
        assert "node-ram-high" not in lbl.classes  # css segue o limiar EXATO
        assert len(fired) == 1  # histerese: NÃO re-notifica

        w._apply_ram({nid: (580.0, 505.0, 390.0)})  # oscilou p/ cima de novo
        assert len(fired) == 1  # ainda armado — flapping não spamma

        w._apply_ram({nid: (300.0, 200.0, 150.0)})  # caiu de verdade (< 450)
        w._apply_ram({nid: (700.0, 640.0, 500.0)})  # novo cruzamento real
        assert len(fired) == 2  # re-armou e notificou de novo


def test_apply_ram_ignora_no_descarregado_e_fechado(tmp_path, monkeypatch):
    """Medição que chega DEPOIS de descarregar/fechar o nó não escreve nada."""
    nid = "term1"
    monkeypatch.setattr("maestro.native.canvas.notify", lambda *a, **k: None)
    with Store(tmp_path / "m.db") as store:
        w = _win(store, tmp_path, nid)
        lbl = w.heads[nid]._ram
        w.model.set_node_cfg(nid, "unloaded", "1")  # descarregou entre medir e aplicar
        w._apply_ram({nid: (600.0, 520.0, 400.0)})
        assert lbl.text == ""  # não escreve número velho num nó morto
        w._apply_ram({"ghost": (100.0, 90.0, 80.0)})  # nó que nem existe: silencioso


def test_unload_zera_badge_e_alerta_na_hora(tmp_path, monkeypatch):
    """_unload_node zera o badge JÁ (não espera o próximo tick) e some do alerta."""
    nid = "term1"
    monkeypatch.setenv("HOME", str(tmp_path))
    with Store(tmp_path / "m.db") as store:
        w = _win(store, tmp_path, nid)
        term = SimpleNamespace(_child_pid=None, _pidfd=None, _respawn_state="idle",
                               _respawn_pending=False, _respawn_force_src=None,
                               _destroyed=False, reset=lambda *_a: None,
                               feed=lambda *_a: None)
        w.frames[nid] = SimpleNamespace(_term=term, _base_argv=["/bin/bash"])
        lbl = w.heads[nid]._ram
        lbl.set_text("520 MB")
        lbl.add_css_class("node-ram-high")
        w._ram_alerted.add(nid)

        w._unload_node(nid)

        assert lbl.text == ""
        assert "node-ram-high" not in lbl.classes
        assert nid not in w._ram_alerted


def test_mm_items_pinta_descarregado_de_cinza(tmp_path):
    """Minimapa: branch EXPLÍCITO de descarregado (a claim 'de graça' era falsa)."""
    nid = "term1"
    with Store(tmp_path / "m.db") as store:
        w = _win(store, tmp_path, nid)
        w._base_pos = {nid: (10.0, 20.0)}
        w._node_size = {}
        w._note_base = {}
        w._ft_base = {}
        w._cam = (0.0, 0.0)
        w.scrolled = SimpleNamespace(get_width=lambda: 800, get_height=lambda: 480)
        items, _vp = w._mm_items()
        normal = items[0][4]
        w.model.set_node_cfg(nid, "unloaded", "1")
        items, _vp = w._mm_items()
        gray = items[0][4]
        assert gray != normal
        assert gray == (0.35, 0.37, 0.42)
