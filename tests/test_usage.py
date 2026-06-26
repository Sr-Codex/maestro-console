"""Testes de uso de tokens/custo por agente (F1a) — sem GTK."""

from maestro.engine.state.store import Store
from maestro.engine.usage import (
    AgentUsage,
    UsageLedger,
    parse_claude_usage,
    parse_codex_cumulative,
)


def test_parse_claude_total_cost_usd():
    s = '{"result":"ok","total_cost_usd":0.012,"usage":{"input_tokens":1200,"output_tokens":340}}'
    u = parse_claude_usage(s)
    assert u == AgentUsage(1200, 340, 0.012)


def test_parse_claude_cost_obj_variante():
    s = '{"result":"x","cost":{"input_tokens":10,"output_tokens":5,"total_cost":0.001}}'
    u = parse_claude_usage(s)
    assert u == AgentUsage(10, 5, 0.001)


def test_parse_claude_sem_uso_eh_none():
    assert parse_claude_usage('{"result":"x"}') is None
    assert parse_claude_usage("não é json") is None


def test_parse_codex_pega_maior_cumulativo():
    nd = "\n".join(
        [
            '{"type":"token_count","usage":{"input_tokens":100,"output_tokens":20}}',
            '{"type":"other"}',
            '{"type":"token_count","usage":{"input_tokens":300,"output_tokens":80}}',
        ]
    )
    assert parse_codex_cumulative(nd) == AgentUsage(300, 80, 0.0)


def test_agentusage_soma():
    assert AgentUsage(10, 5, 0.01) + AgentUsage(2, 3, 0.02) == AgentUsage(12, 8, 0.03)


def test_ledger_acumula_e_persiste(tmp_path):
    with Store(tmp_path / "m.db") as s:
        led = UsageLedger(s)
        assert led.get("claude") == AgentUsage()  # zero inicial
        led.add("claude", AgentUsage(100, 50, 0.01))
        led.add("claude", AgentUsage(20, 10, 0.002))
        assert led.get("claude") == AgentUsage(120, 60, 0.012)
    # persiste entre instâncias
    with Store(tmp_path / "m.db") as s2:
        assert UsageLedger(s2).get("claude") == AgentUsage(120, 60, 0.012)
