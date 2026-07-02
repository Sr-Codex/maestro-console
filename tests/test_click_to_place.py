"""Testes do modo "clique pra posicionar" — o HUMANO escolhe onde o item nasce (clica
no canvas), em vez de um algoritmo tentar adivinhar uma posição livre. Decisão tomada
depois que a correção automática de sobreposição (`_next_node_default`/
`_free_region_origin`) se mostrou frágil na prática (ver docs/CHANGELOG): mais simples
e sempre certo deixar o humano apontar. O algoritmo automático continua valendo só
pros fluxos sem clique humano possível (recrutar por agente, montar equipe)."""

from types import SimpleNamespace

import pytest

pytest.importorskip("gi")  # canvas usa PyGObject; o .venv é gi-free → roda no python do sistema
# ordem intencional (não alfabética): importar canvas primeiro fixa gi.require_version("Gtk",...)
# antes do `from gi.repository import Gtk` abaixo, evitando o PyGIWarning de versão não fixada.
from maestro.native.canvas import CanvasWindow  # noqa: E402, I001
from gi.repository import Gtk  # noqa: E402, I001


def _make_win():
    w = CanvasWindow.__new__(CanvasWindow)  # sem __init__ → não cria GTK
    w._placing_spec = None
    w._placing_cursor = None
    w.plane = SimpleNamespace(queue_draw=lambda: None)
    return w


def test_start_placing_seta_o_spec_e_zera_cursor():
    w = _make_win()
    CanvasWindow._start_placing(w, {"kind": "shell"})
    assert w._placing_spec == {"kind": "shell"}
    assert w._placing_cursor is None


def test_cancel_placing_limpa_estado():
    w = _make_win()
    w._placing_spec = {"kind": "shell"}
    w._placing_cursor = (10.0, 20.0)
    CanvasWindow._cancel_placing(w)
    assert w._placing_spec is None
    assert w._placing_cursor is None


def test_cancel_placing_sem_modo_ativo_nao_quebra():
    w = _make_win()
    CanvasWindow._cancel_placing(w)  # já é None -> no-op seguro
    assert w._placing_spec is None


def test_commit_placing_shell_usa_a_posicao_clicada():
    w = _make_win()
    w._placing_spec = {"kind": "shell"}
    w._placing_cursor = (5.0, 5.0)
    calls = []

    def fake_new_shell(default=None):
        calls.append(("shell", default))
        return "shell-1"

    w._new_shell_terminal = fake_new_shell
    CanvasWindow._commit_placing(w, 123.0, 456.0)
    assert calls == [("shell", (123.0, 456.0))]
    assert w._placing_spec is None  # modo encerra após criar
    assert w._placing_cursor is None


def test_commit_placing_agent_usa_a_posicao_clicada_e_o_agente_escolhido():
    w = _make_win()
    w._placing_spec = {"kind": "agent", "base": "claude"}
    calls = []

    def fake_new_agent(base, default=None):
        calls.append((base, default))
        return "claude-1"

    w._new_agent_terminal = fake_new_agent
    CanvasWindow._commit_placing(w, 10.0, 20.0)
    assert calls == [("claude", (10.0, 20.0))]


def test_commit_placing_note_usa_a_posicao_clicada():
    """Regra de arquitetura (AGENTS.md): todo elemento da cápsula principal nasce por
    clique-pra-posicionar, não só terminal/agente."""
    w = _make_win()
    w._placing_spec = {"kind": "note"}
    calls = []
    w._create_note = lambda default=None: calls.append(default)
    CanvasWindow._commit_placing(w, 30.0, 40.0)
    assert calls == [(30.0, 40.0)]


def test_commit_placing_group_usa_a_posicao_clicada():
    w = _make_win()
    w._placing_spec = {"kind": "group"}
    calls = []
    w._create_group = lambda default=None: calls.append(default)
    CanvasWindow._commit_placing(w, 50.0, 60.0)
    assert calls == [(50.0, 60.0)]


def test_commit_placing_filetree_usa_a_posicao_clicada():
    w = _make_win()
    w._placing_spec = {"kind": "filetree"}
    calls = []
    w._create_file_tree = lambda default=None: calls.append(default)
    CanvasWindow._commit_placing(w, 70.0, 80.0)
    assert calls == [(70.0, 80.0)]


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("shell", (420.0, 220.0)),
        ("agent", (420.0, 220.0)),
        ("note", (200.0, 110.0)),
        ("group", (600.0, 360.0)),
        ("filetree", (300.0, 360.0)),
    ],
)
def test_placing_size_por_tipo(kind, expected):
    w = _make_win()
    w._placing_spec = {"kind": kind}
    assert CanvasWindow._placing_size(w) == expected


def test_commit_placing_sem_spec_pendente_nao_cria_nada():
    w = _make_win()
    calls = []
    w._new_shell_terminal = lambda default=None: calls.append(default)
    CanvasWindow._commit_placing(w, 1.0, 2.0)
    assert calls == []


def test_pan_begin_intercepta_clique_no_modo_posicionar_e_converte_coords():
    """O clique de tela vira coordenada-BASE ((screen-cam)/zoom) antes de ir pro
    `_commit_placing` — e o gesto é CLAIMED, não cai no fluxo normal de seleção/pan."""
    w = _make_win()
    w._placing_spec = {"kind": "shell"}
    w._cam = (-100.0, -50.0)
    w.model = SimpleNamespace(zoom=lambda: 2.0)
    committed = []
    w._commit_placing = lambda bx, by: committed.append((bx, by))
    claimed = []
    gesture = SimpleNamespace(set_state=lambda st: claimed.append(st))

    CanvasWindow._pan_begin(w, gesture, 300.0, 250.0)

    # base = (tela - cam) / zoom = (300-(-100))/2, (250-(-50))/2 = (200.0, 150.0)
    assert committed == [(200.0, 150.0)]
    assert claimed == [Gtk.EventSequenceState.CLAIMED]


def test_draw_placing_preview_sem_modo_ativo_nao_desenha():
    w = _make_win()
    calls = []
    cr = SimpleNamespace(
        save=lambda: calls.append("save"), restore=lambda: calls.append("restore"),
        rectangle=lambda *a: calls.append("rect"), stroke=lambda: calls.append("stroke"),
        set_source_rgba=lambda *a: None, set_line_width=lambda *a: None,
        set_dash=lambda *a: None,
    )
    CanvasWindow._draw_placing_preview_cr(w, cr, 1.0)
    assert calls == []  # nada desenhado sem placing ativo


def test_draw_placing_preview_desenha_retangulo_no_cursor():
    w = _make_win()
    w._placing_spec = {"kind": "shell"}
    w._placing_cursor = (100.0, 80.0)
    w._cam = (0.0, 0.0)
    calls = []
    cr = SimpleNamespace(
        save=lambda: calls.append("save"), restore=lambda: calls.append("restore"),
        rectangle=lambda *a: calls.append(("rect", a)), stroke=lambda: calls.append("stroke"),
        set_source_rgba=lambda *a: None, set_line_width=lambda *a: None,
        set_dash=lambda *a: None,
    )
    CanvasWindow._draw_placing_preview_cr(w, cr, 1.0)
    assert "save" in calls and "stroke" in calls
    rect_call = next(c for c in calls if isinstance(c, tuple) and c[0] == "rect")
    assert rect_call[1][:2] == (100.0, 80.0)  # x,y no cursor (cam=0)
