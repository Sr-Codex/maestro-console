"""Bloco 3 — monitor de atividade padrão-ON nos nós-AGENTE (tri-estado).
Testa `_node_is_agent`/`_monitor_default_on` do canvas (métodos REAIS; mocka só o model)."""
import pytest

pytest.importorskip("gi")  # canvas usa PyGObject; roda no python do SISTEMA
from maestro.native.canvas import CanvasWindow  # noqa: E402


class _Model:
    """Fronteira mockada (CanvasModel): só roster + cfg, que é o que os métodos usam."""

    def __init__(self, roster, cfg=None):
        self._roster = roster
        self._cfg = cfg or {}

    def node_roster(self):
        return self._roster

    def node_cfg(self, nid, key, default=""):
        return self._cfg.get((nid, key), default)


def _win(roster, cfg=None):
    w = CanvasWindow.__new__(CanvasWindow)  # sem __init__ → não cria GTK
    w.model = _Model(roster, cfg)
    return w


def test_node_is_agent_pelo_roster():
    w = _win([{"nid": "a", "kind": "agent"}, {"nid": "s", "kind": "shell"}])
    assert w._node_is_agent("a") is True
    assert w._node_is_agent("s") is False
    assert w._node_is_agent("sumido") is False  # conservador: desconhecido = NÃO agente


def test_monitor_padrao_on_no_agente_sem_cfg():
    # nó-agente sem cfg explícita → padrão LIGADO (fecha a dor "não percebi que parou")
    w = _win([{"nid": "a", "kind": "agent"}])
    assert w._monitor_default_on("a") is True


def test_monitor_padrao_off_no_shell_sem_cfg():
    # shell sem cfg → DESLIGADO (um bash ocioso não pode virar 'waiting' à toa)
    w = _win([{"nid": "s", "kind": "shell"}])
    assert w._monitor_default_on("s") is False


def test_cfg_explicita_vence_o_default():
    # "0" desliga um agente; "1" liga um shell — o explícito manda sobre o default-por-tipo
    w = _win(
        [{"nid": "a", "kind": "agent"}, {"nid": "s", "kind": "shell"}],
        cfg={("a", "monitor"): "0", ("s", "monitor"): "1"},
    )
    assert w._monitor_default_on("a") is False
    assert w._monitor_default_on("s") is True
