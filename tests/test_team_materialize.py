"""Testes do materializador de Team Templates (Fase A, docs/14 §5.A2/§5.A4).

Mocka só fronteiras reais (criação de widget/subprocess via `_new_agent_terminal`,
`_apply_node_role`, `_respawn_node`, GTK draw/resize) — a lógica de grupos/geometria
(`_group_members`, `_autofit_group`, `_persist_group`) roda REAL sobre um `Groups`
de verdade (Store SQLite em tmp_path), pra pegar de fato o insight geométrico do
docs/14 §4 (pertinência ao grupo é por sobreposição, não "add_member").
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("gi")  # canvas usa PyGObject; o .venv é gi-free → roda no python do sistema
from maestro.engine.groups import Groups
from maestro.engine.state.store import Store
from maestro.engine.team_templates import GroupSpec, TeamTemplate
from maestro.engine.teams import Role
from maestro.native.canvas import CanvasWindow  # noqa: E402


class _FakeModel:
    def __init__(self):
        self.cfg = {}

    def node_cfg(self, nid, key, default=""):
        return self.cfg.get((nid, key), default)

    def set_node_cfg(self, nid, key, val):
        self.cfg[(nid, key)] = val


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


def _make_win(tmp_path, fail_indices=frozenset()):
    w = CanvasWindow.__new__(CanvasWindow)  # sem __init__ → não cria GTK
    w.model = _FakeModel()
    w.controller = object()
    w._ask_bus_dir = str(tmp_path / "bus")
    w.edges = _FakeEdges()
    w.groups = Groups(Store(tmp_path / "m.db"))
    w.frames = {}
    w.note_frames = {}
    w._ft_frames = {}
    w._base_pos = {}
    w._note_base = {}
    w._ft_base = {}
    w._node_size = {}
    w.order = []
    w._group_manual = {}
    w._group_base = {}
    w._group_size = {}
    w._group_color = {}
    w._group_title = {}
    w._group_user_sized = set()
    w._group_excluded = set()
    w._loading = False
    w.plane = SimpleNamespace(queue_draw=lambda: None)
    w._agent_nids = set()
    w._recruited_by = {}
    w._sock_server = None
    w._last_recruit_error = ""

    created = []
    call_count = [0]

    def fake_new_agent(base, default=None):
        i = call_count[0]
        call_count[0] += 1
        if i in fail_indices:
            w._last_recruit_error = "spawn simulado falhou"
            return None
        nid = f"{base}-{i + 1}"
        created.append((nid, default))
        w._base_pos[nid] = tuple(default) if default else (0.0, 0.0)
        return nid

    w._new_agent_terminal = fake_new_agent
    w._apply_node_role = lambda nid: None  # fronteira (escreve arquivo/GTK) — mock OK
    w._respawn_node = lambda nid: None  # fronteira (subprocess/GTK) — mock OK
    w._resize_plane = lambda: None  # GTK
    w._refresh_fleet_hud = lambda: None  # GTK
    w._mm_refresh = lambda: None  # GTK
    return w, created


def _template(groups_members):
    """groups_members: lista de listas de nomes de papel, uma lista por grupo."""
    groups = []
    for gi, names in enumerate(groups_members):
        members = [Role(name, "claude", f"faça {name}") for name in names]
        groups.append(GroupSpec(name=f"Grupo{gi}", members=members))
    return TeamTemplate(name="t", groups=groups)


def test_materialize_cria_grupos_e_agentes_com_papel(tmp_path):
    w, created = _make_win(tmp_path)
    spec = _template([["coder", "reviewer"], ["qe"]])
    result = CanvasWindow._materialize_team(w, spec)
    assert result == {"ok": True, "groups": 2, "agents": 3, "warnings": [], "error": None}
    assert len(created) == 3
    roles = {w.model.node_cfg(nid, "role") for nid, _ in created}
    assert roles == {"coder", "reviewer", "qe"}
    assert len(w.groups.list()) == 2


def test_materialize_posiciona_membros_dentro_do_grupo_geometricamente(tmp_path):
    """Prova o insight crítico do docs/14 §4: pertinência ao grupo é por SOBREPOSIÇÃO
    (_group_members), não um add_member — os nós criados precisam cair de fato dentro
    do retângulo do grupo pra contarem como membros."""
    w, _created = _make_win(tmp_path)
    spec = _template([["coder", "reviewer", "qe"]])
    CanvasWindow._materialize_team(w, spec)
    gid = w.groups.list()[0].id
    members = CanvasWindow._group_members(w, gid)
    assert len(members) == 3


def test_materialize_recusa_fleet_cap_estourado_e_nao_cria_nada(tmp_path):
    w, created = _make_win(tmp_path)
    w._agent_nids = {f"x{i}" for i in range(11)}  # só cabe +1 (cap=12)
    spec = _template([["coder", "reviewer"]])  # precisa de 2
    result = CanvasWindow._materialize_team(w, spec)
    assert not result["ok"]
    assert "teto global" in result["error"]
    assert created == []  # guard-rail ANTES de criar nada
    assert w.groups.list() == []


def test_materialize_recusa_grupo_maior_que_8(tmp_path):
    w, created = _make_win(tmp_path)
    spec = _template([[f"m{i}" for i in range(9)]])
    result = CanvasWindow._materialize_team(w, spec)
    assert not result["ok"]
    assert "8 agentes" in result["error"]
    assert created == []


def test_materialize_avisa_grupo_acima_de_5_mas_nao_bloqueia(tmp_path):
    w, created = _make_win(tmp_path)
    spec = _template([[f"m{i}" for i in range(6)]])  # 6: > aviso(5), <= bloqueio(8)
    result = CanvasWindow._materialize_team(w, spec)
    assert result["ok"]
    assert len(created) == 6
    assert result["warnings"] and "3-4" in result["warnings"][0]


def test_materialize_rejeita_template_invalido(tmp_path):
    w, created = _make_win(tmp_path)
    result = CanvasWindow._materialize_team(w, TeamTemplate(name="", groups=[]))
    assert not result["ok"]
    assert created == []


def test_materialize_falha_parcial_continua_e_reporta(tmp_path):
    w, created = _make_win(tmp_path, fail_indices={1})  # o 2º spawn falha
    spec = _template([["coder", "reviewer", "qe"]])
    result = CanvasWindow._materialize_team(w, spec)
    assert result["ok"]  # sucesso parcial não vira falha da chamada toda
    assert result["agents"] == 2
    assert len(created) == 2
    roles = {w.model.node_cfg(nid, "role") for nid, _ in created}
    assert roles == {"coder", "qe"}  # reviewer falhou e foi pulado


def test_materialize_conecta_ao_manager_quando_fase_b(tmp_path):
    w, created = _make_win(tmp_path)
    spec = _template([["coder"]])
    result = CanvasWindow._materialize_team(w, spec, manager="mgr")
    assert result["ok"]
    nid = created[0][0]
    assert w._recruited_by[nid] == "mgr"
    assert ("mgr", nid) in w.edges.list()


def test_materialize_sem_groups_recusa(tmp_path):
    w, created = _make_win(tmp_path)
    w.groups = None
    result = CanvasWindow._materialize_team(w, _template([["coder"]]))
    assert not result["ok"]
    assert "indisponíveis" in result["error"]
    assert created == []
