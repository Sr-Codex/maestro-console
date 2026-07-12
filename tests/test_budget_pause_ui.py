"""Probes gi da pausa de budget (docs/29) — UI do canvas sem GTK real.

Roda no python do SISTEMA (o .venv é gi-free). Mesmo padrão do test_maestro_mode:
CanvasWindow.__new__ + atributos mínimos; mocka só fronteira (widget/notify), nunca
o método de domínio sob teste.
"""

import pytest

from maestro.engine import budget
from maestro.engine.state.store import Store

pytest.importorskip("gi")  # canvas usa PyGObject; o .venv é gi-free → python do sistema
from maestro.native import canvas as canvas_mod  # noqa: E402
from maestro.native.canvas import CanvasWindow, _age_text  # noqa: E402


def _estoura(s, hard="1"):
    s.set_ui("budget_hard", hard)
    budget.record_spend(s, "a", 2.00)


def _win(store):
    w = CanvasWindow.__new__(CanvasWindow)  # sem __init__ → não cria GTK
    w._store = store
    w._agent_nids = set()
    w._recruited_by = {}
    w.edges = None
    return w


class _FakeLabel:
    def __init__(self):
        self.text, self.classes, self.visible = "", set(), False

    def set_text(self, t):
        self.text = t

    def add_css_class(self, c):
        self.classes.add(c)

    def remove_css_class(self, c):
        self.classes.discard(c)

    def set_visible(self, v):
        self.visible = v


def test_age_text():
    import time

    now = time.time()
    assert _age_text(now - 10) == "agora"
    assert _age_text(now - 300) == "há 5min"
    assert _age_text(now - 7200) == "há 2h"
    assert _age_text(now - 200000) == "há 2d"
    assert _age_text(None) == "idade ?"


def test_ask_delegate_live_pula_pro_headless_no_hard(tmp_path):
    # docs/29 §5.1: no hard, o cabo em modo LIVE não injeta no VTE — cai no headless,
    # onde o gate uniforme do delegate barra (um BLOCKED só, mesmo texto)
    with Store(tmp_path / "m.db") as s:
        _estoura(s)
        w = _win(s)
        calls = []
        w._ask_live = lambda to, p: (calls.append("live") or "raspado")
        w._ask_headless = lambda to, p: (calls.append("headless") or "gate")
        w._ask_mode = "live"
        assert CanvasWindow._ask_delegate(w, "b", "oi") == "gate"
        assert calls == ["headless"]  # live PULADO
        budget.reset_budget(s)  # liberou → live volta a valer
        calls.clear()
        assert CanvasWindow._ask_delegate(w, "b", "oi") == "raspado"
        assert calls == ["live"]


def test_hud_mostra_pausado_e_retidas(tmp_path):
    # docs/29 §4.2: HUD vira "⏸ budget · $X/$Y · N retida(s)" (texto de pausa, classe hard)
    with Store(tmp_path / "m.db") as s:
        _estoura(s)
        s.start_chain("r1", "t", "i")
        s.set_chain_status("r1", "escalated_budget")
        w = _win(s)
        w._fleet_hud = _FakeLabel()
        CanvasWindow._refresh_fleet_hud(w)
        assert "⏸ budget" in w._fleet_hud.text and "1 retida" in w._fleet_hud.text
        assert "hud-hard" in w._fleet_hud.classes
        budget.reset_budget(s)  # liberou → volta ao segmento normal de gasto
        CanvasWindow._refresh_fleet_hud(w)
        assert "⏸" not in w._fleet_hud.text and "gasto $" in w._fleet_hud.text


def test_hard_notify_uma_vez_por_episodio_e_rearma(tmp_path, monkeypatch):
    # docs/29 §4.3: notificação com SOM na 1ª barrada; guard 1×; rearma ao liberar
    with Store(tmp_path / "m.db") as s:
        sent = []
        monkeypatch.setattr(canvas_mod, "notify",
                            lambda summary, body="", *, sound=True: sent.append(sound))
        w = _win(s)
        _estoura(s)
        CanvasWindow._budget_hard_notify(w)
        CanvasWindow._budget_hard_notify(w)  # mesmo episódio → não repete
        assert sent == [True]  # 1× e com som (pausa de fleet é o evento audível)
        budget.reset_budget(s)
        CanvasWindow._budget_hard_notify(w)  # liberou → rearma (sem notificar)
        assert sent == [True]
        budget.record_spend(s, "a", 9.00)  # novo episódio (gasto NOVO re-estoura o teto)
        CanvasWindow._budget_hard_notify(w)
        assert sent == [True, True]


def test_held_chains_lista_do_store(tmp_path):
    with Store(tmp_path / "m.db") as s:
        w = _win(s)
        assert CanvasWindow._budget_held_chains(w) == []
        s.start_chain("r1", "t", "i")
        s.set_chain_status("r1", "escalated_budget")
        assert [c["run_id"] for c in CanvasWindow._budget_held_chains(w)] == ["r1"]
        w._store = None  # sem store → lista vazia, nunca erro
        assert CanvasWindow._budget_held_chains(w) == []
