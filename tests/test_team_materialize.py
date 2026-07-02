"""Testes do materializador de Team Templates (Fase A, docs/14 §5.A2/§5.A4).

Mocka só fronteiras reais (criação de widget/subprocess via `_new_agent_terminal`,
`_apply_node_role`, `_respawn_node`, GTK draw/resize) — a lógica de grupos/geometria
(`_group_members`, `_autofit_group`, `_persist_group`) roda REAL sobre um `Groups`
de verdade (Store SQLite em tmp_path), pra pegar de fato o insight geométrico do
docs/14 §4 (pertinência ao grupo é por sobreposição, não "add_member").
"""

import json
import threading
from types import SimpleNamespace

import pytest

pytest.importorskip("gi")  # canvas usa PyGObject; o .venv é gi-free → roda no python do sistema
from maestro.engine.ask_bus import AskRequest
from maestro.engine.groups import Groups
from maestro.engine.state.store import Store
from maestro.engine.team_templates import GroupSpec, TeamTemplate
from maestro.engine.teams import Role
from maestro.engine.workspace import Workspace
from maestro.native.canvas import (  # noqa: E402
    BASE_H,
    BASE_W,
    GROUP_PAD,
    GROUP_TITLE_H,
    CanvasWindow,
)


class _FakeModel:
    def __init__(self):
        self.cfg = {}
        self.positions = {}
        self.sizes = {}

    def node_cfg(self, nid, key, default=""):
        return self.cfg.get((nid, key), default)

    def set_node_cfg(self, nid, key, val):
        self.cfg[(nid, key)] = val

    def position(self, nid, default):
        return self.positions.get(nid, default)

    def set_position(self, nid, x, y):
        self.positions[nid] = (x, y)

    def node_size(self, nid, default):
        return self.sizes.get(nid, default)

    def set_node_size(self, nid, w, h):
        self.sizes[nid] = (w, h)

    def zoom(self):
        return 1.0

    def node_name(self, nid, default):
        return default

    def node_roster(self):
        return []


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
    w._ask_bus_dir = str(tmp_path / "home" / "bus")
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
    w._cam = (0.0, 0.0)
    w.scrolled = SimpleNamespace(get_width=lambda: 1280, get_height=lambda: 720)
    w.plane = SimpleNamespace(queue_draw=lambda: None)
    w._agent_nids = set()
    w._recruited_by = {}
    w._sock_server = None
    w._last_recruit_error = ""
    w._mutate_log = {}
    _tick = [0.0]

    def _clock():  # avança muito por chamada -> rate-limit não trip por acidente nos testes
        _tick[0] += 1000.0
        return _tick[0]

    w._maestro_clock = _clock

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
        # espelha o `_new_agent_terminal` real: cria o workspace isolado ANTES de devolver o
        # nid — `_apply_role_spec` (real, não mockado) escreve o bloco de role nele.
        Workspace(str(tmp_path / "home" / "workspaces")).create(nid)
        return nid

    w._new_agent_terminal = fake_new_agent
    w._apply_node_color = lambda nid, hexc: None  # fronteira (CSS/GTK) — mock OK
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


def test_free_region_origin_canvas_vazio_comeca_na_viewport(tmp_path):
    """Canvas vazio começa no topo-esquerdo da VIEWPORT atual (câmera em (0,0) na
    fixture) — não num canto absoluto arbitrário do canvas infinito."""
    w, _created = _make_win(tmp_path)
    assert CanvasWindow._free_region_origin(w) == (0.0, GROUP_PAD * 2)


def test_free_region_origin_evita_conteudo_visivel(tmp_path):
    w, _created = _make_win(tmp_path)
    w._base_pos["existing-node"] = (100.0, 100.0)
    w._node_size["existing-node"] = (400.0, 300.0)  # ocupa até y=400, dentro da viewport
    w._group_base["g1"] = (0.0, 500.0)
    w._group_size["g1"] = (600.0, 50.0)  # ocupa até y=550, ainda dentro da viewport (0-720)
    ox, oy = CanvasWindow._free_region_origin(w)
    assert oy == 550.0 + GROUP_PAD * 2  # abaixo do que está VISÍVEL
    assert ox == 0.0  # alinhado ao mais à esquerda visível


