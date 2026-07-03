"""Testes de uso de tokens/custo por agente (F1a) — sem GTK."""

from maestro.engine.state.store import Store
from maestro.engine.usage import (
    AgentUsage,
    UsageLedger,
    cost_from_tokens,
    model_price,
    parse_claude_usage,
    parse_codex_cumulative,
    parse_run_usage,
    with_cost,
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


# --- F1 Bloco A: preço vendorizado + custo a partir de tokens (Codex) ---

def test_model_price_exato_e_normalizado():
    # match exato
    p = model_price("gpt-5.5")
    assert p is not None and p["input"] == 5e-06 and p["output"] == 3e-05
    # normalização: sufixo de data e prefixo de região caem no modelo base
    assert model_price("gpt-5.5-2026-04-23") == p
    assert model_price("us.anthropic.claude-sonnet-5") == model_price("claude-sonnet-5")


def test_model_price_desconhecido_none():
    assert model_price("modelo-que-nao-existe-9000") is None
    assert model_price("") is None


def test_cost_from_tokens_codex():
    # gpt-5.5: input 5e-06, output 3e-05 → 1000*5e-06 + 500*3e-05 = 0.005 + 0.015 = 0.02
    assert cost_from_tokens(1000, 500, "gpt-5.5") == 0.02


def test_cost_from_tokens_desconhecido_none():
    # modelo sem preço → None (mostra tokens, marca 'sem preço', não chuta)
    assert cost_from_tokens(1000, 500, "modelo-fantasma") is None


def test_cost_from_tokens_cache_barato():
    # cache_read é ~10x mais barato que input base; separar os baldes reduz o custo
    caro = cost_from_tokens(1000, 0, "gpt-5.5")  # tudo input base
    barato = cost_from_tokens(1000, 0, "gpt-5.5", cache_read=900)  # 900 vieram de cache
    assert caro is not None and barato is not None and barato < caro


def test_with_cost_preenche_so_codex():
    # Codex (cost=0) → preenche pela tabela
    u = with_cost(AgentUsage(1000, 500, 0.0), "gpt-5.5")
    assert u.cost_usd == 0.02
    # Claude (já tem total_cost_usd) → inalterado
    claude = AgentUsage(1000, 500, 0.99)
    assert with_cost(claude, "claude-sonnet-5") == claude
    # modelo desconhecido → inalterado (não zera nem chuta)
    unk = AgentUsage(1000, 500, 0.0)
    assert with_cost(unk, "fantasma") == unk


# --- F1 Bloco B: dispatcher parse_run_usage (o que o run chama) ---

def test_parse_run_usage_claude_usa_total_cost():
    out = '{"model":"claude-sonnet-5","total_cost_usd":0.42,"usage":{"input_tokens":100,"output_tokens":50}}'
    u = parse_run_usage(out, "claude")
    assert u == AgentUsage(100, 50, 0.42)  # custo autoritativo do Claude


def test_parse_run_usage_codex_calcula_pela_tabela():
    # codex NDJSON com model gpt-5.5 → tokens viram custo pela tabela vendorizada
    nd = "\n".join([
        '{"type":"token_count","model":"gpt-5.5","usage":{"input_tokens":1000,"output_tokens":500}}',
    ])
    u = parse_run_usage(nd, "codex")
    assert u.input_tokens == 1000 and u.output_tokens == 500
    assert u.cost_usd == 0.02  # 1000*5e-06 + 500*3e-05


def test_parse_run_usage_codex_sem_modelo_fica_sem_custo():
    nd = '{"type":"token_count","usage":{"input_tokens":1000,"output_tokens":500}}'
    u = parse_run_usage(nd, "codex")
    assert u.input_tokens == 1000 and u.cost_usd == 0.0  # sem model → tokens sem custo, não chuta


def test_parse_run_usage_sem_uso_none():
    assert parse_run_usage("lixo sem json", "claude") is None
