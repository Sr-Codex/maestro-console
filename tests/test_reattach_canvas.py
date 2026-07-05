"""R3 do reattach (docs/25 §4-R3): a ação "Reanexar" num nó órfão, no canvas real.

Roda no python do SISTEMA (importa CanvasWindow → PyGObject). Prova que um órfão
(`orphan`+`unloaded`+`session`) reataca via `_reload_node` — o MESMO caminho do ⏏ do
unload — retomando com `--resume` e limpando AMBAS as flags. Molde de
`test_unload_reload_canvas.py`: método REAL sob teste, só as fronteiras são mockadas.
"""

import pytest

pytest.importorskip("gi")
from canvas_harness import patch_agents as _patch_agents  # noqa: E402
from canvas_harness import term as _term  # noqa: E402
from canvas_harness import win as _win  # noqa: E402

from maestro.engine.sandbox import bwrap_available  # noqa: E402
from maestro.engine.state.store import Store  # noqa: E402

pytestmark = pytest.mark.skipif(not bwrap_available(), reason="bwrap ausente")


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