def test_free_region_origin_ignora_conteudo_fora_da_vista(tmp_path):
    """Regressão ao vivo: "está aparecendo muito longe da vista" — conteúdo espalhado
    longe (fora da viewport atual) NÃO pode empurrar o item novo pra longe da câmera."""
    w, _created = _make_win(tmp_path)
    w._base_pos["longe"] = (5000.0, 5000.0)  # bem fora da viewport (0,0)-(1280,720)
    w._node_size["longe"] = (BASE_W, BASE_H)
    ox, oy = CanvasWindow._free_region_origin(w)
    assert oy < 1000.0  # continua perto da câmera, não em y~5000+
    assert ox < 1000.0


def test_materialize_nao_sobrepoe_conteudo_existente(tmp_path):
    """Regressão ao vivo: grupos/agentes novos nasciam em cima de cards já presentes no
    canvas (a cascata modular de `_next_node_default` repete depois de 6 itens)."""
    w, _created = _make_win(tmp_path)
    w._base_pos["existing"] = (0.0, 0.0)
    w._node_size["existing"] = (BASE_W, BASE_H)  # ocupa (0,0)-(420,220)
    spec = _template([["coder"]])
    CanvasWindow._materialize_team(w, spec)
    gid = w.groups.list()[0].id
    _gx, gy = w._group_base[gid]
    assert gy >= 220  # nasce ABAIXO do card existente, não em cima


def test_materialize_forca_posicao_mesmo_com_posicao_persistida_orfa(tmp_path):
    """Regressão ao vivo: o grupo nascia num lugar e os nós-terminal em outro — porque
    `model.position()` prefere uma posição PERSISTIDA antiga (id reciclado/órfão) em vez
    da posição calculada pelo materializador."""
    w, created = _make_win(tmp_path)
    w.model.positions["claude-1"] = (9999.0, 9999.0)  # posição "órfã" simulada
    spec = _template([["coder"]])
    result = CanvasWindow._materialize_team(w, spec)
    assert result["ok"]
    nid = created[0][0]
    assert nid == "claude-1"
    assert w._base_pos[nid] != (9999.0, 9999.0)
    assert w.model.positions[nid] == w._base_pos[nid]  # persistido foi sobrescrito


def test_materialize_forca_tamanho_mesmo_com_tamanho_persistido_orfao(tmp_path):
    """Regressão ao vivo (achado real na sessão): um id reciclado/órfão pode ter um
    TAMANHO persistido de um resize manual anterior, bem maior que o nominal
    (`BASE_W`×`BASE_H`) — o card nascia gigante, estourando o grid e sobrepondo os
    vizinhos dentro do mesmo grupo. `_force_node_rect` precisa sobrescrever o tamanho,
    não só a posição."""
    w, created = _make_win(tmp_path)
    w.model.sizes["claude-1"] = (999.0, 999.0)  # tamanho "órfão" simulado (resize antigo)
    spec = _template([["coder", "reviewer", "qe"]])  # 3 lado a lado no grid
    result = CanvasWindow._materialize_team(w, spec)
    assert result["ok"]
    nid = created[0][0]
    assert nid == "claude-1"
    card = (CanvasWindow.MAESTRO_TEAM_CARD_W, CanvasWindow.MAESTRO_TEAM_CARD_H)
    assert w._node_size[nid] == card
    assert w.model.sizes[nid] == card  # persistido foi sobrescrito
    # com o tamanho forçado, os 3 cards do grid não se tocam (col a col)
    positions = [w._base_pos[n] for n, _d in created]
    xs = sorted(p[0] for p in positions)
    assert xs[1] - xs[0] >= card[0]  # espaço horizontal >= a largura real do card
    assert xs[2] - xs[1] >= card[0]


