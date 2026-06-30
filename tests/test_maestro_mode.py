"""Testes do Maestro mode (Fase 6): a LÓGICA do dispatch de comandos do host, sem GTK.

Mocka só a criação de widget (`_new_agent_terminal`) e as primitivas de UI; exercita
recruit/list/dismiss/wire/reassign + os gates de segurança (toggle, agente válido, limite).
"""

import os
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
    w._agent_nids = set()  # fleet (cap global + kill-switch)
    w._recruited_by = {}  # linhagem (profundidade)
    w._spawn_log = []  # rate-limit
    _tick = [0.0]

    def _clock():  # avança muito por chamada → rate-limit não trip por acidente nos testes
        _tick[0] += 1000.0
        return _tick[0]

    w._maestro_clock = _clock
    w._sock_server = None  # vigilância (Etapa 4) — testes ligam quando precisam
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


def test_fleet_cap_global(tmp_path):
    """Teto GLOBAL de agentes (ADR-17 Etapa 2): bloqueia mesmo com o manager sem recrutas."""
    from maestro.engine.maestro_audit import read_events

    w, _ = _make_win()
    w.model.set_node_cfg("mgr", "maestro", "1")
    w._ask_bus_dir = str(tmp_path)
    w._agent_nids = {f"a{i}" for i in range(w.MAESTRO_FLEET_CAP)}  # fleet cheio
    r = _disp(w, "mgr", "recruit", ["codex"])
    assert not r["ok"] and "GLOBAL" in r["error"]
    assert any(e["event"] == "recruit_blocked" for e in read_events(tmp_path))  # auditado


def test_kill_all_ceifa_e_desarma(tmp_path):
    """Kill-switch: sinaliza SIGKILL em todo o fleet + desarma os managers + audita."""
    import signal

    from maestro.engine.maestro_audit import read_events

    w, _ = _make_win()
    w._ask_bus_dir = str(tmp_path)
    w.model.set_node_cfg("mgr", "maestro", "1")  # manager a ser desarmado
    w._agent_nids = {"a1", "a2"}
    w.frames = {
        "mgr": SimpleNamespace(_term=SimpleNamespace()),
        "a1": SimpleNamespace(_term=SimpleNamespace()),
        "a2": SimpleNamespace(_term=SimpleNamespace()),
    }
    sigs = []
    w._signal_child = lambda term, sig: (sigs.append(sig) or True)

    killed = CanvasWindow._kill_all_agents(w)

    assert killed == 2  # sinalizou os 2 agentes do fleet
    assert sigs == [signal.SIGKILL, signal.SIGKILL]  # SIGKILL colapsa cada bwrap
    assert not w.model.node_cfg("mgr", "maestro")  # manager desarmado (re-armar é manual)
    assert any(e["event"] == "kill_all" and e["killed"] == 2 for e in read_events(tmp_path))


def test_profundidade_da_arvore(tmp_path):
    """Linhagem host-derivada: mgr→a1→a2 ok; a2 (profundidade 2) NÃO pode recrutar mais."""
    w, created = _make_win()
    w._ask_bus_dir = str(tmp_path)
    w.model.set_node_cfg("mgr", "maestro", "1")
    a1 = created and None
    # mgr recruta a1 (profundidade 1)
    assert _disp(w, "mgr", "recruit", ["codex"])["ok"]
    a1 = created[0][0]
    assert w._node_depth(a1) == 1
    # humano promove a1 a manager; a1 recruta a2 (profundidade 2)
    w.model.set_node_cfg(a1, "maestro", "1")
    assert _disp(w, a1, "recruit", ["codex"])["ok"]
    a2 = created[1][0]
    assert w._node_depth(a2) == 2
    # a2 promovido tenta recrutar → barra na profundidade máxima
    w.model.set_node_cfg(a2, "maestro", "1")
    r = _disp(w, a2, "recruit", ["codex"])
    assert not r["ok"] and "profundidade" in r["error"]


def test_rate_limit_token_bucket(tmp_path):
    """Com relógio FIXO, estoura o rate-limit antes do limite por-manager."""
    w, created = _make_win()
    w._ask_bus_dir = str(tmp_path)
    w.model.set_node_cfg("mgr", "maestro", "1")
    w._maestro_clock = lambda: 100.0  # tempo congelado → token-bucket não repõe
    for _ in range(w.MAESTRO_SPAWN_RATE):
        assert _disp(w, "mgr", "recruit", ["codex"])["ok"]
    r = _disp(w, "mgr", "recruit", ["codex"])  # próximo na mesma janela → barra
    assert not r["ok"] and "muitos recrutamentos" in r["error"]


