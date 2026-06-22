"""Testes do handoff mediado por cabo (V7-S3) — sem GTK."""

import asyncio
import threading

from maestro.engine.envelope import Envelope, EnvelopeState
from maestro.native.orchestrate import run_edge_handoff, run_edge_handoff_in_thread


def _env(sender, state, result=None, note=None):
    return Envelope(
        sender=sender,
        recipient="orchestrator",
        message_id=f"m-{sender}",
        state=state,
        result=result,
        note=note,
    )


class _FakeController:
    """delegate(agent_id, task) async, devolvendo o envelope pré-configurado."""

    def __init__(self, envs):
        self._envs = envs
        self.calls = []  # [(agent_id, task)]

    async def delegate(self, agent_id, task):
        self.calls.append((agent_id, task))
        return self._envs[agent_id]


def test_a_done_passa_result_para_b():
    ctrl = _FakeController(
        {
            "A": _env("A", EnvelopeState.DONE, result="saida-de-A"),
            "B": _env("B", EnvelopeState.DONE, result="ok"),
        }
    )
    res = asyncio.run(run_edge_handoff(ctrl, "A", "B", "faça X"))
    assert res.ok and not res.escalated
    # A recebeu a intenção; B recebeu o RESULT de A
    assert ctrl.calls == [("A", "faça X"), ("B", "saida-de-A")]


def test_a_nao_done_escala_sem_chamar_b():
    ctrl = _FakeController(
        {
            "A": _env("A", EnvelopeState.BLOCKED, note="preciso de input"),
            "B": _env("B", EnvelopeState.DONE, result="ok"),
        }
    )
    res = asyncio.run(run_edge_handoff(ctrl, "A", "B", "faça X"))
    assert res.escalated and res.dst is None
    assert [c[0] for c in ctrl.calls] == ["A"]  # B nunca chamado
    assert "BLOCKED" in res.reason


def test_b_falha_escala_mas_b_foi_chamado():
    ctrl = _FakeController(
        {
            "A": _env("A", EnvelopeState.DONE, result="r"),
            "B": _env("B", EnvelopeState.FAILED, note="boom"),
        }
    )
    res = asyncio.run(run_edge_handoff(ctrl, "A", "B", "faça X"))
    assert res.escalated and res.dst is not None
    assert [c[0] for c in ctrl.calls] == ["A", "B"]
    assert "FAILED" in res.reason


def test_emite_stepprogress_em_ordem():
    ctrl = _FakeController(
        {
            "A": _env("A", EnvelopeState.DONE, result="r"),
            "B": _env("B", EnvelopeState.DONE, result="ok"),
        }
    )
    seen = []
    asyncio.run(
        run_edge_handoff(
            ctrl, "A", "B", "x", on_step=lambda sp: seen.append((sp.agent, sp.phase, sp.state))
        )
    )
    assert seen == [
        ("A", "start", None),
        ("A", "done", "DONE"),
        ("B", "start", None),
        ("B", "done", "DONE"),
    ]


def test_result_none_vira_string_vazia():
    # A DONE mas sem result -> B recebe "" (não None)
    ctrl = _FakeController(
        {
            "A": _env("A", EnvelopeState.DONE, result=None),
            "B": _env("B", EnvelopeState.DONE, result="ok"),
        }
    )
    asyncio.run(run_edge_handoff(ctrl, "A", "B", "x"))
    assert ctrl.calls[1] == ("B", "")


def test_in_thread_executa_e_chama_on_step():
    ctrl = _FakeController(
        {
            "A": _env("A", EnvelopeState.DONE, result="r"),
            "B": _env("B", EnvelopeState.DONE, result="ok"),
        }
    )
    done = threading.Event()
    seen = []

    def on_step(sp):
        seen.append((sp.agent, sp.phase))
        if sp.agent == "B" and sp.phase == "done":
            done.set()

    t = run_edge_handoff_in_thread(ctrl, "A", "B", "x", on_step)
    assert isinstance(t, threading.Thread)
    assert done.wait(timeout=5.0)
    t.join(timeout=5.0)
    assert ("A", "start") in seen and ("B", "done") in seen
