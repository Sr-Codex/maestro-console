"""Testes do budget cap (F1 Bloco D) — o "limitador". gi-free."""
import asyncio

from pytest import approx

from maestro.engine import budget
from maestro.engine.state.store import Store


def test_budget_verdict():
    assert budget.budget_verdict(1.0, 2.0, 5.0) == "ok"
    assert budget.budget_verdict(3.0, 2.0, 5.0) == "soft"  # >= soft, < hard
    assert budget.budget_verdict(5.0, 2.0, 5.0) == "hard"  # >= hard
    assert budget.budget_verdict(100.0, None, None) == "ok"  # sem teto = desligado
    assert budget.budget_verdict(100.0, 0, 0) == "ok"  # 0 = desligado


def test_budget_limits_soft_default_75pct(tmp_path):
    with Store(tmp_path / "m.db") as s:
        assert budget.budget_limits(s) == (None, None)  # sem hard = desligado
        s.set_ui("budget_hard", "8")
        assert budget.budget_limits(s) == (6.0, 8.0)  # soft vazio → 75% do hard
        s.set_ui("budget_soft", "2")
        assert budget.budget_limits(s) == (2.0, 8.0)


def test_record_spend_monotonico_soma_delta(tmp_path):
    with Store(tmp_path / "m.db") as s:
        budget.record_spend(s, "a", 0.10)   # sessão cresce
        budget.record_spend(s, "a", 0.30)   # +0.20
        assert budget.counted_spend(s) == approx(0.30)
        budget.record_spend(s, "b", 0.50)   # outro agente soma
        assert budget.counted_spend(s) == approx(0.80)


def test_record_spend_nao_baixa_com_rotacao_de_sessao(tmp_path):
    # LAUNDERING: rotacionar a sessão (total cai p/ 0) NÃO reduz o contado — banca o novo
    with Store(tmp_path / "m.db") as s:
        budget.record_spend(s, "a", 1.00)   # sessão 1: gastou 1.00
        budget.record_spend(s, "a", 0.05)   # sessão 2 (rotacionou): novo < último → banca 0.05
        assert budget.counted_spend(s) == approx(1.05)  # 1.00 velho FICA + 0.05 novo


def test_reset_budget_move_baseline(tmp_path):
    with Store(tmp_path / "m.db") as s:
        budget.record_spend(s, "a", 2.00)
        assert budget.counted_spend(s) == approx(2.00)
        budget.reset_budget(s)              # zera (baseline = total)
        assert budget.counted_spend(s) == approx(0.0)
        budget.record_spend(s, "a", 2.50)   # gasto NOVO conta a partir do reset
        assert budget.counted_spend(s) == approx(0.50)


def test_check_dispara_hard(tmp_path):
    with Store(tmp_path / "m.db") as s:
        s.set_ui("budget_hard", "1")
        budget.record_spend(s, "a", 0.90)
        assert budget.check(s) == "soft"    # 0.90 >= 0.75 (soft default)
        budget.record_spend(s, "a", 1.10)
        assert budget.check(s) == "hard"    # 1.10 >= 1.0


def test_delegate_barra_no_hard(tmp_path):
    # o gate REAL: delegate recusa o turno (BLOCKED) quando o budget estourou, SEM rodar o agente
    from maestro.engine.envelope import EnvelopeState
    from maestro.engine.orchestrator import Orchestrator

    with Store(tmp_path / "m.db") as s:
        s.set_ui("budget_hard", "1")
        budget.record_spend(s, "a", 2.00)  # já estourou

        rodou = []

        async def ask(agent_id, prompt):
            rodou.append(agent_id)  # NÃO deve ser chamado
            return "resp"

        orch = Orchestrator(ask, store=s)
        env = asyncio.run(orch.delegate("a", "faça algo"))
        assert env.state is EnvelopeState.BLOCKED
        # docs/29 §4.2: o texto é de PAUSA (retomável), nunca de falha/erro
        assert (env.note or "").startswith("pausado por budget")
        assert rodou == []  # o agente NÃO rodou (barrado antes)
