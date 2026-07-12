"""Pausa graciosa + retomada do budget cap (docs/29) — gi-free.

Cobre o DoD §8: gate loga o BLOCKED no envelope_log; chain barrada por budget escala
TIPADA (`escalated_budget`, distinta da escalada por erro); `resume_chain` re-roda o
passo barrado; re-estouro no meio re-escala sem loop; `is_paused` é derivado; floor
run faz fail-fast sem rodar o agente; `resume_run` retoma por run_id (sem depender
do contexto em memória — sobrevive a reabrir o app).
"""
import asyncio
import json

from maestro.engine import budget
from maestro.engine.orchestrator import Orchestrator, is_budget_blocked
from maestro.engine.state.store import Store
from maestro.engine.teams import Role, Team


def _env(state="DONE", result="ok"):
    return json.dumps({"state": state, "result": result})


def _estoura(s, hard="1"):
    s.set_ui("budget_hard", hard)
    budget.record_spend(s, "a", 2.00)


def _team():
    return Team("t", [Role("coder", "a", "faça"), Role("reviewer", "b", "revise")])


def test_is_paused_derivado(tmp_path):
    # docs/29 §4.2 (E10): pausado NÃO é flag — deriva do veredito; liberar despausa sozinho
    with Store(tmp_path / "m.db") as s:
        assert budget.is_paused(s) is False  # sem teto
        _estoura(s)
        assert budget.is_paused(s) is True
        s.set_ui("budget_hard", "10")        # subiu o teto → despausa (sem tocar em flag)
        assert budget.is_paused(s) is False
        s.set_ui("budget_hard", "1")
        budget.reset_budget(s)               # zerar também despausa
        assert budget.is_paused(s) is False


def test_gate_loga_blocked_no_envelope_log(tmp_path):
    # docs/29 §4.1: a barrada deixa de ser invisível — entra no envelope_log
    with Store(tmp_path / "m.db") as s:
        _estoura(s)

        async def ask(agent_id, prompt):
            raise AssertionError("não deve rodar")

        env = asyncio.run(Orchestrator(ask, store=s).delegate("a", "t"))
        assert is_budget_blocked(env)
        logged = s.list_envelopes(limit=5)
        assert len(logged) == 1 and logged[0]["state"] == "BLOCKED"
        assert "pausado por budget" in logged[0]["payload"]


def test_gate_emite_sinal_on_budget_block(tmp_path):
    # docs/29 §4.3 (E4): o gate barra ANTES de rodar → on_usage nunca dispara; o sinal
    # dedicado é o canal engine→UI da pausa
    with Store(tmp_path / "m.db") as s:
        _estoura(s)
        sinais = []

        async def ask(agent_id, prompt):
            raise AssertionError("não deve rodar")

        orch = Orchestrator(ask, store=s, on_budget_block=sinais.append)
        asyncio.run(orch.delegate("a", "t"))
        assert sinais == ["a"]


def test_chain_barrada_escala_escalated_budget(tmp_path):
    # docs/29 §4.1: escalada por budget é TIPADA — a retomada sabe que é pausa, não erro
    with Store(tmp_path / "m.db") as s:
        _estoura(s)

        async def ask(agent_id, prompt):
            raise AssertionError("não deve rodar")

        res = asyncio.run(Orchestrator(ask, store=s).run_team(_team(), "faça x", task_id="r1"))
        assert res.escalated
        assert s.get_chain("r1")["status"] == "escalated_budget"
        assert s.list_chains("escalated_budget")[0]["run_id"] == "r1"


def test_chain_erro_de_agente_segue_escalated_generico(tmp_path):
    # BLOCKED do PRÓPRIO agente (sem budget) não é pausa → status "escalated" de sempre
    with Store(tmp_path / "m.db") as s:
        async def ask(agent_id, prompt):
            return _env(state="BLOCKED", result=None)

        res = asyncio.run(Orchestrator(ask, store=s).run_team(_team(), "faça x", task_id="r1"))
        assert res.escalated
        assert s.get_chain("r1")["status"] == "escalated"
        assert s.list_chains("escalated_budget") == []


