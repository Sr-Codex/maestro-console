"""C2 (review docs/33): fechar um nó apaga TODO o estado por-nó, senão o id RECICLADO
(por `_unique_nid`) herda conta/credencial + bypass de permissão do nó fechado.

Teste gi-FREE (roda no venv/CI, não no ponto cego dos skipados) — exercita a camada de
persistência real (`CanvasModel.purge_node_state` → `Store.delete_ui_prefix`), que é o
cerne do fix. A fiação no `_close_node` (GTK) é coberta pelos testes de canvas gi.
"""

from maestro.engine.state.store import Store
from maestro.native.state import CanvasModel

# Toda a config sensível que o C2 vazava + nome + tamanho.
_CFG = ["account", "autoapprove", "maestro", "role", "command", "cwd", "env",
        "birth_group", "session", "unloaded", "orphan", "monitor", "theme"]


def _seed(m, nid):
    for k in _CFG:
        m.set_node_cfg(nid, k, f"{nid}-{k}")
    m.set_node_name(nid, f"nome-{nid}")
    m.set_node_size(nid, 800, 600)
    m._store.set_ui(f"usage_{nid}", "1.23")           # custo acumulado (HUD)
    m._store.set_ui(f"budget_last_{nid}", "9.99")     # baseline do budget (ADR-22)


def test_purge_apaga_toda_a_config_do_no(tmp_path):
    with Store(tmp_path / "m.db") as store:
        m = CanvasModel(store)
        _seed(m, "claude-2")
        m.purge_node_state("claude-2")
        # nada sobra: nem config, nem nome, nem tamanho, nem custo, nem baseline de budget
        leftover = {k: m.node_cfg("claude-2", k) for k in _CFG if m.node_cfg("claude-2", k)}
        assert not leftover, f"config órfã sobreviveu ao purge: {leftover}"
        assert m.node_name("claude-2", default="") == ""
        assert m.node_size("claude-2", None) is None
        assert store.get_ui("usage_claude-2") is None          # C2: HUD $ não herda
        assert store.get_ui("budget_last_claude-2") is None    # C2: baseline não subconta


def test_purge_nao_toca_outros_nos(tmp_path):
    """O purge é POR NID — o LIKE-por-prefixo não pode varrer nós irmãos (ex.: com id que
    seja prefixo de outro, 'claude-2' vs 'claude-20')."""
    with Store(tmp_path / "m.db") as store:
        m = CanvasModel(store)
        _seed(m, "claude-2")
        _seed(m, "claude-20")   # id do qual 'claude-2' é prefixo
        _seed(m, "codex-2")
        m.purge_node_state("claude-2")
        assert not any(m.node_cfg("claude-2", k) for k in _CFG)     # alvo limpo
        for nid in ("claude-20", "codex-2"):                        # irmãos intactos
            assert m.node_cfg(nid, "account") == f"{nid}-account", f"{nid} foi varrido junto"
            assert m.node_name(nid, default="") == f"nome-{nid}"
            assert m.node_size(nid, None) == (800.0, 600.0)


def test_id_reciclado_nao_herda_apos_purge(tmp_path):
    """O cenário-fim do C2: purga 'claude-2', o mesmo id volta a ser usado → nasce limpo."""
    with Store(tmp_path / "m.db") as store:
        m = CanvasModel(store)
        m.set_node_cfg("claude-2", "account", "cliente-secreta")
        m.set_node_cfg("claude-2", "autoapprove", "1")
        m.purge_node_state("claude-2")
        # id reusado: sem herança de conta nem de bypass
        assert m.node_cfg("claude-2", "account") == ""
        assert m.node_cfg("claude-2", "autoapprove") == ""


def test_delete_ui_prefix_escapa_metacaracteres(tmp_path):
    """`delete_ui_prefix` não pode deixar `_`/`%` do prefixo virarem wildcard de LIKE."""
    with Store(tmp_path / "m.db") as store:
        store.set_ui("nodecfg_a_x", "1")     # alvo
        store.set_ui("nodecfgXaXx", "2")     # casaria se `_` fosse wildcard — NÃO pode sumir
        store.delete_ui_prefix("nodecfg_a_")
        assert store.get_ui("nodecfg_a_x") is None
        assert store.get_ui("nodecfgXaXx") == "2"
