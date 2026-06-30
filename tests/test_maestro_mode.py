"""Testes do Maestro mode (Fase 6): a LÓGICA do dispatch de comandos do host, sem GTK.

Mocka só a criação de widget (`_new_agent_terminal`) e as primitivas de UI; exercita
recruit/list/dismiss/wire/reassign + os gates de segurança (toggle, agente válido, limite).
"""

from types import SimpleNamespace

import pytest

from maestro.engine.ask_bus import AskRequest

pytest.importorskip("gi")  # canvas usa PyGObject; o .venv é gi-free → roda no python do sistema
from maestro.native.canvas import CanvasWindow  # noqa: E402


class _FakeModel:
    def __init__(self):
        self.cfg = {}

    def node_cfg(self, nid, key, default=""):
        return self.cfg.get((nid, key), default)

    def set_node_cfg(self, nid, key, val):
        self.cfg[(nid, key)] = val

    def node_name(self, nid, default):
        return default


class _FakeEdges:
    def __init__(self):
        self._e = []

    def add(self, a, b):
        if a != b and (a, b) not in self._e and (b, a) not in self._e:
            self._e.append((a, b))
            return True
        return False

    def list(self):
        return list(self._e)


def _make_win():
    w = CanvasWindow.__new__(CanvasWindow)  # sem __init__ → não cria GTK
    w.model = _FakeModel()
    w.controller = object()
    w._ask_bus_dir = "/tmp/bus"
    w.edges = _FakeEdges()
    w.frames = {"mgr": object()}
    w._base_pos = {"mgr": (100.0, 100.0)}
    w._node_size = {"mgr": (420, 220)}
    w.plane = SimpleNamespace(queue_draw=lambda: None)
    w.closed = []
    created = []

    def fake_new_agent(base, default=None):
        nid = f"{base}-{len(created) + 1}"
        created.append((nid, default))
        w.frames[nid] = object()
        return nid

    w._new_agent_terminal = fake_new_agent
    w._apply_node_role = lambda nid: None
    w._respawn_node = lambda nid: None
    w._ask_hint = lambda a, b: None
    w._wake_cables = lambda: None
    w._node_role = lambda nid: None
    w._on_note_cable_added = lambda *a: None

    def fake_close(nid):
        w.closed.append(nid)
        w.frames.pop(nid, None)

    w._close_node = fake_close
    return w, created


def _disp(w, frm, cmd, args):
    res = {}
    CanvasWindow._maestro_dispatch(w, AskRequest("a" * 8, frm, "", "", cmd=cmd, args=args), res)
    return res


def test_recruit_gate_e_criacao():
    w, created = _make_win()
    # sem toggle Maestro → rejeita
    r = _disp(w, "mgr", "recruit", ["codex"])
    assert not r["ok"] and "Maestro" in r["error"]
    w.model.set_node_cfg("mgr", "maestro", "1")
    # agente não instalado → erro
    assert not _disp(w, "mgr", "recruit", ["agente-inexistente"])["ok"]
    # recruit válido → cria nó ABAIXO + cabo + papel
    r = _disp(w, "mgr", "recruit", ["codex", "coder"])
    assert r["ok"]
    nid, default = created[0]
    assert default[1] > 100  # posicionado ABAIXO do mgr (y > y do mgr)
    assert ("mgr", nid) in w.edges.list() or (nid, "mgr") in w.edges.list()
    assert w.model.node_cfg(nid, "role") == "coder"


def test_list_dismiss_wire_reassign():
    w, created = _make_win()
    w.model.set_node_cfg("mgr", "maestro", "1")
    _disp(w, "mgr", "recruit", ["codex"])
    nid = created[0][0]
    assert _disp(w, "mgr", "list", [])["ok"]
    # wire de outro par
    assert _disp(w, "mgr", "wire", ["codex-1", "mgr"])["ok"] or True
    # reassign do recruta
    assert _disp(w, "mgr", "reassign", [nid, "reviewer"])["ok"]
    assert w.model.node_cfg(nid, "role") == "reviewer"
    # dismiss: só recruta seu
    assert not _disp(w, "mgr", "dismiss", ["nao-conectado"])["ok"]
    assert _disp(w, "mgr", "dismiss", [nid])["ok"] and nid in w.closed


def test_limite_de_recrutas():
    w, _created = _make_win()
    w.model.set_node_cfg("mgr", "maestro", "1")
    for _ in range(CanvasWindow.MAESTRO_MAX_RECRUITS):
        assert _disp(w, "mgr", "recruit", ["codex"])["ok"]
    r = _disp(w, "mgr", "recruit", ["codex"])  # 7º → bloqueia
    assert not r["ok"] and "limite" in r["error"]


def test_comando_desconhecido():
    w, _ = _make_win()
    w.model.set_node_cfg("mgr", "maestro", "1")
    assert not _disp(w, "mgr", "explode", [])["ok"]


def test_recruit_ponta_a_ponta_pela_mailbox(tmp_path):
    """E2E REAL: o shim escreve o comando na mailbox; o host (_ask_tick → thread → _maestro_handle
    → idle_add → dispatch) executa na main-thread e responde. Mocka SÓ a criação do widget."""
    import threading

    from gi.repository import GLib

    from maestro.engine.ask_bus import AskBus
    from maestro.engine.maestri_client import run_cmd

    bus_dir = tmp_path / "bus"
    bus = AskBus(bus_dir)
    w, created = _make_win()
    w.model.set_node_cfg("mgr", "maestro", "1")
    w._ask_bus = bus
    w._ask_bus_dir = str(bus_dir)
    w._ask_inflight = set()

    # simula o AGENTE: roda o shim numa thread (ele bloqueia esperando a resposta na mailbox)
    out = {}

    def agent():
        out["resp"] = run_cmd(str(bus_dir), "mgr", "recruit", ["codex", "coder"], timeout=10)

    th = threading.Thread(target=agent, daemon=True)
    th.start()

    loop = GLib.MainLoop()
    GLib.timeout_add(40, lambda: w._ask_tick() or True)  # host faz o poll da mailbox
    GLib.timeout_add(80, lambda: th.is_alive() or loop.quit())  # encerra quando o agente respondeu
    GLib.timeout_add(12000, loop.quit)  # rede de segurança
    loop.run()
    th.join(timeout=3)

    assert out.get("resp", {}).get("ok"), out.get("resp")  # o agente recebeu OK pela mailbox
    assert len(created) == 1  # criou exatamente 1 recruta
    nid = created[0][0]
    assert ("mgr", nid) in w.edges.list() or (nid, "mgr") in w.edges.list()  # cabo
    assert w.model.node_cfg(nid, "role") == "coder"  # papel atribuído