def test_materialize_escreve_instrucao_real_no_workspace_nao_so_o_nome(tmp_path):
    """Regressão: `_apply_node_role` resolve o papel pelo NOME (`node_cfg`) contra a
    biblioteca e, sem entrada lá, usaria o NOME como instrução — perdendo o texto real
    (com placeholder já interpolado) do `AgentSpec`. `_materialize_team` precisa escrever
    via `_apply_role_spec(nid, member)` direto, preservando a instrução completa."""
    w, created = _make_win(tmp_path)
    rich_instruction = "Arquiteto do projeto n8n. Decide desenho técnico; result objetivo."
    spec = TeamTemplate(
        name="t",
        groups=[GroupSpec(name="G", members=[Role("arquiteto", "claude", rich_instruction)])],
    )
    result = CanvasWindow._materialize_team(w, spec)
    assert result["ok"]
    nid = created[0][0]
    ws = Workspace(str(tmp_path / "home" / "workspaces")).path(nid)
    agents_md = (ws / "AGENTS.md").read_text(encoding="utf-8")
    assert rich_instruction in agents_md
    # a armadilha do bug original: escrever só o NOME como se fosse a instrução
    assert "Seu papel: arquiteto\n\narquiteto\n" not in agents_md


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


def test_materialize_usa_origin_explicito_em_vez_de_free_region_origin(tmp_path):
    """Clique-pra-posicionar (AGENTS.md § Cápsulas de UI, item 5): quando `origin` é dado
    (posição clicada pelo humano), `_materialize_team` NÃO chama `_free_region_origin` —
    usa exatamente o que foi passado."""
    w, created = _make_win(tmp_path)
    w._free_region_origin = lambda: (9999.0, 9999.0)  # se for chamado, o teste falha
    spec = _template([["coder"]])
    result = CanvasWindow._materialize_team(w, spec, origin=(500.0, 300.0))
    assert result["ok"]
    gid = w.groups.list()[0].id
    assert w._group_base[gid] == pytest.approx((500.0, 300.0))
    nid = created[0][0]
    px, py = w._base_pos[nid]
    assert px == pytest.approx(500.0 + GROUP_PAD)  # dentro do grupo, ancorado no origin dado
    assert py == pytest.approx(300.0 + GROUP_PAD + GROUP_TITLE_H)


def test_materialize_sem_origin_usa_free_region_origin(tmp_path):
    """Regressão: sem `origin` (ex.: Fase B, sem clique humano), continua caindo no
    cálculo automático de área livre — comportamento anterior inalterado."""
    w, created = _make_win(tmp_path)
    calls = []
    real = CanvasWindow._free_region_origin

    def spy():
        calls.append(1)
        return real(w)

    w._free_region_origin = spy
    result = CanvasWindow._materialize_team(w, _template([["coder"]]))
    assert result["ok"]
    assert calls == [1]


def test_team_group_footprint_calcula_grid():
    w = CanvasWindow.__new__(CanvasWindow)
    group = GroupSpec(name="G", members=[
        Role("a", "claude", "x"), Role("b", "claude", "x"), Role("c", "claude", "x"),
        Role("d", "claude", "x"),
    ])
    gw, gh, cols, rows = CanvasWindow._team_group_footprint(w, group)
    assert cols == 3  # teto de 3 colunas
    assert rows == 2  # 4 membros / 3 colunas -> 2 linhas
    assert gw > 0 and gh > 0


