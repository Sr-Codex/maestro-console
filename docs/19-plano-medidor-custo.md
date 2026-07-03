# Plano — F1: medidor de custo/tokens + budget cap

> Data: 2026-07-03 · PT-BR · Origem: `docs/08` (diferencial-âncora, dor #1 "custo às cegas") +
> `docs/15` (F1 reelevado pelo Fable: é **controle de segurança do ADR-17** sem implementação) +
> pesquisa profunda 2026-07-03 (103 subagentes, repos GitHub reais, verificação adversarial).
> Segue o protocolo do `AGENTS.md`: **analisar → planejar → pesquisar → validar → codar.**
>
> ✅ **Blocos A+B+C ENTREGUES em v0.54.0 (2026-07-03)** — o "velocímetro": preço vendorizado +
> custo + fiação no run + display lean por nó. Absorve o PR #9 (`usage.py` estendido). **Falta o
> Bloco D (budget cap)** — próxima PR (o "limitador"; sensível a segurança, possível nota no
> ADR-17). Detalhes/verificação no CHANGELOG v0.54.0 e no `docs/STATUS.md`.

## 1. Objetivo (a dor, dupla)
- **Produto:** "custo às cegas" é a **dor #1 da categoria** (`docs/08`; Vantage/Finout). Sessões
  agênticas têm custo ~quadrático; ninguém atribui gasto por agente. O Maestri não tem medidor.
- **Segurança:** o **ADR-17 (Etapa 3) EXIGE "budget por CUSTO REAL de tokens"** como controle
  obrigatório do Maestro mode (contagem de agentes é "teatro parcial"). Hoje é **promessa sem
  implementação** — com agentes recrutando agentes, custo às cegas é um **guardrail que falta**.

## 2. O que já existe (PR #9, `maestro/engine/usage.py` — NÃO reinventar)
- `AgentUsage(input_tokens, output_tokens, cost_usd)` (dataclass gi-free, com `__add__`).
- `parse_claude_usage(s)` — lê `usage` + `total_cost_usd` do `claude -p --output-format json`.
- `parse_codex_cumulative(s)` — maior total CUMULATIVO de tokens do `codex exec --json` (NDJSON);
  **Codex não dá custo, só tokens.**
- `UsageLedger` — acumula por agente, persiste no Store (`ui_state` `usage_<agente>`); `add`/`get`.
- **Status:** parser + ledger prontos e testados, mas **não fiados no fluxo de run** e **sem
  custo pro Codex, sem budget, sem display**. É a fundação certa (a pesquisa confirma o approach).

## 3. Veredito da pesquisa (repos reais — fonte + data, tudo verificado 3-0)
1. **Fonte do uso:** todo tracker maduro parseia **JSONL local** (`~/.claude/projects/*/*.jsonl`,
   `~/.codex/sessions/*.jsonl`), lendo `message.usage` (input/output/`cache_creation_input_tokens`/
   `cache_read_input_tokens`/model). Fontes: [ccusage](https://github.com/ryoppippi/ccusage),
   [tokscale](https://github.com/junhoyeo/tokscale), [phuryn/claude-usage](https://github.com/phuryn/claude-usage),
   [claude-code#33978](https://github.com/anthropics/claude-code/issues/33978). **PORÉM:** nosso
   `--output-format json` (com `total_cost_usd` autoritativo) é **alternativa válida e mais simples**
   pra um turno headless — **não precisamos trocar** pra scan de JSONL. (JSONL fica de fallback.)
2. **Tabela de preço canônica:** LiteLLM [`model_prices_and_context_window.json`](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json)
   — por-token USD, com `cache_creation_input_token_cost` e `cache_read_input_token_cost` separados.
   Ex. Sonnet: input 3e-06, output 1.5e-05, cache-write 3.75e-06, cache-read 3e-07 (verificado no
   arquivo ao vivo 2026-07-03). `tokencost`/`ccusage`/`tokscale` todos derivam dela.
3. **Custo preciso = 3 baldes** (input base · cache-write **~1.25x** · cache-read **~0.1x**) —
   aplicar 1 taxa única é materialmente errado. Claude: `total_cost_usd` da CLI **já é cache-aware**
   (confiar). Codex: converter tokens→$ pela tabela.
4. **Resolução em camadas (lean):** override do usuário → match exato na tabela → fallback estático;
   `ccusage`/`tokencost` embutem subset estático + `--offline`; unknown model → mostra tokens com
   marca "sem preço", **não chuta**. Pular fuzzy/OpenRouter (over-engineering p/ app de 2 provedores).
5. **Padrão vencedor single-user (ccusage):** parse local + tabela estática + **um número**, sem
   daemon/rede. Langfuse/Helicone/OpenTelemetry GenAI = **overkill** p/ app GTK local no ARM.
   → valida o **display lean por nó**.
6. **Fiação no run (tokscale headless):** após cada turno, jogar o **stdout já capturado**
   (`claude -p --output-format json`; `codex exec --json`) no `parse_*` + `UsageLedger.add` — o
   orquestrador já é dono do subprocess; **não precisa** dar tail em `~/.claude/projects`.

**⚠️ Gap da pesquisa (honesto):** os repos **não** documentam bem a *mecânica de enforcement do
budget cap* (pausa vs aborta, pre-turn vs post-turn). → o design do teto sai do **ADR-17**, não é
copiado. (Ver §5, decisões abertas.)

## 4. Plano cirúrgico (o que a pesquisa já resolve)
**Bloco A — preço + custo (engine, gi-free, testável):**
- **Vendorizar** `maestro/engine/pricing.json` — subset ESTÁTICO da LiteLLM só com os modelos
  Claude + Codex/GPT usados, com **header datado + SHA da fonte + URL de refresh** (raw LiteLLM).
  Isola o volátil atrás de um arquivo de dados (regra 5 de stack durável) — **sem depender do
  pacote `litellm`** (pesado/churny no ARM).
- Estender `AgentUsage` com `cache_creation_input_tokens`/`cache_read_input_tokens` (Claude).
- `cost_from_tokens(usage, model, table)` — 3 baldes; unknown model → `None` (marca "sem preço").
- Claude: usar `total_cost_usd` direto. Codex: `cost_from_tokens`.

**Bloco B — fiar no run (fonte = JSONL de sessão):**
- **Achado na implementação (medido):** o run headless emite TEXTO (adapters com `output_args=[]`),
  então o stdout NÃO tem uso. Fonte correta = o **JSONL de sessão** (o que a pesquisa apontou):
  `usage_from_session(agente, session_id)` lê `~/.claude/projects/*.jsonl` / `~/.codex/sessions`,
  soma o uso e calcula o custo pela tabela. Mapeado por `session_id` (o `SessionManager` já rastreia).
  `on_usage` grava o TOTAL no `UsageLedger` (persiste via `ui_state`).

**Bloco C — display lean por nó:**
- Um número discreto de **$ acumulado** no header/cápsula contextual do nó (reusa o padrão do dot
  de estado / badges). Total do fleet num cantinho. Sem dashboard.

**Bloco D — budget cap (design do ADR-17 — ver §5):**
- Teto por nó/linhagem + total; **soft cap** (pausa-e-confirma, HITL) e **hard cap** (barra o
  próximo turno). Alinha com ADR-17 "HITL por irreversibilidade" + "budget por custo real".

## 5. Decisões — VALIDADAS com o usuário (2026-07-03)
1. ✅ **Fonte do custo:** Claude = `total_cost_usd` (autoritativo/cache-aware); Codex = tabela
   vendorizada (Codex não dá custo). Usa o melhor de cada.
2. ✅ **Budget dispara PÓS-TURNO** (mede o real → gate no próximo dispatch) — casa com "medir antes
   de teorizar". *(Para o Bloco D, na 2ª rodada.)*
3. ✅ **Soft + hard cap** (2 limites): soft = avisa + pede confirmação humana (HITL, ADR-17); hard =
   barra o próximo turno. *(Bloco D, 2ª rodada.)*
4. ✅ **Escopo desta 1ª rodada = A+B+C** (medir + custo + display lean por nó — "o velocímetro").
   O **Bloco D (budget cap)** vem na **PR seguinte** (a parte delicada — barra o dispatch, HITL,
   sensível a segurança — merece PR própria + possível nota no ADR-17). Ordem sã: ver o número
   certo antes de barrar com base nele.

## 6. Git (absorver o PR #9)
O PR #9 (só `usage.py`+teste, pausado desde 26/06) é a **fundação** desta feature. Plano: trazer
o `usage.py` pra esta branch, estendê-lo (cache buckets), e esta feature **supersede** o PR #9 →
fechar o #9 apontando pra cá (o código é absorvido, não perdido).

## 7. Definition of done (por rodada)
- `usage.py`/`pricing` gi-free → testes unit (3 baldes, unknown→sem preço, Codex tokens→$, ledger
  acumula+persiste). Fiação testada (parse do stdout real de claude/codex → ledger). Display:
  probe de runtime (número no header). `ruff` + suite verdes + boot smoke. CHANGELOG + 1 bump.
  ADR? — o **budget cap (Bloco D)** provavelmente merece nota no/ligada ao ADR-17 (é o controle
  que ele exige); avaliar um ADR curto quando o D for implementado.
