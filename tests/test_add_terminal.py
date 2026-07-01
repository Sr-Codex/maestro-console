"""Testes da feature '➕ novo terminal' (instância de agente em runtime)."""

import pytest

from maestro.engine.registry import Registry
from maestro.engine.state.store import Store
from maestro.native.toolbar import action_menu_items
from maestro.tui.controller import TUIController


def _ctrl(tmp_path):
    store = Store(tmp_path / "m.db")
    c = TUIController(Registry(store), store, orchestrator=None)
    c.agents = {"claude": object()}  # como o bootstrap faz (id -> profile)
    return c, store


def test_add_agent_instance_registra_no_dict_e_no_registry(tmp_path):
    c, store = _ctrl(tmp_path)
    try:
        c.add_agent_instance("claude-2", "claude")
        assert "claude-2" in c.agents  # delegate/maestro-ask passam a resolver
        assert c.agents["claude-2"] is c.agents["claude"]  # mesma profile
        assert c._registry.get("claude-2") is not None  # registrado
    finally:
        store.close()


def test_add_agent_instance_base_desconhecido(tmp_path):
    c, store = _ctrl(tmp_path)
    try:
        with pytest.raises(ValueError):
            c.add_agent_instance("x-2", "inexistente")
    finally:
        store.close()


def test_add_agent_instance_id_duplicado(tmp_path):
    c, store = _ctrl(tmp_path)
    try:
        c.add_agent_instance("claude-2", "claude")
        with pytest.raises(ValueError):
            c.add_agent_instance("claude-2", "claude")  # já existe
    finally:
        store.close()


def test_remove_agent_instance_libera_o_id(tmp_path):
    """Ao dispensar/fechar, a instância sai do dict E do registry → o id pode ser reusado
    (fix do 'id já existe' no recruit quando sobrava um codex-N antigo só no controller)."""
    c, store = _ctrl(tmp_path)
    try:
        c.add_agent_instance("codex-3", "claude")
        c.remove_agent_instance("codex-3")
        assert "codex-3" not in c.agents
        assert c._registry.get("codex-3") is None
        c.add_agent_instance("codex-3", "claude")  # id liberado: re-registra sem erro
        assert "codex-3" in c.agents
        c.remove_agent_instance("nao-existe")  # idempotente: não levanta
    finally:
        store.close()


def test_toolbar_tem_novo_terminal():
    items = action_menu_items(
        has_controller=True,
        has_edges=False,
        has_notes=False,
        has_floors=False,
        has_routines=False,
    )
    assert ("➕ novo terminal", "newterm") in items