def test_team_layout_size_soma_grupos_lado_a_lado():
    w = CanvasWindow.__new__(CanvasWindow)
    spec = TeamTemplate(name="t", groups=[
        GroupSpec(name="G1", members=[Role("a", "claude", "x")]),
        GroupSpec(name="G2", members=[Role("b", "claude", "x"), Role("c", "claude", "x")]),
    ])
    tw, th = CanvasWindow._team_layout_size(w, spec)
    g1w, g1h, _c1, _r1 = CanvasWindow._team_group_footprint(w, spec.groups[0])
    g2w, g2h, _c2, _r2 = CanvasWindow._team_group_footprint(w, spec.groups[1])
    assert tw == g1w + GROUP_PAD * 2 + g2w  # 2 grupos lado a lado + 1 gap entre eles
    assert th == max(g1h, g2h)


def test_materialize_grupo_com_leader_lider_conecta_no_manager_outros_no_lider(tmp_path):
    """Fase D (docs/14 §12): grupo com líder vira caixa-preta — só o líder conecta pra
    fora (orquestrador); os demais membros conectam no líder, não no orquestrador."""
    w, created = _make_win(tmp_path)
    spec = TeamTemplate(name="t", groups=[GroupSpec(
        name="G", leader="coder",
        members=[
            Role("coder", "claude", "implemente"),
            Role("reviewer", "codex", "revise"),
            Role("qe", "codex", "teste"),
        ],
    )])
    result = CanvasWindow._materialize_team(w, spec, manager="mgr")
    assert result["ok"]
    nid_by_role = {w.model.node_cfg(nid, "role"): nid for nid, _d in created}
    leader_nid = nid_by_role["coder"]
    assert w._recruited_by[leader_nid] == "mgr"
    assert ("mgr", leader_nid) in w.edges.list()
    for role in ("reviewer", "qe"):
        nid = nid_by_role[role]
        # fiação: conecta no líder (visual) — mas AUTORIDADE continua com o manager, nunca
        # com o líder (fix 2026-07-02: líder não deve ganhar dismiss/reassign de graça).
        assert w._recruited_by[nid] == "mgr"
        assert (leader_nid, nid) in w.edges.list()
        assert ("mgr", nid) not in w.edges.list()  # NÃO conecta direto no orquestrador


def test_materialize_grupo_com_leader_sem_manager_lider_fica_solto_como_t1(tmp_path):
    """Sem orquestrador (FAB/humano): o líder não conecta em ninguém externo — ele É o
    T1 do grupo; os outros membros ainda conectam nele (fiação), mas ninguém tem
    autoridade de comando sobre ninguém (igual T1 humano, sem manager de verdade)."""
    w, created = _make_win(tmp_path)
    spec = TeamTemplate(name="t", groups=[GroupSpec(
        name="G", leader="coder",
        members=[Role("coder", "claude", "implemente"), Role("reviewer", "codex", "revise")],
    )])
    result = CanvasWindow._materialize_team(w, spec)  # sem manager=
    assert result["ok"]
    nid_by_role = {w.model.node_cfg(nid, "role"): nid for nid, _d in created}
    leader_nid = nid_by_role["coder"]
    assert leader_nid not in w._recruited_by
    assert nid_by_role["reviewer"] not in w._recruited_by  # sem manager, sem autoridade rastreada
    assert (leader_nid, nid_by_role["reviewer"]) in w.edges.list()  # fiação continua correta


def test_materialize_grupo_com_leader_lider_nao_ganha_autoridade_sobre_colegas(tmp_path):
    """Regressão de segurança (achado por revisão adversarial pós-merge, 2026-07-02): o
    líder recebe o CABO dos colegas (fiação/UI), mas NÃO deve virar `_own_recruit` deles —
    senão ganharia dismiss/reassign sobre o próprio grupo de graça, poder que a Fase D
    (docs/14 §12) explicitamente disse que não daria."""
    w, created = _make_win(tmp_path)
    spec = TeamTemplate(name="t", groups=[GroupSpec(
        name="G", leader="coder",
        members=[Role("coder", "claude", "implemente"), Role("reviewer", "codex", "revise")],
    )])
    result = CanvasWindow._materialize_team(w, spec, manager="mgr")
    assert result["ok"]
    nid_by_role = {w.model.node_cfg(nid, "role"): nid for nid, _d in created}
    leader_nid = nid_by_role["coder"]
    reviewer_nid = nid_by_role["reviewer"]
    assert CanvasWindow._own_recruit(w, leader_nid, reviewer_nid) is False
    assert CanvasWindow._own_recruit(w, "mgr", reviewer_nid) is True  # autoridade real: manager


