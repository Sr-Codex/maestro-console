"""R3 do reattach (docs/25 §4-R3): a ação "Reanexar" num nó órfão, no canvas real.

Roda no python do SISTEMA (importa CanvasWindow → PyGObject). Prova que um órfão
(`orphan`+`unloaded`+`session`) reataca via `_reload_node` — o MESMO caminho do ⏏ do
unload — retomando com `--resume` e limpando AMBAS as flags. Molde de
`test_unload_reload_canvas.py`: método REAL sob teste, só as fronteiras são mockadas.
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("gi")
from maestro.engine.adapters.base import load_profiles  # noqa: E402
from maestro.engine.sandbox import bwrap_available  # noqa: E402
from maestro.engine.state.store import Store  # noqa: E402
from maestro.native.canvas import CanvasWindow  # noqa: E402
from maestro.native.state import CanvasModel  # noqa: E402

pytestmark = pytest.mark.skipif(not bwrap_available(), reason="bwrap ausente")


def _term(pid=None):
    return SimpleNamespace(
        _child_pid=pid, _pidfd=None, _respawn_state="idle", _respawn_pending=False,
        _respawn_force_src=None, _destroyed=False,
        reset=lambda *_a: None, feed=lambda *_a: None,
        connect=lambda *_a, **_k: 1, disconnect=lambda *_a: None,
    )


def _win(store, tmp_path, nid, term, *, base="claude"):
    w = CanvasWindow.__new__(CanvasWindow)
    w.model = CanvasModel(store)
    w.model.set_node_roster([{"nid": nid, "kind": "agent", "base": base}])
    w._ask_bus_dir = str(tmp_path / "askbus")
    (tmp_path / "askbus").mkdir(exist_ok=True)
    w.frames = {nid: SimpleNamespace(_term=term, _base_argv=["/bin/bash"])}
    w._mon = {}
    w._mon_alerted = set()
    w._ram_alerted = set()
    w._node_state = {}
    w._focused_nid = None
    w.heads = {}
    w.plane = SimpleNamespace(queue_draw=lambda: None)
    return w


def _patch_agents(monkeypatch, *bases):
    profs = load_profiles()
    monkeypatch.setattr("maestro.native.canvas.installed_agents",
                        lambda: {b: profs[b] for b in bases})


def test_reanexar_orfao_retoma_e_limpa_ambas_as_flags(tmp_path, monkeypatch):
    """Órfão (orphan+unloaded+session) → _reload_node retoma com --resume e limpa
    orphan E unloaded (o rótulo de crash não sobrevive à recuperação)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    nid = "claude"
    spawned = []
    with Store(tmp_path / "m.db") as store:
        w = _win(store, tmp_path, nid, _term())
        _patch_agents(monkeypatch, "claude")
        monkeypatch.setattr("maestro.native.canvas._spawn_into",
                            lambda *a, **k: spawned.append(a))
        # estado que o R2 (detect_orphans) deixa persistido no boot:
        w.model.set_node_cfg(nid, "orphan", "1")
        w.model.set_node_cfg(nid, "unloaded", "1")
        w.model.set_node_cfg(nid, "session", "sid-crash")
        assert w._node_orphan(nid) is True  # nasceu órfão

        w._reload_node(nid)  # = a ação "Reanexar" (mesmo caminho do ⏏)

        assert len(spawned) == 1
        assert "claude --resume sid-crash" in spawned[0][1][-1]  # retomou a sessão do crash
        assert w._node_orphan(nid) is False  # rótulo de órfão limpo
        assert w._node_unloaded(nid) is False  # e não está mais dormente


def test_novo_agente_orfao_comeca_do_zero_e_limpa_flags(tmp_path, monkeypatch):
    """A ação "Novo agente" (✧): descarta a sessão do crash e spawna do ZERO (sem --resume),
    limpando orphan+unloaded."""
    monkeypatch.setenv("HOME", str(tmp_path))
    nid = "claude"
    spawned = []
    with Store(tmp_path / "m.db") as store:
        w = _win(store, tmp_path, nid, _term())
        _patch_agents(monkeypatch, "claude")
        monkeypatch.setattr("maestro.native.canvas._spawn_into",
                            lambda *a, **k: spawned.append(a))
        w.model.set_node_cfg(nid, "orphan", "1")
        w.model.set_node_cfg(nid, "unloaded", "1")
        w.model.set_node_cfg(nid, "session", "sid-crash")

        w._selected = ("node", nid)  # _ctx_new_agent → _sel_nid lê a seleção
        w._ctx_new_agent()  # método REAL (bound no CanvasWindow via __new__)

        assert len(spawned) == 1
        assert "--resume" not in spawned[0][1][-1]  # começou do ZERO (sem retomar)
        assert w.model.node_cfg(nid, "session") == ""  # sessão do crash descartada
        assert w._node_orphan(nid) is False
        assert w._node_unloaded(nid) is False
