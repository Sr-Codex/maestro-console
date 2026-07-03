# Plano — F1 Bloco D: budget cap (o "limitador")

> Data: 2026-07-03 · PT-BR · Origem: `docs/19` (F1; Bloco D era a 2ª rodada) + `docs/15` (F1 =
> controle de segurança do **ADR-17** sem implementação). Segue o protocolo do `AGENTS.md`:
> **analisar → planejar → validar → codar.** RASCUNHO — passou por revisão adversarial (Fable 5)
> antes de ir pra validação do usuário (ver §7). **Não codar antes de validar.**

## 1. Objetivo (o freio)
O **medidor** (v0.54.0) mostra o gasto. O **budget cap** o usa pra **frear**: um teto de $ que
**avisa** (soft) e depois **barra** (hard) o gasto dos agentes. Fecha o requisito do **ADR-17
(Etapa 3)** — "budget por CUSTO REAL de tokens" — hoje uma promessa sem implementação. Com
agentes recrutando agentes, gasto às cegas deixa de ser caro e vira **risco**.

## 2. O que já existe (REUSAR — não reinventar)
A infra do ADR-17 já tem o **padrão exato**, só que em *contagem de agentes*:
- **Cap de recrutamento:** `MAESTRO_SOFT_CAP=8` / `MAESTRO_FLEET_CAP` (hard); `_recruit_needs_hitl`
  (soft cruzado → confirmação humana); recrutar acima do hard → **bloqueado** + `_audit`.
- **`maestro_guard.py`:** `spawn_anomaly` (martelar o cap repetido → gatilho pro **kill-switch**).
- **HUD do fleet** (`_fleet_hud`), **trilha append-only** (`_audit`), **kill-switch** global.
- **`UsageLedger`** (F1): custo por agente → **custo do fleet** = soma. É o número do budget.

→ O budget é o cap de recrutamento **espelhado em $**: mesma máquina (soft→HITL, hard→bloqueia,
trilha, HUD), fonte = `UsageLedger` em vez de `_fleet_count()`.

## 3. Decisões já VALIDADAS (docs/19 §5)
- **Pós-turno:** mede o custo real depois do turno → decide sobre o PRÓXIMO dispatch.
- **Soft + hard cap** (2 limites de $).

## 4. Design (revisado pós-Fable — os furos que a v1 tinha)
- **Config:** `budget_soft`/`budget_hard` (USD) em `ui_state`; UI na **cápsula do Maestro mode**;
  **"sem teto" é o default** (opt-in). Se o usuário só preenche o hard, o soft nasce em ~75% dele.
- **CONTADOR MONOTÔNICO NO HOST (o coração — anti-laundering).** NÃO somar "agentes vivos" pelo
  `set_total` (lavável: o agente **dispensa** o caro ou **rotaciona a sessão** → o total cai →
  cap "libera"; é o runaway do ADR-17 contornando o próprio freio). Em vez disso, um acumulador
  `ui_state fleet_cost_total` que **só soma deltas positivos** por agente
  (`+= max(0, novo_total − anterior_daquele_agente)`), **inclusive de dispensados**, e **nunca
  subtrai**. Aplica a lição "gasto contado não pode diminuir por ação do agente".
- **Baseline + reset (senão o cap é inutilizável):** o gasto que conta = `fleet_cost_total −
  baseline`, onde `baseline` é gravado quando o cap é (re)setado. Botão **"zerar budget" SÓ na UI
  do host** (nunca comando de agente) → move o baseline pro total atual + `_audit budget_reset`.
- **Enforcement (pré-dispatch, no `Orchestrator.delegate`):**
  - `gasto_contado + (dispatches_em_voo × custo_médio_por_turno) ≥ **hard**` → **recusa o turno**
    (envelope de erro "budget excedido") + `_audit budget_blocked`. *(contar os em-voo fecha metade
    do overshoot — N turnos paralelos que já passaram no check pousam depois.)*
  - `gasto_contado ≥ **soft**` (< hard) → **só AVISO** (notificação + HUD âmbar + `_audit`),
    **não bloqueia** (ver §7.1 — custo é monotônico, HITL por-turno seria um hard-cap ruim).
