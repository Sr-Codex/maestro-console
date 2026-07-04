"""Unload — Bloco A′ no canvas: captura/persistência da sessão do nó + limpeza no fechar.

Testa os métodos finos do `CanvasWindow` contra um `CanvasModel` REAL (fronteira de dados
legítima, não mockada) e um workspace/dir-de-projeto em tmp. O `_close_node` é exercido de
verdade (não só o helper), com um nó SEM frame → roda a limpeza e retorna cedo no check de
frame, sem precisar construir GTK.
"""

import os

import pytest

pytest.importorskip("gi")  # canvas usa PyGObject; o .venv é gi-free → python do sistema
from maestro.engine.state.store import Store  # noqa: E402
from maestro.native.canvas import CanvasWindow  # noqa: E402
from maestro.native.state import CanvasModel  # noqa: E402


def _write_session(home, ws_path, sid, mtime):
    """Grava um JSONL de sessão no dir de projeto do Claude para `ws_path` (sob `home`)."""
    from maestro.engine.session_capture import project_dir

    pdir = project_dir(ws_path, home=home)
    pdir.mkdir(parents=True, exist_ok=True)
    f = pdir / f"{sid}.jsonl"
    f.write_text('{"type":"assistant"}\n', encoding="utf-8")
    os.utime(f, (mtime, mtime))


def _win_with_model(store, home, ws_base):
    w = CanvasWindow.__new__(CanvasWindow)  # sem __init__ → não cria GTK
    w.model = CanvasModel(store)
    # _node_ws real usa Path(self._ask_bus_dir).parent / "workspaces" / nid;
    # apontamos o ask_bus_dir p/ um irmão de "workspaces" sob ws_base.
    w._ask_bus_dir = str(ws_base / "askbus")
    # HOME injetado: forçamos Path.home() a resolver p/ o tmp (o helper de captura usa Path.home()).
    return w


def test_capture_persiste_session_id(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    store = Store(tmp_path / "m.db")
    w = _win_with_model(store, tmp_path, tmp_path)
    nid = "term1"
    ws = str(w._node_ws(nid))
    _write_session(tmp_path, ws, "sid-abc", mtime=2000)

    got = w._capture_node_session(nid)
    assert got == "sid-abc"
    assert w._node_session(nid) == "sid-abc"  # persistido no ui_state
    store.close()


def test_capture_pega_a_sessao_mais_nova(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    store = Store(tmp_path / "m.db")
    w = _win_with_model(store, tmp_path, tmp_path)
    nid = "term1"
    ws = str(w._node_ws(nid))
    _write_session(tmp_path, ws, "old", mtime=1000)
    _write_session(tmp_path, ws, "new", mtime=3000)
    assert w._capture_node_session(nid) == "new"
    store.close()


def test_capture_sem_sessao_nao_persiste(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    store = Store(tmp_path / "m.db")
    w = _win_with_model(store, tmp_path, tmp_path)
    nid = "term1"
    assert w._capture_node_session(nid) is None  # nó nunca gravou sessão
    assert w._node_session(nid) == ""
    store.close()


def test_close_node_limpa_sessao_persistida(tmp_path, monkeypatch):
    """Wiring REAL: _close_node apaga nodecfg_{nid}_session (id órfão não herda sessão morta)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    store = Store(tmp_path / "m.db")
    w = _win_with_model(store, tmp_path, tmp_path)
    nid = "term1"
    ws = str(w._node_ws(nid))
    _write_session(tmp_path, ws, "sid-doomed", mtime=2000)
    w._capture_node_session(nid)
    assert w._node_session(nid) == "sid-doomed"

    # setup mínimo p/ _close_node rodar a limpeza e retornar cedo (nó sem frame):
    w._set_node_monitor = lambda *_a, **_k: None
    w._mon_alerted = set()
    w._ram_alerted = set()  # Bloco D
    w._sock_server = None
    w._agent_nids = set()
    w._recruited_by = {}
    w._agent_base = lambda _nid: None
    w.controller = None
    w.frames = {}  # sem frame → retorna após a limpeza

    w._close_node(nid)
    assert w._node_session(nid) == ""  # sessão apagada
    store.close()
