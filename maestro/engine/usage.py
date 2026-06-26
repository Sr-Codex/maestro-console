"""Uso de tokens/custo por agente (diferencial F1) — gi-free, testável.

Captura o uso reportado pelos CLIs em modo estruturado e acumula por agente:
- **claude** (`-p --output-format json`): tem `total_cost_usd` + `usage.input_tokens`/
  `output_tokens` (ou variações `cost.{input_tokens,output_tokens,total_cost}`).
- **codex** (`exec --json`): emite tokens CUMULATIVOS; o uso de um run = cumulativo
  atual − anterior (mesma lógica do `ccusage`).

Esta fase (F1a) entrega só o parser + o ledger (persistência via Store). O wiring no
run mediado é a F1b.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def __add__(self, other: AgentUsage) -> AgentUsage:
        return AgentUsage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            round(self.cost_usd + other.cost_usd, 6),
        )


def _int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def parse_claude_usage(s) -> AgentUsage | None:
    """Uso a partir do JSON do `claude -p --output-format json`. None se não houver."""
    try:
        d = json.loads(s) if isinstance(s, str) else s
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(d, dict):
        return None
    usage = d.get("usage") if isinstance(d.get("usage"), dict) else None
    cost_obj = d.get("cost") if isinstance(d.get("cost"), dict) else None
    src = usage or cost_obj or d
    inp = _int(src.get("input_tokens"))
    out = _int(src.get("output_tokens"))
    cost = _float(
        d.get("total_cost_usd")
        if d.get("total_cost_usd") is not None
        else (cost_obj or {}).get("total_cost", src.get("total_cost"))
    )
    if inp == 0 and out == 0 and cost == 0.0:
        return None
    return AgentUsage(inp, out, cost)


def parse_codex_cumulative(s) -> AgentUsage | None:
    """Maior total CUMULATIVO de tokens encontrado no `codex exec --json` (NDJSON).

    Codex reporta cumulativo; o delta de um run é responsabilidade do chamador
    (cumulativo_atual − cumulativo_anterior). Custo costuma vir em créditos (ausente).
    """
    best: AgentUsage | None = None
    for line in (s or "").splitlines():
        line = line.strip()
        if not line or "token" not in line.lower():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        u = ev.get("usage") if isinstance(ev.get("usage"), dict) else ev
        if not isinstance(u, dict):
            continue
        inp = _int(u.get("input_tokens"))
        out = _int(u.get("output_tokens"))
        if inp or out:
            cand = AgentUsage(inp, out, 0.0)
            if best is None or (cand.input_tokens + cand.output_tokens) > (
                best.input_tokens + best.output_tokens
            ):
                best = cand
    return best


class UsageLedger:
    """Acumula uso por agente, persistido no Store (ui_state `usage_<agente>`)."""

    def __init__(self, store) -> None:
        self._store = store

    def add(self, agent_id: str, u: AgentUsage) -> AgentUsage:
        total = self.get(agent_id) + u
        self._store.set_ui(
            f"usage_{agent_id}",
            json.dumps(
                {
                    "input": total.input_tokens,
                    "output": total.output_tokens,
                    "cost": total.cost_usd,
                }
            ),
        )
        return total

    def get(self, agent_id: str) -> AgentUsage:
        raw = self._store.get_ui(f"usage_{agent_id}")
        if not raw:
            return AgentUsage()
        try:
            d = json.loads(raw)
            return AgentUsage(_int(d.get("input")), _int(d.get("output")), _float(d.get("cost")))
        except (json.JSONDecodeError, TypeError, AttributeError):
            return AgentUsage()
