# Plano — Budget cap: pausa graciosa + notificação + retomada 1-clique

> Data: 2026-07-11 · PT-BR · Origem: `docs/15` (item 2026-07-03, dor RunMaestro #235) — extensão
> do Bloco D do F1 (`docs/20`, entregue em v0.55.0/ADR-22). Protocolo do `AGENTS.md`:
> **analisar → planejar → pesquisar → validar → codar.** A v1 deste plano foi **REPROVADA na
> revisão adversarial (Fable 5)** — a peça central (fila FIFO de dispatches crus) re-executaria
> prompts órfãos de consumidor; o design abaixo é a **v2 pós-Fable** (ver §9, 10 emendas).
> **Não codar antes da validação do usuário.**

## 1. Objetivo (do freio ao freio COM retomada)

O budget cap (v0.55.0) **barra** o gasto ao estourar o hard — mas barra do jeito que a dor #235
descreve: **em silêncio e perdendo o trabalho**. Hoje, estourou o teto no meio de um run longo:
o turno barrado é descartado (nem no `envelope_log` entra), ninguém é avisado (só o HUD fica
vermelho — o hard NÃO notifica; só o soft avisa), e "retomar" significa reconstruir o contexto na
mão. Este plano fecha o tríptico:

1. **Pausa graciosa** — a unidade de trabalho barrada é **preservada de forma retomável**; o fleet
   entra num estado explícito "⏸ pausado por budget" (textualmente distinto de erro).
2. **Notificação imediata** — desktop notify na PRIMEIRA barrada do hard, com motivo + gasto/teto
   + o que fazer (padrão da mensagem 429 da Anthropic: motivo explícito + ação).
3. **Retomada 1-clique** — o humano sobe o teto OU zera o gasto → um clique retoma do ponto exato,
   sem re-perguntar (padrão GitHub Actions: aprovar re-executa a unidade barrada, não re-pergunta).

## 2. O que já existe (REUSAR — não reinventar) — mapeado no código 2026-07-11

- **Gate hard:** `Orchestrator.delegate` (`orchestrator.py:100-111`) — `budget.check(store)=="hard"`
  → devolve `Envelope(BLOCKED)` ANTES de rodar o agente (→ re-executar é idempotente por
  construção). O turno barrado é perdido e invisível (sem fila; fora do `envelope_log`).
- **Cadeia de team (a ÚNICA unidade retomável do codebase — achado Fable E1):** passo não-DONE
  → `chain_status="escalated"` e a cadeia PARA (`orchestrator.py:255-260`). Persistida em
  `chain_runs`/`chain_steps` e **`resume_chain` (`orchestrator.py:181-220`) já retoma da 1ª etapa
  não-DONE** — inclusive re-rodando o passo que ficou BLOCKED (verificado). Falta só saber POR QUE
  escalou (budget vs erro) pra retomada saber o que listar.
- **Demais origens de dispatch NÃO são retomáveis por design** (verificado pelo Fable, E1): ask
  por cabo devolve a resposta síncrona a quem perguntou (`ask_router.py:76` — re-rodar depois =
  resposta pro nada); handoff avulso A→B morre com a thread (`orchestrate.py:105-117`); routine
  re-roda inteira no próximo tick do scheduler (`routines.py:93-107` — reter um passo = execução
  duplicada); nota→agente idem (callback do caller).
- **Notificação:** `notify()` único via `notify-send` (`attention.py:107-118`). Soft avisa 1×
  (`_budget_soft_notify`, `canvas.py:4412-4425`); **hard não notifica**. Atenção (E4): `on_usage`
  só dispara DEPOIS de `run_in_session` (`orchestrator.py:291-297`) — uma barrada não gera
  callback de usage; o sinal da pausa precisa de outro canal (ver §4.3).
- **UI:** HUD `gasto $X/$Y` + classes `hud-soft`/`hud-hard` (`canvas.py:4370-4390`); diálogo
  **Limites** (💰, `_budget_dialog`, `canvas.py:4427-4495`) com Hard/Soft/RAM e "Zerar gasto".
- **Persistência:** chaves `budget_*` em `ui_state` sobrevivem a fechar/reabrir (ADR-22); chains
  em `chain_runs`/`chain_steps`. Regra do repo: "abre igual fechou" vale pro estado da pausa.

## 3. Pesquisa ao vivo (2026-07-11) — o que a comunidade validou

- **RunMaestro #235** ("Token Exhaustion UX in Auto-Run Mode", aberta, sem implementação): run de
  24h parado 4h em silêncio; pedem (a) detecção proativa, (b) notificação, (c) retomada sem perder
  contexto ("reiniciar perde tudo"; hoje descobrem via `git log`). — github.com/RunMaestro/Maestro/issues/235
- **Claude Code**: ao bater usage limit, para e NÃO retoma sozinho; 5+ issues pedem auto-resume
  (#18980, #38263, #47276…). A mensagem boa (motivo + horário de reset) é o modelo a copiar.
- **Mercado**: NENHUM orquestrador de código tem budget-cap com pause/resume (Cursor cappa por $
  mas só PARA; Conductor/Squad/Vibe Kanban só têm pause manual). Diferencial real; sem referência
  canônica a copiar.
- **LiteLLM** ao estourar: 429 e **DROPA** a request (anti-padrão). Issue #14144 pede distinguir
  "parado por budget" de erro — mesma lacuna do #235: **o estado pausado tem que ser textualmente
  distinto de falha**.
- **LangGraph interrupt/checkpoint** (padrão-ouro): pausar = persistir + reter; retomar re-executa
  a **unidade barrada inteira** (exige idempotência — no nosso caso, de graça: o gate barra
  pré-turno). No maestro, a "unidade com contexto longo" é a **chain** — que já tem checkpoint.
- **GitHub Actions approval gate** (UX de referência): aprovar 1×; re-run não re-pergunta.

## 4. Design v2 (pós-Fable) — retenção por UNIDADE TIPADA, sem fila nova

**Princípio (emenda E1):** só se retém o que tem retomada com consumidor vivo. Nada de fila
genérica de prompts crus — cada origem tem seu destino:

| Origem do dispatch barrado | O que acontece na pausa | Retomada |
|---|---|---|
| **Chain de team** | `chain_status="escalated_budget"` (novo valor, distingue de erro) | `resume_chain` (já existe) — re-roda o passo BLOCKED |
| **Routine** | nada a reter — o scheduler re-roda a routine inteira no próximo tick | automática ao liberar o teto |
| **Ask por cabo / handoff / nota** | só o BLOCKED (agora logado no `envelope_log`) + notificação | humano re-dispara pelo fluxo normal |
| **Floor run** | fail-fast com mensagem clara (E3: reter re-executaria no workspace errado) | humano re-dispara (é ação humana por natureza) |

### 4.1 Marcar a escalada por budget + logar o BLOCKED
No gate (`orchestrator.py:100-111`): logar o envelope BLOCKED no `envelope_log` (hoje invisível).
Em `_run_steps`/`run_chain` (`orchestrator.py:148-151,255-260`): quando o passo volta BLOCKED por
budget, gravar `chain_status="escalated_budget"` (em vez do genérico `"escalated"`). É o ÚNICO
delta de dado do plano — sem tabela nova, sem fila (corte Fable: mata E1/E2/E5/E6/E7/E8).

### 4.2 Estado visível "⏸ pausado por budget" (derivado, não flag solta)
Emenda E10: nada de flag que dessincroniza. "Pausado" é **derivado**: `veredito == hard` (e/ou
existem chains `escalated_budget`). Na UI:
- **HUD**: segmento vira `⏸ budget · $X/$Y · N chains retidas` (classe `hud-hard` mantida).
- **Texto distinto de erro em TODO lugar** (LiteLLM #14144/#235): nota do envelope, HUD, tooltip e
  notificação dizem "pausado por budget" — nunca "falhou".
- Nó que recebeu BLOCKED aparece `blocked` (Mocha red, v0.61.0) com tooltip do motivo budget.

### 4.3 Notificação no hard (fecha a falha silenciosa)
Na **primeira** barrada do hard: `notify("maestro: budget PAUSOU o fleet", "gasto $X de $Y ·
abra Limites (💰) pra liberar e retomar", sound=True)` — som LIGADO (diferente do soft): pausa de
fleet é o evento que o humano ausente precisa ouvir. Guard 1×-por-episódio; rearma ao liberar.
**Canal (E4):** o gate NÃO gera callback de usage (barra antes de rodar) → sinal engine→UI
dedicado no padrão do `usage_bus` (`bootstrap.py:59-60`), com fallback de poll no `_anomaly_tick`
(3s, já existe) pra barradas com o canvas ocupado.

### 4.4 Retomada 1-clique
No diálogo **Limites** (e atalho no HUD quando pausado):
- **Lista do que está retido** (E6): chains `escalated_budget` com time/agente do passo + idade —
  cada uma com **▶ retomar** e **🗑 descartar** (+ "descartar todas"). Sem lista, a única saída
  da fila seria gastar; e retomar às cegas prompt de horas atrás é o risco de ação obsoleta.
- **"▶ Retomar"** habilita só quando o veredito atual < hard (o humano JÁ subiu o teto ou zerou —
  senão re-barraria tudo). Clique → `resume_chain(run_id)` por item (ou todas, em ordem de idade);
  se o teto novo estourar no meio, o passo volta a escalar `escalated_budget` — sem loop, sem
  perder posição (a chain é o checkpoint, não uma fila — E8 não se aplica).
- **Alvo morto (E9):** agente do passo dispensado/time editado → skip com aviso na lista
  ("time mudou — retome pelo editor de team"), nunca crash.
- `_audit budget_resumed` / `budget_discarded` (trilha; fora de `ABUSE_EVENTS`, como
  `budget_blocked` — ADR-22).

### 4.5 Threshold proativo? NÃO — o hard JÁ vira o checkpoint gracioso
O #235 pede "pausar a 90%, antes do zero". Não precisa de 3º limiar: com pausa graciosa +
retomada, **o próprio hard é o ponto de pausa limpa** — quem quer pausar a 90% da carteira seta o
hard nesse valor. Mantém o ADR-22 intacto (soft = só aviso; sem HITL por-turno; monotonicidade).
**Endossado pela revisão Fable** ("só ficou verdade PORQUE a pausa vira graciosa").

## 5. Brechas de invariante (lição: o freio vale em TODAS as entradas)

O mapeamento achou 2 caminhos que gastam $ **fora do gate — e sem alimentar o contador** (mesma
classe do confused-deputy do wire/dismiss/reassign):
1. **Modo LIVE do cabo**: `_ask_live` injeta no VTE vivo sem gate nem contagem. **Fix (ajuste
   Fable):** gate no `_ask_delegate` (`canvas.py:4040-4047`) — veredito hard → **pula o live** e
   cai no headless, onde o gate uniforme do delegate barra (um BLOCKED só, mesmo texto).
   Verificado: `_ask_live` é SÓ injeção por cabo agente→agente; **digitação humana no VTE nunca
   passa por ali** — humano segue não-gateado e não-contado (o adversário do ADR-17 é o agente,
   não o dono; registrar 1 linha no ADR).
2. **Floor run** (`floor_run.py:39-48`): checar `budget.check` antes de rodar → **fail-fast** com
   mensagem "pausado por budget" (SEM retenção — E3: reter re-executaria fora do floor). Contagem
   do gasto do floor: entra no `on_usage` se barato; senão registra a lacuna no ADR.
3. **Contagem do gasto do modo LIVE** (sessão viva tem JSONL próprio; exige mapear session_id do
   PTY): **backlog próprio** — o gate entra JÁ, a contagem fica pra depois (endossado).

## 6. Pontos no código

- `orchestrator.py:100-111` — logar BLOCKED no `envelope_log`; `:148-151,255-260` — status
  `escalated_budget`.
- `budget.py` — helper puro `is_paused(store)` (derivado, gi-free, testável).
- `bootstrap.py:59-60` (padrão `usage_bus`) — sinal de pausa engine→UI.
- `canvas.py` — HUD (`_refresh_fleet_hud:4370`), notify hard, diálogo Limites (lista retidas +
  retomar/descartar), gate LIVE em `_ask_delegate:4040`.
- `floor_run.py:39-48` — gate fail-fast.
- `store.py` — query de chains por status (list `escalated_budget`).
- `_audit` — `budget_paused`/`budget_resumed`/`budget_discarded` (fora de `ABUSE_EVENTS`).

## 7. O que NÃO muda (guard-rails)

- **ADR-22 intocado**: contador monotônico, soft=só-aviso, reset só na UI do host, overshoot
  documentado. A pausa não mexe na contagem — só no destino da unidade barrada.
- **Sem fila persistente nova, sem tabela nova, sem estado novo na máquina de nó.**
- **Sem auto-resume por tempo**: retomar exige clique humano — o cap é controle de segurança
  (ADR-17); auto-resume o transformaria em atraso, não freio.
- **Retomada/descartar nunca por comando de agente** — mesmo princípio do "zerar só no host".

## 8. Definition of done (rascunho)

- Testes `.venv` (gi-free): gate loga BLOCKED; chain barrada vira `escalated_budget`;
  `resume_chain` re-roda o passo BLOCKED; re-estouro no meio re-escala sem loop; `is_paused`
  derivado; alvo morto → skip; floor run fail-fast.
- Probe gi (python do sistema): HUD pausado, notify hard 1×, lista de retidas + habilitação do
  Retomar conforme veredito, gate LIVE pulando pro headless.
- Persistência: fechar/reabrir pausado → reabre pausado com as chains listadas ("abre igual fechou").
- **Teste visual no device** (obrigatório antes do merge): estourar um teto baixo real e assistir
  pausa→notificação→liberar→retomar.
- `ruff` + suite + boot smoke + CHANGELOG + 1 bump. **Nota ligada ao ADR-22** (extensão do
  disjuntor) + linha sobre digitação humana não-gateada — avaliar ADR curto próprio.

## 9. Revisão adversarial (Fable 5, 2026-07-11) — v1 REPROVADA → v2

**Veredito da v1: REPROVADO** — "a peça central (fila FIFO de dispatches crus re-despachados via
`controller.delegate`) não retoma corretamente NENHUMA unidade de trabalho real do código". As 10
emendas, todas incorporadas na v2:

1. **E1 (ALTA)** Fila de prompts crus = resultados sem consumidor (ask síncrono, handoff morto com
   a thread, routine duplicada, nota sem callback). → retenção por unidade tipada (§4); só chain é
   retomável (e já tem `resume_chain`).
2. **E2 (ALTA)** Fila híbrida duplicaria a execução do passo de chain (item cru + `resume_chain`).
   → sem fila; só `escalated_budget`.
3. **E3 (ALTA)** Floor run retido re-executaria no workspace ERRADO (perde o cwd do floor). →
   fail-fast sem retenção.
4. **E4 (média)** `_on_usage_update` nunca dispara numa barrada (barra antes do run). → sinal
   dedicado padrão `usage_bus` + poll fallback.
5. **E5 (média)** Ressuscitar a tabela `tasks` é necromancia: sem colunas pra task_id/origem/chain,
   `set_task_status` nem existe (é `update_task`), sem método de listagem. → cortada com a fila.
6. **E6 (média)** Retomada cega a prompts obsoletos + sem "descartar". → lista com idade +
   descarte por item.
7. **E7 (média)** Fila sem teto = DoS de disco na pausa. → morta com a fila (chains já são
   bounded pelos fleet-caps).
8. **E8 (baixa)** Re-pausa embaralharia o FIFO. → n/a sem fila (chain é o checkpoint).
9. **E9 (baixa)** Alvo morto entre pausa e retomada → skip+aviso, nunca crash.
10. **E10 (baixa)** Flag `budget_paused` dessincronizável → estado derivado, não flag.

**Aprovado pelo Fable:** §4.5 (sem 3º limiar — coerente com ADR-22), as 2 brechas da §5 (reais,
verificadas; gate LIVE movido pro `_ask_delegate`), guard-rails da §7. Spot-check das citações da
v1: 13/14 corretas (a errada — métodos da tabela `tasks` — morreu com a fila).

## 10. DECISÕES — VALIDADAS com o usuário (2026-07-11, pós-Fable)

- ✅ **Design v2 como um todo** (retenção tipada via `escalated_budget` + `resume_chain`; sem fila).
- ✅ **Gates da §5 no MESMO PR** (LIVE via `_ask_delegate` + floor fail-fast) — é o invariante do
  mesmo freio (lição wire/dismiss); a contagem do gasto do LIVE fica pra backlog próprio.
- ✅ **Digitação humana segue fora do cap** (não gateada, não contada — o adversário do ADR-17 é o
  agente, não o dono). Registrar a linha no ADR junto com a implementação (§8 DoD).

Plano fechado pra implementação (branch `feat/` própria, após o merge deste doc).