def test_materialize_grupo_sem_leader_mantem_comportamento_anterior(tmp_path):
    """Regressão: grupo SEM líder continua com todo mundo conectando direto no
    orquestrador (comportamento de antes da Fase D, inalterado)."""
    w, created = _make_win(tmp_path)
    spec = _template([["coder", "reviewer"]])  # sem leader (GroupSpec.leader=None default)
    result = CanvasWindow._materialize_team(w, spec, manager="mgr")
    assert result["ok"]
    for nid, _d in created:
        assert w._recruited_by[nid] == "mgr"
        assert ("mgr", nid) in w.edges.list()


def test_materialize_sem_groups_recusa(tmp_path):
    w, created = _make_win(tmp_path)
    w.groups = None
    result = CanvasWindow._materialize_team(w, _template([["coder"]]))
    assert not result["ok"]
    assert "indisponíveis" in result["error"]
    assert created == []


# -- Fase B (docs/14 §6): comando `team` — NL desenha, humano confirma, materializa --

def _team_spec_json(name="t") -> str:
    groups = [{"name": "Grupo", "members": [
        {"name": "coder", "agent": "claude", "instruction": "implemente"},
        {"name": "reviewer", "agent": "codex", "instruction": "revise"},
    ]}]
    return json.dumps({"name": name, "groups": groups})


def _req(frm, cmd, args):
    return AskRequest("a" * 8, frm, "", "", cmd=cmd, args=args)


def test_hitl_team_exige_maestro_mode(tmp_path):
    w, created = _make_win(tmp_path)
    result, done = {}, threading.Event()
    CanvasWindow._hitl_team(w, _req("mgr", "team", [_team_spec_json()]), result, done)
    assert not result["ok"] and "Maestro" in result["error"]
    assert done.is_set()
    assert created == []


def test_hitl_team_rejeita_sem_args(tmp_path):
    w, _created = _make_win(tmp_path)
    w.model.set_node_cfg("mgr", "maestro", "1")
    result, done = {}, threading.Event()
    CanvasWindow._hitl_team(w, _req("mgr", "team", []), result, done)
    assert not result["ok"] and "uso: team" in result["error"]
    assert done.is_set()


def test_hitl_team_rejeita_json_invalido(tmp_path):
    w, _created = _make_win(tmp_path)
    w.model.set_node_cfg("mgr", "maestro", "1")
    result, done = {}, threading.Event()
    CanvasWindow._hitl_team(w, _req("mgr", "team", ["{ nao é json ]["]), result, done)
    assert not result["ok"] and "spec inválido" in result["error"]
    assert done.is_set()


def test_hitl_team_rejeita_json_que_nao_e_objeto(tmp_path):
    w, _created = _make_win(tmp_path)
    w.model.set_node_cfg("mgr", "maestro", "1")
    result, done = {}, threading.Event()
    CanvasWindow._hitl_team(w, _req("mgr", "team", ["[1, 2, 3]"]), result, done)
    assert not result["ok"] and "spec inválido" in result["error"]


def test_hitl_team_rejeita_spec_grande_demais(tmp_path):
    w, _created = _make_win(tmp_path)
    w.model.set_node_cfg("mgr", "maestro", "1")
    huge = "x" * 9000  # > ASK_MAX_PROMPT_BYTES (8192)
    result, done = {}, threading.Event()
    CanvasWindow._hitl_team(w, _req("mgr", "team", [huge]), result, done)
    assert not result["ok"] and "grande demais" in result["error"]
    assert done.is_set()