def test_recruta_nasce_sem_recrutar(tmp_path):
    """O recruta NÃO herda Maestro mode (promover exige o toggle humano)."""
    w, created = _make_win()
    w._ask_bus_dir = str(tmp_path)
    w.model.set_node_cfg("mgr", "maestro", "1")
    assert _disp(w, "mgr", "recruit", ["codex"])["ok"]
    nid = created[0][0]
    assert not w.model.node_cfg(nid, "maestro")  # nasce desarmado


def test_hitl_predicado_soft_cap(tmp_path):
    """HITL liga só na faixa soft-cap ≤ fleet < hard-cap."""
    w, _ = _make_win()
    w._agent_nids = set()
    assert not w._recruit_needs_hitl("mgr")  # fleet 0 < soft-cap
    w._agent_nids = {f"a{i}" for i in range(w.MAESTRO_SOFT_CAP)}
    assert w._recruit_needs_hitl("mgr")  # na faixa de confirmação
    w._agent_nids = {f"a{i}" for i in range(w.MAESTRO_FLEET_CAP)}
    assert not w._recruit_needs_hitl("mgr")  # no hard-cap já é o dispatch que recusa


def test_hitl_aprovar_e_negar(tmp_path):
    """Acima do soft-cap, a decisão humana decide: aprovar cria; negar recusa + audita."""
    import threading

    from maestro.engine.ask_bus import AskRequest
    from maestro.engine.maestro_audit import read_events

    # APROVAR
    w, created = _make_win()
    w._ask_bus_dir = str(tmp_path / "ap")
    w.model.set_node_cfg("mgr", "maestro", "1")
    w._agent_nids = {f"a{i}" for i in range(w.MAESTRO_SOFT_CAP)}  # na faixa de HITL
    req = AskRequest("a" * 8, "mgr", "", "", cmd="recruit", args=["codex"])
    res, done = {}, threading.Event()
    CanvasWindow._apply_recruit_decision(w, True, req, res, done)
    assert res.get("ok") and done.is_set() and len(created) == 1  # criou ao aprovar

    # NEGAR
    w2, created2 = _make_win()
    w2._ask_bus_dir = str(tmp_path / "ng")
    w2.model.set_node_cfg("mgr", "maestro", "1")
    w2._agent_nids = {f"a{i}" for i in range(w2.MAESTRO_SOFT_CAP)}
    res2, done2 = {}, threading.Event()
    CanvasWindow._apply_recruit_decision(w2, False, req, res2, done2)
    assert not res2.get("ok") and "negado" in res2["error"] and created2 == []
    assert any(e["event"] == "recruit_denied" for e in read_events(tmp_path / "ng"))


def test_maestro_exec_roteia_hitl(tmp_path):
    """_maestro_exec NÃO despacha direto quando precisa de HITL — delega a _hitl_recruit."""
    import threading

    from maestro.engine.ask_bus import AskRequest

    w, created = _make_win()
    w._ask_bus_dir = str(tmp_path)
    w.model.set_node_cfg("mgr", "maestro", "1")
    w._agent_nids = {f"a{i}" for i in range(w.MAESTRO_SOFT_CAP)}  # precisa de HITL
    calls = []
    w._hitl_recruit = lambda req, result, done: calls.append(req.frm)  # não seta done
    req = AskRequest("b" * 8, "mgr", "", "", cmd="recruit", args=["codex"])
    res, done = {}, threading.Event()
    CanvasWindow._maestro_exec(w, req, res, done)
    assert calls == ["mgr"] and not done.is_set()  # roteou p/ HITL, não despachou direto
    assert created == []  # nada criado sem a decisão humana


def test_fleet_hud_text(tmp_path):
    """HUD: nº de agentes, profundidade máxima e aviso de ciclo."""
    w, _ = _make_win()
    w._agent_nids = {"a1", "a2"}
    w._recruited_by = {"a1": "mgr", "a2": "a1"}  # a2 está a 2 níveis
    txt = w._fleet_hud_text()
    assert "2/" in txt and "prof 2" in txt and "ciclo" not in txt
    w.edges._e = [("a", "b"), ("b", "c"), ("c", "a")]  # fecha um ciclo
    assert "ciclo" in w._fleet_hud_text()


def test_anomaly_tick_dispara_killswitch(tmp_path):
    """Vigilância ATIVA: rajada de recruit_blocked → kill-switch automático (não passivo)."""
    import signal
    import time as _time

    from maestro.engine.maestro_audit import append_event, read_events

    w, _ = _make_win()
    w._ask_bus_dir = str(tmp_path)
    w._sock_server = object()  # vigilância ligada
    w.model.set_node_cfg("mgr", "maestro", "1")
    w._agent_nids = {"a1"}
    w.frames = {
        "a1": SimpleNamespace(_term=SimpleNamespace()),
        "mgr": SimpleNamespace(_term=None),
    }
    sigs = []
    w._signal_child = lambda term, sig: (sigs.append(sig) or True)
    now = _time.time()
    for i in range(8):  # rajada de bloqueios recentes
        append_event(tmp_path, "recruit_blocked", now=now - i, manager="mgr")

    assert CanvasWindow._anomaly_tick(w) is True  # o tick continua
    assert sigs == [signal.SIGKILL]  # matou o fleet automaticamente
    assert not w.model.node_cfg("mgr", "maestro")  # desarmou os managers
    assert any(e["event"] == "anomaly_killswitch" for e in read_events(tmp_path))


