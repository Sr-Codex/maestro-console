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
import re
from dataclasses import dataclass
from pathlib import Path

_PRICING_PATH = Path(__file__).with_name("pricing.json")
_pricing_cache: dict | None = None


def _load_pricing_file() -> dict:
    """Tabela de preço vendorizada (pricing.json), cacheada. Só modelos → preços (sem _meta)."""
    global _pricing_cache
    if _pricing_cache is None:
        try:
            raw = json.loads(_PRICING_PATH.read_text(encoding="utf-8"))
            _pricing_cache = {k: v for k, v in raw.items() if not k.startswith("_")}
        except (OSError, json.JSONDecodeError):
            _pricing_cache = {}
    return _pricing_cache


def _norm_model(model: str) -> str:
    """Normaliza o id do modelo p/ casar na tabela: tira prefixo de região/provedor
    (`us.`/`eu.`/`global.`/`anthropic.`/`openai/`) e sufixo de data (`-YYYY-MM-DD`)."""
    m = (model or "").strip()
    m = re.sub(r"^(us|eu|au|jp|global)\.", "", m)
    m = re.sub(r"^anthropic\.", "", m)
    m = re.sub(r"^[a-z-]+/", "", m)  # ex.: "openai/gpt-5.5" → "gpt-5.5"
    m = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", m)  # sufixo de data
    return m


def model_price(model: str, table: dict | None = None) -> dict | None:
    """Preços de um modelo (override → tabela; com normalização). None se desconhecido."""
    table = _load_pricing_file() if table is None else table
    if not model:
        return None
    if model in table:
        return table[model]
    nm = _norm_model(model)
    return table.get(nm) or table.get(model)


def cost_from_tokens(
    input_tokens: int, output_tokens: int, model: str, *,
    cache_read: int = 0, cache_write: int = 0, table: dict | None = None,
) -> float | None:
    """Custo em USD por baldes. `input_tokens` = input BASE (não-cacheado); `cache_read`/
    `cache_write` são SEPARADOS e ADITIVOS — é o formato do JSONL do claude (input excl. cache) e
    do codex (sem cache). **None** se o modelo é desconhecido (tokens 'sem preço', não chuta)."""
    p = model_price(model, table)
    if p is None:
        return None
    cost = int(input_tokens) * float(p.get("input", 0.0))
    cost += int(output_tokens) * float(p.get("output", 0.0))
    cost += int(cache_read) * float(p.get("cache_read", p.get("input", 0.0)))
    cost += int(cache_write) * float(p.get("cache_write", p.get("input", 0.0)))
    return round(cost, 6)


