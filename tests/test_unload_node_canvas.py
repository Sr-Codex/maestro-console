"""Unload — Bloco B: ação "Descarregar" (kill sem respawn + flag persistida + guard).

Prova em RUNTIME (não só lógica): o kill usa um PROCESSO REAL (sleep) e verifica o
SIGKILL de verdade. A race achada na revisão adversarial (respawn em voo ressuscita o
nó descarregado) é reproduzida com o `_on_child_exited` REAL — só a fronteira GLib
(scheduler) é substituída, nunca o método sob teste.
"""

import signal
import subprocess
from types import SimpleNamespace

import pytest

pytest.importorskip("gi")  # canvas usa PyGObject; o .venv é gi-free → python do sistema
from maestro.engine.state.store import Store  # noqa: E402
from maestro.native.canvas import CanvasWindow  # noqa: E402
from maestro.native.state import CanvasModel  # noqa: E402


def _term(pid=None, state="idle", pending=False):
    return SimpleNamespace(
        _child_pid=pid, _pidfd=None, _respawn_state=state,
        _respawn_pending=pending, _respawn_force_src=None, _destroyed=False,
        reset=lambda *_a: None,
        feed=lambda *_a: None,  # Bloco C: o unload escreve o hint de retomada no terminal
    )


def _win(store, tmp_path, nid, term):
    w = CanvasWindow.__new__(CanvasWindow)  # sem __init__ → não cria GTK
    w.model = CanvasModel(store)
    w._ask_bus_dir = str(tmp_path / "askbus")  # _node_ws → tmp/workspaces/<nid>
    (tmp_path / "askbus").mkdir(exist_ok=True)
    w.frames = {nid: SimpleNamespace(_term=term, _base_argv=["/bin/bash"])}
    w._mon = {nid: {"handler": None, "quiet_id": None}}  # monitor "ligado" (sem GTK)
    w._mon_alerted = {nid}
    w._ram_alerted = set()  # Bloco D: alerta de RAM (unload/close limpam)
    w._node_state = {}
    w.heads = {}
    w.plane = SimpleNamespace(queue_draw=lambda: None)
    return w


def test_unload_mata_processo_real_sem_respawn(tmp_path, monkeypatch):
    """Fluxo inteiro com um processo VIVO de verdade: SIGKILL real, monitor desligado,
    flag persistida, sessão capturada (A′) antes de matar."""
    monkeypatch.setenv("HOME", str(tmp_path))
    nid = "term1"
    p = subprocess.Popen(["sleep", "60"])
    try:
        with Store(tmp_path / "m.db") as store:
            term = _term(pid=p.pid)
            w = _win(store, tmp_path, nid, term)
            # sessão viva do nó no dir de projeto (fonte da captura A′)
            from maestro.engine.session_capture import project_dir
            pdir = project_dir(str(w._node_ws(nid)), home=tmp_path)
            pdir.mkdir(parents=True)
            (pdir / "sid-live.jsonl").write_text("{}\n", encoding="utf-8")

            w._unload_node(nid)

            assert p.wait(timeout=5) == -signal.SIGKILL  # morreu com SIGKILL REAL
            assert w._node_unloaded(nid) is True  # flag persistida
            assert w._node_session(nid) == "sid-live"  # A′ capturou ANTES de matar
            assert nid not in w._mon  # monitor desligado (sem falso "é sua vez")
            assert nid not in w._mon_alerted
            assert term._respawn_state == "idle" and term._respawn_pending is False
    finally:
        if p.poll() is None:
            p.kill()


def test_race_respawn_em_voo_ressuscitaria_sem_o_fix(tmp_path, monkeypatch):
    """Prova a RACE achada na revisão: com respawn em voo ('killing'), o child-exited
    REAL agenda o respawn — se o unload não zerasse o estado, o nó ressuscitaria."""
    monkeypatch.setenv("HOME", str(tmp_path))
    nid = "term1"
    scheduled = []
    with Store(tmp_path / "m.db") as store:
        term = _term(pid=None, state="killing")  # respawn em voo, filho já sem pid
        w = _win(store, tmp_path, nid, term)
        monkeypatch.setattr(  # fronteira: só o scheduler GLib (não o método sob teste)
            "maestro.native.canvas.GLib",
            SimpleNamespace(idle_add=lambda fn, *a: scheduled.append(a),
                            source_remove=lambda *_: None),
        )
        w._on_child_exited(term, 0, nid)  # child-exited REAL
        assert scheduled  # SEM o fix do unload, o respawn é agendado (a race existe)


def test_unload_zera_respawn_em_voo_e_nao_ressuscita(tmp_path, monkeypatch):
    """O fix: _unload_node zera 'killing'/pending ANTES do kill → o child-exited que
    segue o SIGKILL NÃO agenda respawn (o nó fica morto, como pedido)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    nid = "term1"
    scheduled = []
    with Store(tmp_path / "m.db") as store:
        term = _term(pid=None, state="killing", pending=True)  # pior caso: os DOIS
        w = _win(store, tmp_path, nid, term)
        monkeypatch.setattr(
            "maestro.native.canvas.GLib",
            SimpleNamespace(idle_add=lambda fn, *a: scheduled.append(a),
                            source_remove=lambda *_: None),
        )
        w._unload_node(nid)
        w._on_child_exited(term, 0, nid)  # o exit que o SIGKILL provocaria
        assert scheduled == []  # NÃO ressuscita
        assert w._node_unloaded(nid) is True


def test_do_respawn_limpa_flag_unloaded(tmp_path, monkeypatch):
    """Qualquer respawn (todos os ~8 gatilhos passam por _do_respawn) limpa a flag —
    'descarregado' nunca fica mentindo com processo vivo."""
    monkeypatch.setenv("HOME", str(tmp_path))
    nid = "term1"
    spawned = []
    with Store(tmp_path / "m.db") as store:
        term = _term()
        w = _win(store, tmp_path, nid, term)
        w.model.set_node_cfg(nid, "unloaded", "1")
        monkeypatch.setattr(  # fronteira real: spawn de PTY no widget VTE
            "maestro.native.canvas._spawn_into", lambda *a, **k: spawned.append(a))
        assert w._do_respawn(nid) is False  # idle one-shot
        assert spawned  # respawnou de verdade (fronteira registrou)
        assert w._node_unloaded(nid) is False  # flag limpa


def test_close_node_limpa_flag_unloaded(tmp_path, monkeypatch):
    """✕ num nó descarregado: nid reciclado não pode nascer 'descarregado' (id órfão)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    nid = "term1"
    with Store(tmp_path / "m.db") as store:
        w = _win(store, tmp_path, nid, _term())
        w.model.set_node_cfg(nid, "unloaded", "1")
        # setup mínimo p/ _close_node rodar a limpeza e retornar cedo (sem frame GTK)
        w._set_node_monitor = lambda *_a, **_k: None
        w._sock_server = None
        w._agent_nids = set()
        w._recruited_by = {}
        w._agent_base = lambda _n: None
        w.controller = None
        w.frames = {}
        w._close_node(nid)
        assert w._node_unloaded(nid) is False


def test_unload_msg_reforca_quando_ocupado():
    """Guard: confirmação SEMPRE; quando busy o aviso é reforçado (turno em voo)."""
    idle = CanvasWindow._unload_msg(False)
    busy = CanvasWindow._unload_msg(True)
    assert "liberar RAM" in idle and "TRABALHANDO" not in idle
    assert "TRABALHANDO" in busy and "turno em voo" in busy
    assert idle in busy  # o texto base está nos dois (o busy só ANTEPÕE o aviso)