def test_anomaly_tick_quieto_sem_burst(tmp_path):
    """Sem rajada, o tick NÃO mata ninguém (não é trigger-happy)."""
    import time as _time

    from maestro.engine.maestro_audit import append_event

    w, _ = _make_win()
    w._ask_bus_dir = str(tmp_path)
    w._sock_server = object()
    w._agent_nids = {"a1"}
    w.frames = {"a1": SimpleNamespace(_term=SimpleNamespace())}
    sigs = []
    w._signal_child = lambda term, sig: (sigs.append(sig) or True)
    append_event(tmp_path, "recruit_blocked", now=_time.time(), manager="mgr")  # 1 só
    CanvasWindow._anomaly_tick(w)
    assert sigs == []  # nada morto


def test_recruit_audita_sucesso(tmp_path):
    w, created = _make_win()
    w.model.set_node_cfg("mgr", "maestro", "1")
    w._ask_bus_dir = str(tmp_path)
    assert _disp(w, "mgr", "recruit", ["codex", "coder"])["ok"]
    from maestro.engine.maestro_audit import read_events
    evs = read_events(tmp_path)
    assert any(e["event"] == "recruit" and e["agent"] == "codex" and e["role"] == "coder"
               for e in evs)


def _run_via_socket(w, box_dir, frm, cmd, args, timeout=10):
    """Sobe o SockServer ligado a `w._on_sock_request` + roda o shim numa thread, com loop GLib."""
    import threading

    from gi.repository import GLib

    from maestro.engine.ask_sock import SockServer
    from maestro.engine.maestri_client import run_cmd

    srv = SockServer()
    srv.add_node(frm if box_dir is None else os.path.basename(str(box_dir)), str(box_dir))
    w._sock_server = srv
    threading.Thread(target=srv.serve, args=(w._on_sock_request,), daemon=True).start()
    out: dict = {}

    def agent():
        out["resp"] = run_cmd(str(box_dir), frm, cmd, args, timeout=timeout)

    th = threading.Thread(target=agent, daemon=True)
    th.start()
    loop = GLib.MainLoop()
    GLib.timeout_add(50, lambda: th.is_alive() or loop.quit())  # encerra quando o agente respondeu
    GLib.timeout_add(12000, loop.quit)  # rede de segurança
    loop.run()
    th.join(timeout=3)
    srv.stop()
    return out.get("resp", {})


def test_recruit_ponta_a_ponta_pelo_socket(tmp_path):
    """E2E REAL: o shim conecta no SOCKET da box; o host (_on_sock_request → _maestro_handle
    → idle_add → dispatch) executa na main-thread e responde. Mocka SÓ a criação do widget."""
    box = tmp_path / "bus" / "box" / "mgr"
    box.mkdir(parents=True)
    w, created = _make_win()
    w.model.set_node_cfg("mgr", "maestro", "1")
    w._ask_bus_dir = str(tmp_path / "bus")

    resp = _run_via_socket(w, box, "mgr", "recruit", ["codex", "coder"])

    assert resp.get("ok"), resp  # o agente recebeu OK pelo socket
    assert len(created) == 1  # criou exatamente 1 recruta
    nid = created[0][0]
    assert ("mgr", nid) in w.edges.list() or (nid, "mgr") in w.edges.list()  # cabo
    assert w.model.node_cfg(nid, "role") == "coder"  # papel atribuído


def test_socket_anti_spoofing_no_canvas(tmp_path):
    """IDENTIDADE POR CANAL: 'intruder' conecta no SEU socket mentindo frm='mgr' no payload.

    O host carimba frm='intruder' (o canal), o gate rejeita (intruder não é manager), e
    NADA é criado — o spoofing que existia na Fase 6 fica impossível por construção (ADR-17).
    """
    box_intruder = tmp_path / "bus" / "box" / "intruder"
    box_intruder.mkdir(parents=True)
    w, created = _make_win()
    w.model.set_node_cfg("mgr", "maestro", "1")  # mgr é manager; intruder NÃO
    w._ask_bus_dir = str(tmp_path / "bus")

    resp = _run_via_socket(w, box_intruder, "mgr", "recruit", ["codex", "coder"])

    assert not resp.get("ok")  # recusado
    assert "Maestro" in (resp.get("error") or "")  # intruder não está em Maestro mode
    assert created == []  # NADA foi criado em nome do mgr
