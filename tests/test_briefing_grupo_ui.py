"""Briefing por grupo (docs/30) — lógica do canvas sem GTK real.

Roda no python do SISTEMA (o .venv é gi-free). Padrão test_maestro_mode:
CanvasWindow.__new__ + atributos mínimos; mocka só FRONTEIRA (onde fica o
workspace = _role_targets), nunca o método de domínio sob teste.
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("gi")  # canvas usa PyGObject; o .venv é gi-free → python do sistema
from maestro.native.canvas import BASE_H, BASE_W, CanvasWindow  # noqa: E402


class _FakeModel:
    def __init__(self):
        self.cfg = {}
        self.roster = []

    def node_cfg(self, nid, key, default=""):
        return self.cfg.get((nid, key), default)

    def set_node_cfg(self, nid, key, val):
        self.cfg[(nid, key)] = val

    def node_roster(self):
        return self.roster


class _FakeStore:
    def __init__(self):
        self.ui = {}

    def get_ui(self, key):
        return self.ui.get(key)

    def set_ui(self, key, value):
        self.ui[key] = value


def _win(tmp_path):
    w = CanvasWindow.__new__(CanvasWindow)  # sem __init__ → não cria GTK
    w.model = _FakeModel()
    w._store = _FakeStore()
    w.frames = {}
    w._group_base = {}
    w._group_size = {}
    w._node_size = {}
    # fronteira: onde fica o workspace do nó (dir real em tmp, criado sob demanda)
    def targets(nid):
        d = tmp_path / nid
        d.mkdir(exist_ok=True)
        return [str(d)]
    w._role_targets = targets
    return w


def _ws_text(tmp_path, nid):
    return (tmp_path / nid / "CLAUDE.md").read_text()


def test_group_at_point_menor_grupo_vence(tmp_path):
    w = _win(tmp_path)
    w._group_base = {"g-fora": (0.0, 0.0), "g-dentro": (100.0, 100.0)}
    w._group_size = {"g-fora": (1000.0, 800.0), "g-dentro": (300.0, 200.0)}
    assert CanvasWindow._group_at_point(w, 150.0, 150.0) == "g-dentro"  # aninhado: menor
    assert CanvasWindow._group_at_point(w, 900.0, 700.0) == "g-fora"
    assert CanvasWindow._group_at_point(w, 5000.0, 5000.0) == ""  # fora de tudo


def test_assign_birth_group_carimba_workspace(tmp_path):
    w = _win(tmp_path)
    CanvasWindow._set_group_brief(w, "g1", "migrar parser", "decisão: asyncio")
    CanvasWindow._assign_birth_group(w, "claude-2", "g1")
    assert w.model.node_cfg("claude-2", "birth_group") == "g1"
    t = _ws_text(tmp_path, "claude-2")
    assert "migrar parser" in t and "decisão: asyncio" in t


def test_set_group_brief_sanitiza_e_recarimba_membros(tmp_path):
    w = _win(tmp_path)
    CanvasWindow._assign_birth_group(w, "claude-2", "g1")  # membro ANTES do brief existir
    w.frames = {"claude-2": object()}
    CanvasWindow._set_group_brief(w, "g1", "meta\u200b nova", "corpo\u202eoculto")  # com invisíveis
    assert w._store.get_ui("group_goal_g1") == "meta nova"  # sanitizado no save
    assert w._store.get_ui("group_brief_g1") == "corpooculto"
    assert w._store.get_ui("group_brief_ts_g1")  # data registrada
    assert "meta nova" in _ws_text(tmp_path, "claude-2")  # membro re-carimbado NA HORA


def test_stamp_brief_sem_grupo_remove_bloco(tmp_path):
    w = _win(tmp_path)
    CanvasWindow._set_group_brief(w, "g1", "meta", "corpo")
    CanvasWindow._assign_birth_group(w, "claude-2", "g1")
    assert "maestro-brief" in _ws_text(tmp_path, "claude-2")
    CanvasWindow._assign_birth_group(w, "claude-2", "")  # saiu do grupo
    assert "maestro-brief" not in _ws_text(tmp_path, "claude-2")


def test_brief_members_roster_e_frames(tmp_path):
    w = _win(tmp_path)
    w.model.set_node_cfg("a1", "birth_group", "g1")
    w.model.set_node_cfg("a2", "birth_group", "g2")
    w.model.set_node_cfg("a3", "birth_group", "g1")
    w.model.roster = [{"nid": "a1"}, {"nid": "a2"}]  # a3 só nos frames (vivo, fora do roster)
    w.frames = {"a3": object()}
    assert sorted(CanvasWindow._brief_members(w, "g1")) == ["a1", "a3"]


def test_update_birth_group_on_drop_pelo_centro(tmp_path):
    w = _win(tmp_path)
    w._group_base = {"g1": (0.0, 0.0)}
    w._group_size = {"g1": (600.0, 360.0)}
    w._node_size = {"claude-2": (BASE_W, BASE_H)}
    CanvasWindow._set_group_brief(w, "g1", "meta", "")
    CanvasWindow._update_birth_group_on_drop(w, "claude-2", 10.0, 10.0)  # centro dentro
    assert w.model.node_cfg("claude-2", "birth_group") == "g1"
    CanvasWindow._update_birth_group_on_drop(w, "claude-2", 5000.0, 5000.0)  # arrastou pra fora
    assert w.model.node_cfg("claude-2", "birth_group") == ""
    assert "maestro-brief" not in _ws_text(tmp_path, "claude-2")


def test_close_group_limpa_chaves_membros_e_blocos(tmp_path):
    w = _win(tmp_path)
    w._selected = None
    w._select = lambda *_a: None
    w.groups = None
    w._group_color = {}
    w._group_title = {}
    w._group_manual = {}
    w._group_user_sized = set()
    w.plane = SimpleNamespace(queue_draw=lambda: None)
    w._mm_refresh = lambda: None
    CanvasWindow._set_group_brief(w, "g1", "meta", "corpo")
    CanvasWindow._assign_birth_group(w, "claude-2", "g1")
    w.frames = {"claude-2": object()}
    CanvasWindow._close_group(w, "g1")
    assert w.model.node_cfg("claude-2", "birth_group") == ""
    assert "maestro-brief" not in _ws_text(tmp_path, "claude-2")
    assert not w._store.get_ui("group_brief_g1")  # chaves zeradas (E7)
    assert not w._store.get_ui("group_brief_ts_g1")
