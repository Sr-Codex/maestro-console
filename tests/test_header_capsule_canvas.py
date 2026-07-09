"""Fase B — header do card: cápsula do agente (cor fixa) + chips SEPARADOS de custo/token, cada
um some quando vazio; RAM idem. Testa os métodos REAIS (só mocka os widgets Label — fronteira).
Guardado por `importorskip("gi")`: no `.venv` gi-free este arquivo é pulado (roda no py do sistema).
"""
import pytest

pytest.importorskip("gi")  # canvas importa gi

from types import SimpleNamespace  # noqa: E402

from maestro.native.canvas import CanvasWindow  # noqa: E402


class _Lbl:
    """Label fake que registra text/visible/classes (superset do que o header seta)."""

    def __init__(self):
        self.text = ""
        self.tip = None
        self.visible = True
        self.classes = set()

    def set_text(self, t):
        self.text = t

    def set_visible(self, v):
        self.visible = bool(v)

    def set_tooltip_text(self, t):
        self.tip = t

    def add_css_class(self, c):
        self.classes.add(c)

    def remove_css_class(self, c):
        self.classes.discard(c)


def _usage(cost=0.0, itok=0, otok=0):
    return SimpleNamespace(cost_usd=cost, input_tokens=itok, output_tokens=otok)


# ---- formatação dos chips (pura) ----
def test_fmt_money():
    assert CanvasWindow._fmt_money(_usage(cost=0.0)) == ""       # Codex sem preço → vazio
    assert CanvasWindow._fmt_money(_usage(cost=0.42)) == "$0.42"


def test_fmt_tokens():
    assert CanvasWindow._fmt_tokens(_usage()) == ""
    assert CanvasWindow._fmt_tokens(_usage(itok=800, otok=40)) == "840 tok"
    assert CanvasWindow._fmt_tokens(_usage(itok=8000, otok=4200)) == "12.2k tok"


# ---- custo e token como chips SEPARADOS, cada um some quando vazio ----
def test_refresh_node_cost_chips_separados_e_visibilidade():
    w = CanvasWindow.__new__(CanvasWindow)
    cost, tok = _Lbl(), _Lbl()
    w.heads = {"n1": SimpleNamespace(_cost=cost, _tok=tok)}

    def _ctrl(u):
        return SimpleNamespace(usage_ledger=SimpleNamespace(get=lambda _nid: u))

    # Claude (com preço): mostra custo E token
    w.controller = _ctrl(_usage(cost=0.42, itok=8000, otok=4200))
    w._refresh_node_cost("n1")
    assert (cost.text, cost.visible) == ("$0.42", True)
    assert (tok.text, tok.visible) == ("12.2k tok", True)

    # Codex (sem preço): chip de custo SOME, token fica
    w.controller = _ctrl(_usage(cost=0.0, itok=14000, otok=200))
    w._refresh_node_cost("n1")
    assert (cost.text, cost.visible) == ("", False)
    assert tok.visible is True

    # zerado: os dois somem (sem "losango fantasma")
    w.controller = _ctrl(_usage())
    w._refresh_node_cost("n1")
    assert cost.visible is False and tok.visible is False


# ---- cápsula do agente: nome do papel (cor fixa) / escondida sem role ----
def test_refresh_agent_cap_mostra_nome_e_esconde_sem_role():
    w = CanvasWindow.__new__(CanvasWindow)
    cap = _Lbl()
    w.heads = {"n1": SimpleNamespace(_agent=cap)}

    # role explícito → mostra o nome, visível
    w._refresh_agent_cap("n1", SimpleNamespace(name="revisor"))
    assert (cap.text, cap.visible) == ("revisor", True)

    # role de nome vazio → esconde
    w._refresh_agent_cap("n1", SimpleNamespace(name="   "))
    assert cap.visible is False

    # sem role (resolve por _node_role=None) → esconde
    w._node_role = lambda _nid: None  # fronteira (lê node_cfg); aqui só o None importa
    w._refresh_agent_cap("n1")
    assert cap.text == "" and cap.visible is False


def test_refresh_agent_cap_sem_heads_nao_estoura():
    """Fase B: chamada durante team materialize numa janela sem `heads` não pode estourar."""
    w = CanvasWindow.__new__(CanvasWindow)  # sem atributo `heads`
    w._refresh_agent_cap("n1", SimpleNamespace(name="x"))  # não levanta


# ---- RAM: chip some quando vazio ----
def test_set_ram_label_esconde_quando_vazio():
    w = CanvasWindow.__new__(CanvasWindow)
    ram = _Lbl()
    w.heads = {"n1": SimpleNamespace(_ram=ram)}
    w._set_ram_label("n1", "312 MB", high=False)
    assert ram.visible is True and ram.text == "312 MB"
    w._set_ram_label("n1", "", high=False)   # medição vazia → some
    assert ram.visible is False