- **`budget_blocked` FORA de `ABUSE_EVENTS`** (`maestro_guard.py:37`): pós-hard todo dispatch é
  bloqueado pra sempre — se contasse como abuso, uma cadeia com retry armaria o **kill-switch
  global** por estado permanente, não por runaway. Vai pra trilha, mas não pro `spawn_anomaly`.
- **Display:** HUD do fleet ganha `$X.XX / $HARD` (âmbar perto do soft, vermelho no hard) + o
  **top-spender** ao avisar (o humano decide quem dispensar). Codex sem preço → marca "+tokens sem
  preço" (senão um fleet Codex-pesado fura o teto invisível — `usage.py`).
- **Overshoot aceito e DOCUMENTADO:** medir pós-turno deixa passar até `N_paralelo × turno_máximo`
  acima do hard (turno pode custar centavos a ~$15 no patológico). Registrar no ADR: "é disjuntor,
  não medidor de precisão". Estimativa pré-turno foi preterida (chute).

## 5. Pontos no código (reuso)
- `maestro/engine/orchestrator.py` `delegate` (fronteira do dispatch mediado) — check pré-turno.
- `maestro/engine/maestro_guard.py` — função pura `budget_verdict(fleet_cost, soft, hard)` →
  `ok|soft|hard` (gi-free, testável), espelhando o estilo de `spawn_anomaly`.
- `maestro/engine/usage.py` `UsageLedger` — somar o fleet (novo helper `fleet_cost(agent_ids)`).
- `maestro/native/canvas.py` — config na cápsula Maestro mode; `$` no `_fleet_hud`; HITL (se §7).
- `_audit` (trilha) + `ui_state` (persistência) — já existem.

## 6. Definition of done (rascunho)
- `budget_verdict`/`fleet_cost` gi-free → testes (ok/soft/hard, sem-teto, borda). Enforcement
  testado no delegate (mock do ledger acima/abaixo do teto → recusa/passa). Persistência ("abre
  igual fechou"). Display: probe do HUD. `ruff` + suite + boot smoke. CHANGELOG + bump.
  **Nota no/ligada ao ADR-17** (é o controle que ele exige) — avaliar ADR curto.

## 7. Tensões — RESOLVIDAS pela revisão Fable 5 (2026-07-03)
1. ✅ **Soft = só AVISO** (não HITL). *Por quê:* custo é **monotônico** (cruzou o soft, todo turno
   fica acima pra sempre) — HITL por-turno vira um hard-cap com UX pior; ack-uma-vez vira máquina
   de estado que no fim se comporta como aviso. O recruit é reversível (dismiss volta pra baixo do
   cap), custo não. **Reverte a decisão original do usuário "soft = HITL"** — precisa da confirmação
   dele (foi decidido antes de ver a monotonicidade).
2. ✅ **Escopo GLOBAL** do fleet no MVP — é **disjuntor, não árbitro**: dinheiro é fungível; parar
   todo mundo quando a carteira estourou é o comportamento seguro. Per-linhagem responde justiça/
   atribuição (outra pergunta), só se houver dor medida. Mitiga mostrando o **top-spender** no aviso.
3. ✅ **Overshoot aceito** (é disjuntor) + contar dispatches em-voo no check + documentar no ADR.
4. ✅ **Barra no `delegate` (engine)** — como o soft virou só-aviso, **sem HITL na thread da main**.

## 8. DECISÕES que ainda faltam o usuário validar (o que o Fable elevou)
- **A mais importante (semântica do contador):** confirmar o **contador monotônico host-side**
  (soma só deltas positivos, inclui dispensados, nunca subtrai) + **baseline/reset manual**. É o
  que torna o cap **não-contornável** por agente e **usável** por humano. Errar aqui = cap teatral
  ou inquebrável-e-inútil.
- **Soft = aviso (não HITL):** confirmar a reversão (§7.1).
- **Codex sem preço:** aceitar que um fleet Codex-pesado pode furar o teto invisível (só marca no
  HUD), ou bloquear tokens-sem-preço também? (MVP: só marca.)