def test_resume_chain_re_roda_o_passo_barrado(tmp_path):
    # docs/29 §4.4: liberar o teto + resume_chain → re-roda o passo BLOCKED e conclui
    with Store(tmp_path / "m.db") as s:
        _estoura(s)
        rodou = []

        async def ask(agent_id, prompt):
            rodou.append(agent_id)
            return _env()

        orch = Orchestrator(ask, store=s)
        team = _team()
        asyncio.run(orch.run_team(team, "faça x", task_id="r1"))
        assert rodou == []  # tudo barrado
        budget.reset_budget(s)  # humano liberou
        res = asyncio.run(orch.resume_chain(team, "faça x", "r1"))
        assert res.ok
        assert rodou == ["a", "b"]  # re-rodou do passo barrado (nenhum DONE repetido)
        assert s.get_chain("r1")["status"] == "done"


def test_resume_com_re_estouro_re_escala_sem_loop(tmp_path):
    # docs/29 §4.4: o teto novo estoura no meio da retomada → re-escala escalated_budget
    # preservando a posição (passo 0 DONE não repete na próxima retomada)
    with Store(tmp_path / "m.db") as s:
        _estoura(s)
        rodou = []

        async def ask(agent_id, prompt):
            rodou.append(agent_id)
            budget.record_spend(s, agent_id, 5.00)  # o passo gasta e re-estoura o teto
            return _env()

        orch = Orchestrator(ask, store=s)
        team = _team()
        asyncio.run(orch.run_team(team, "faça x", task_id="r1"))
        budget.reset_budget(s)
        s.set_ui("budget_hard", "1")  # teto apertado: o gasto do passo "a" re-estoura
        res = asyncio.run(orch.resume_chain(team, "faça x", "r1"))
        assert res.escalated and rodou == ["a"]  # "b" barrado pelo re-estouro
        assert s.get_chain("r1")["status"] == "escalated_budget"
        steps = s.get_steps("r1")
        assert steps[0]["state"] == "DONE"  # checkpoint preservado — sem loop, sem perder posição


def test_list_chains_filtra_por_status_mais_antiga_primeiro(tmp_path):
    with Store(tmp_path / "m.db") as s:
        s.start_chain("r1", "t", "i1")
        s.start_chain("r2", "t", "i2")
        s.set_chain_status("r1", "escalated_budget")
        s.set_chain_status("r2", "escalated_budget")
        held = s.list_chains("escalated_budget")
        assert [c["run_id"] for c in held] == ["r1", "r2"]  # updated_at crescente
        s.set_chain_status("r1", "discarded")
        assert [c["run_id"] for c in s.list_chains("escalated_budget")] == ["r2"]


def test_floor_run_fail_fast_no_hard(tmp_path):
    # docs/29 §5.2 (E3): floor run gastava FORA do freio; no hard → fail-fast com texto de
    # pausa, SEM rodar o agente (reter re-executaria fora do cwd do floor)
    from maestro.engine.floor_run import run_agent_in_floor
    from maestro.engine.floors import Floor

    with Store(tmp_path / "m.db") as s:
        _estoura(s)

        class SM:  # session_manager que NÃO pode ser chamado
            async def run_in_session(self, *a, **k):
                raise AssertionError("agente não deve rodar no hard")

        floor = Floor(name="f1", branch="floor/f1", path=str(tmp_path), base_branch="main")
        res = asyncio.run(run_agent_in_floor(
            SM(), object(), "a", "p", floor, tmp_path, timeout=1, store=s
        ))
        assert not res.ok
        assert "pausado por budget" in res.stderr


def test_controller_resume_run_por_run_id(tmp_path):
    # docs/29 §4.4: a retomada 1-clique do diálogo Limites retoma POR run_id — não depende
    # do _resume_ctx em memória (funciona depois de fechar/reabrir o app)
    from maestro.engine.registry import Registry
    from maestro.tui.controller import TUIController

    with Store(tmp_path / "m.db") as s:
        _estoura(s)
        rodou = []

        async def ask(agent_id, prompt):
            rodou.append(agent_id)
            return _env()

        orch = Orchestrator(ask, store=s)
        team = _team()
        asyncio.run(orch.run_team(team, "faça x", task_id="r1"))
        assert s.get_chain("r1")["status"] == "escalated_budget"
        budget.reset_budget(s)
        ctl = TUIController(Registry(s), s, orch)  # controller NOVO (como pós-reabrir)
        res = asyncio.run(ctl.resume_run(team, "faça x", "r1"))
        assert res.ok and rodou == ["a", "b"]
        assert s.get_chain("r1")["status"] == "done"