def _iter_jsonl(path: Path):
    """Itera dicts de um arquivo JSONL (linha inválida = pulada). Silencioso se o arquivo some."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                d = _loads(line)
                if d is not None:
                    yield d
    except OSError:
        return


def _claude_session_usage(session_id: str) -> AgentUsage | None:
    """Soma o uso de um session_id nos JSONL do claude (~/.claude/projects/*/<id>.jsonl). O
    input_tokens do JSONL é BASE; cache_creation/cache_read são separados → custo por baldes."""
    base = Path.home() / ".claude" / "projects"
    hits = list(base.glob(f"*/{session_id}.jsonl")) if base.is_dir() else []
    if not hits:
        return None
    inp = out = cw = cr = 0
    model = ""
    for d in _iter_jsonl(hits[0]):
        if d.get("type") != "assistant":
            continue
        msg = d.get("message") or {}
        u = msg.get("usage")
        if not isinstance(u, dict):
            continue
        inp += _int(u.get("input_tokens"))
        out += _int(u.get("output_tokens"))
        cw += _int(u.get("cache_creation_input_tokens"))
        cr += _int(u.get("cache_read_input_tokens"))
        model = msg.get("model") or model
    if not (inp or out or cw or cr):
        return None
    cost = cost_from_tokens(inp, out, model, cache_read=cr, cache_write=cw) or 0.0
    return AgentUsage(inp + cw + cr, out, cost)  # input exibido = total de prompt tokens


def _codex_session_usage(session_id: str) -> AgentUsage | None:
    """Uso de uma sessão do codex (~/.codex/sessions/**/*<id>*.jsonl): maior cumulativo → custo."""
    base = Path.home() / ".codex" / "sessions"
    hits = list(base.glob(f"**/*{session_id}*.jsonl")) if base.is_dir() else []
    if not hits:
        return None
    text = "".join(open(hits[0], encoding="utf-8", errors="ignore"))
    u = parse_codex_cumulative(text)
    return with_cost(u, _extract_model(text)) if u else None


def usage_from_session(agent_name: str, session_id: str | None) -> AgentUsage | None:
    """Uso ACUMULADO de um agente, lido do JSONL de sessão (a fonte que ccusage/tokscale usam —
    o run headless emite texto, não JSON, então o stdout não serve). Retorna o TOTAL da sessão."""
    if not session_id:
        return None
    if "codex" in (agent_name or "").lower():
        return _codex_session_usage(session_id)
    return _claude_session_usage(session_id)


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
    if inp == 0 and out == 0 and not cost:  # sem tokens nem custo → nada a reportar
        return None
    return AgentUsage(inp, out, cost)


def _loads(line) -> dict | None:
    """json.loads tolerante: o dict do JSON, ou None se vazio/inválido/não-dict."""
    line = (line or "").strip()
    if not line:
        return None
    try:
        v = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None
    return v if isinstance(v, dict) else None


def _tok(u: AgentUsage) -> int:
    return u.input_tokens + u.output_tokens


def _codex_line_tokens(line: str) -> AgentUsage | None:
    """Tokens de UMA linha do codex NDJSON (evento com 'token'); None se não aplicável."""
    if "token" not in line.lower():
        return None
    ev = _loads(line)
    if ev is None:
        return None
    u = ev.get("usage") if isinstance(ev.get("usage"), dict) else ev
    if not isinstance(u, dict):
        return None
    inp, out = _int(u.get("input_tokens")), _int(u.get("output_tokens"))
    return AgentUsage(inp, out, 0.0) if (inp or out) else None


def parse_codex_cumulative(s) -> AgentUsage | None:
    """Maior total CUMULATIVO de tokens encontrado no `codex exec --json` (NDJSON).

    Codex reporta cumulativo; o delta de um run é responsabilidade do chamador
    (cumulativo_atual − cumulativo_anterior). Custo costuma vir em créditos (ausente).
    """
    best: AgentUsage | None = None
    for line in (s or "").splitlines():
        cand = _codex_line_tokens(line)
        if cand is not None and (best is None or _tok(cand) > _tok(best)):
            best = cand
    return best


def _extract_model(s) -> str:
    """Melhor-esforço: acha o id do modelo no output (claude json `model`; codex ndjson `model`
    em algum evento). '' se não achar (→ Codex fica com tokens sem custo, sem chutar)."""
    if not isinstance(s, str):
        return ""
    d = _loads(s)  # claude: um único objeto JSON
    if d is not None and d.get("model"):
        return str(d["model"])
    for line in s.splitlines():  # codex: NDJSON, procura o 1º evento com "model"
        if '"model"' not in line:
            continue
        ev = _loads(line)
        if ev is not None and (ev.get("model") or (ev.get("msg") or {}).get("model")):
            return str(ev.get("model") or ev["msg"]["model"])
    return ""


def parse_run_usage(stdout, agent_name: str) -> AgentUsage | None:
    """Uso de UM turno headless, por tipo de agente (o dispatcher que o run usa). Claude: custo
    autoritativo (`total_cost_usd`, cache-aware). Codex: tokens → custo pela tabela (se o modelo
    aparecer no output; senão tokens sem custo). None se não há uso capturável."""
    if "codex" in (agent_name or "").lower():
        u = parse_codex_cumulative(stdout)
        return with_cost(u, _extract_model(stdout)) if u else None
    return parse_claude_usage(stdout)  # claude-like (json com total_cost_usd)


def with_cost(u: AgentUsage | None, model: str) -> AgentUsage | None:
    """Preenche o custo de um `AgentUsage` a partir dos tokens (caso do Codex, `cost_usd==0`).
    Se já tem custo (Claude via `total_cost_usd`) ou o modelo é desconhecido, retorna inalterado."""
    if u is None or u.cost_usd:
        return u
    c = cost_from_tokens(u.input_tokens, u.output_tokens, model)
    return AgentUsage(u.input_tokens, u.output_tokens, c) if c is not None else u


class UsageLedger:
    """Acumula uso por agente, persistido no Store (ui_state `usage_<agente>`)."""

    def __init__(self, store) -> None:
        self._store = store

    def add(self, agent_id: str, u: AgentUsage) -> AgentUsage:
        return self.set_total(agent_id, self.get(agent_id) + u)

    def set_total(self, agent_id: str, total: AgentUsage) -> AgentUsage:
        """Grava o TOTAL do agente (usado quando a fonte é o JSONL de sessão, que já é cumulativo —
        somar de novo duplicaria). Persiste no Store."""
        self._store.set_ui(
            f"usage_{agent_id}",
            json.dumps(
                {"input": total.input_tokens, "output": total.output_tokens, "cost": total.cost_usd}
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
