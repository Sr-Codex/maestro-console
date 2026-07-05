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


def test_tooltips_da_capsula_cientes_do_estado(tmp_path):
    """O ⏏ é um toggle: num nó VIVO descarrega (libera RAM), num ÓRFÃO reataca. O tooltip
    tem de refletir isso — senão o ⏏ num órfão diria 'libera RAM' e enganaria (achado do
    usuário). Idem 🗑: em órfão é 'Arquivar' (preserva o trabalho), não 'Fechar/remove'."""
    with Store(tmp_path / "m.db") as store:
        w = _win(store, tmp_path, "claude", None)  # sem terminal; só a cápsula
        w.edges = None                    # pula o botão conectar
        w._update_note_ctx = lambda: None  # stub (não é o foco)
        w._build_node_ctx()               # monta a cápsula real (seta _ctx_unl/new/del_btn)
        w._selected = ("node", "claude")

        w._update_ctx()  # nó VIVO
        assert "Descarregar" in w._ctx_unl_btn.get_tooltip_text()
        assert "Fechar" in w._ctx_del_btn.get_tooltip_text()
        assert w._ctx_new_btn.get_visible() is False  # ✧ só em órfão
        for b in (w._ctx_unl_btn, w._ctx_new_btn, w._ctx_del_btn):  # vivo: sem âmbar
            assert b.has_css_class("orphan-action") is False

        w.model.set_node_cfg("claude", "orphan", "1")
        w.model.set_node_cfg("claude", "unloaded", "1")
        w._update_ctx()  # ÓRFÃO
        assert "Reanexar" in w._ctx_unl_btn.get_tooltip_text()
        assert "Arquivar" in w._ctx_del_btn.get_tooltip_text()
        assert w._ctx_new_btn.get_visible() is True
        for b in (w._ctx_unl_btn, w._ctx_new_btn, w._ctx_del_btn):  # órfão: os 3 âmbar
            assert b.has_css_class("orphan-action") is True