def test_hitl_team_valido_abre_confirmacao_sem_materializar(tmp_path):
    """`_hitl_team` com spec válido NÃO materializa direto — abre confirmação assíncrona
    (`done` não é setado até a decisão humana)."""
    w, created = _make_win(tmp_path)
    w.model.set_node_cfg("mgr", "maestro", "1")
    calls = []
    w._confirm_team_from_agent = lambda frm, spec, result, done: calls.append((frm, spec.name))
    result, done = {}, threading.Event()
    CanvasWindow._hitl_team(w, _req("mgr", "team", [_team_spec_json("dev-x")]), result, done)
    assert calls == [("mgr", "dev-x")]
    assert not done.is_set()
    assert created == []


def test_maestro_exec_roteia_team_sem_despachar_direto(tmp_path):
    w, created = _make_win(tmp_path)
    w.model.set_node_cfg("mgr", "maestro", "1")
    calls = []
    w._hitl_team = lambda req, result, done: calls.append(req.frm)  # não seta done
    req = _req("mgr", "team", [_team_spec_json()])
    result, done = {}, threading.Event()
    CanvasWindow._maestro_exec(w, req, result, done)
    assert calls == ["mgr"] and not done.is_set()
    assert created == []


def test_apply_team_decision_aprovar_materializa_com_manager_igual_ao_frm(tmp_path):
    w, created = _make_win(tmp_path)
    spec = TeamTemplate.from_dict(json.loads(_team_spec_json("dev-y")))
    result, done = {}, threading.Event()
    CanvasWindow._apply_team_decision(w, True, "mgr", spec, result, done)
    assert result["ok"]
    assert done.is_set()
    assert len(created) == 2
    for nid, _default in created:
        assert w._recruited_by[nid] == "mgr"
        assert ("mgr", nid) in w.edges.list()


def test_apply_team_decision_ignora_manager_do_json(tmp_path):
    """ADR-17/18: autoridade nunca vem de campo que o agente preenche — mesmo se o JSON
    tiver um `manager` apontando outro nó, quem liga o cabo é sempre o `frm` real (canal)."""
    w, created = _make_win(tmp_path)
    raw = json.loads(_team_spec_json("dev-z"))
    raw["manager"] = "outro-no-qualquer"
    spec = TeamTemplate.from_dict(raw)
    result, done = {}, threading.Event()
    CanvasWindow._apply_team_decision(w, True, "mgr-real", spec, result, done)
    nid = created[0][0]
    assert w._recruited_by[nid] == "mgr-real"
    assert "outro-no-qualquer" not in w._recruited_by.values()


def test_apply_team_decision_negar_nao_materializa_e_audita(tmp_path):
    w, created = _make_win(tmp_path)
    from maestro.engine.maestro_audit import read_events

    spec = TeamTemplate.from_dict(json.loads(_team_spec_json()))
    result, done = {}, threading.Event()
    CanvasWindow._apply_team_decision(w, False, "mgr", spec, result, done)
    assert not result["ok"] and "negad" in result["error"]
    assert done.is_set()
    assert created == []
    assert any(e["event"] == "team_denied" for e in read_events(w._ask_bus_dir))


def test_hitl_team_respeita_rate_limit(tmp_path):
    w, _created = _make_win(tmp_path)
    w.model.set_node_cfg("mgr", "maestro", "1")
    w._maestro_clock = lambda: 0.0  # trava o tempo -> todo comando cai na MESMA janela
    for _ in range(w.MAESTRO_SPAWN_RATE):
        assert w._mutate_rate_ok("mgr")
    result, done = {}, threading.Event()
    CanvasWindow._hitl_team(w, _req("mgr", "team", [_team_spec_json()]), result, done)
    assert not result["ok"] and "aguarde" in result["error"]
    assert done.is_set()
