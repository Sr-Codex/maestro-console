"""Budget cap (F1 Bloco D) — o "limitador" de gasto do fleet. gi-free, testável.

Modelo de segurança (ADR-17): o gasto CONTADO é um **contador monotônico host-side** — só sobe,
nunca por ação do agente. Isso fecha o *laundering* (o agente dispensar o caro ou rotacionar a
sessão pra "zerar" o total e o cap liberar). O humano zera manualmente (baseline/reset).

Estado no `ui_state`:
- `budget_hard` / `budget_soft` (USD, string; vazio = SEM teto — opt-in).
- `budget_fleet_total` — acumulador monotônico do custo (USD), só cresce.
- `budget_last_<agente>` — último total de sessão visto por agente (p/ calcular o delta positivo).
- `budget_baseline` — marco: o gasto que CONTA = `budget_fleet_total − baseline`.
"""
from __future__ import annotations


def budget_verdict(counted: float, soft: float | None, hard: float | None) -> str:
    """`hard` (barra) / `soft` (avisa) / `ok`. Teto None/≤0 = desligado (não dispara)."""
    if hard is not None and hard > 0 and counted >= hard:
        return "hard"
    if soft is not None and soft > 0 and counted >= soft:
        return "soft"
    return "ok"


def _f(v, default: float | None = None) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def budget_limits(store) -> tuple[float | None, float | None]:
    """(soft, hard) em USD do `ui_state`. Sem hard → (None, None) [desligado]. Soft vazio com hard
    setado → 75% do hard (a "linha operacional" — Fable)."""
    hard = _f(store.get_ui("budget_hard"))
    if hard is None or hard <= 0:
        return (None, None)
    soft = _f(store.get_ui("budget_soft"))
    if soft is None or soft <= 0:
        soft = round(0.75 * hard, 2)
    return (soft, hard)


def record_spend(store, agent_id: str, session_total_cost: float) -> None:
    """Acumula o gasto de um agente no contador MONOTÔNICO. `session_total_cost` é o total da
    sessão ATUAL do agente (cumulativo). Delta positivo: se a sessão cresceu, `novo − último`; se
    rotacionou (novo < último), a sessão anterior já foi bancada → banca o novo total. **Nunca
    subtrai** (dispensar/rotacionar não reduz o contado)."""
    new = max(0.0, _f(session_total_cost, 0.0) or 0.0)
    last = _f(store.get_ui(f"budget_last_{agent_id}"), 0.0) or 0.0
    delta = (new - last) if new >= last else new
    if delta > 0:
        total = (_f(store.get_ui("budget_fleet_total"), 0.0) or 0.0) + delta
        store.set_ui("budget_fleet_total", f"{total:.6f}")
    store.set_ui(f"budget_last_{agent_id}", f"{new:.6f}")


def counted_spend(store) -> float:
    """Gasto que CONTA pro budget = acumulador monotônico − baseline (nunca negativo)."""
    total = _f(store.get_ui("budget_fleet_total"), 0.0) or 0.0
    base = _f(store.get_ui("budget_baseline"), 0.0) or 0.0
    return max(0.0, round(total - base, 6))


def reset_budget(store) -> None:
    """Zera o gasto contado movendo o baseline pro total atual (só o HOST — nunca o agente)."""
    total = _f(store.get_ui("budget_fleet_total"), 0.0) or 0.0
    store.set_ui("budget_baseline", f"{total:.6f}")


def check(store) -> str:
    """Veredito atual do budget (`ok`/`soft`/`hard`) a partir do estado no store."""
    soft, hard = budget_limits(store)
    return budget_verdict(counted_spend(store), soft, hard)
