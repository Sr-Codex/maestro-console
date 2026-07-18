# Review de prontidão pra produção — por fases (doc vivo)

> **Objetivo:** responder "está realmente pronto pra produção real?" com evidência, não impressão.
> "Produção" aqui = app single-user rodando no uConsole CM4 do dono: funciona de verdade no
> device, não perde dado, o sandbox segura agente hostil, se recupera de crash.
> **Método:** 7 fases (docs → código → segurança → testes → runtime no device → UX por estado →
> veredito adversarial Fable), cada uma com relatório aqui. Achado vira fix ou item de fila —
> nunca "anotado e esquecido". Nível escolhido pelo usuário: **avançado (todas as fases)**.
> Iniciado: 2026-07-18 · baseline **v0.67.0** (`2a6c77a`).

---

## Fase 1 — Verdade dos docs (drift docs↔código) — ✅ CONCLUÍDA 2026-07-18

**Método:** leitura direta dos docs-âncora + 3 verificadores independentes em paralelo
(STATUS.md↔código · CHANGELOG↔git · ADR-1..29↔código), cada um reportando só divergência
com evidência `file:line`.

### Veredito da fase

**Os docs são substancialmente VERDADEIROS.** Nenhuma feature afirmada que não exista; nenhum
ADR violado no código atual — incluindo TODOS os invariantes de segurança (ADR-17/18/21/22/23/
25/26/27/28/29) e os 19 testes-prova citados, todos presentes. O drift encontrado é de
**contadores/carimbos não re-atualizados** (padrão claro: conteúdo novo entra certo; os ranges
"v0.X→v0.Y / ADR-1..N" dos docs-âncora ficam congelados) + 1 achado de processo (tags).

### Achados (A1..A10)

| # | Sev | Onde | O que |
|---|-----|------|-------|
| A1 | 🟡 média | `docs/index.md` (cabeçalho + linhas canônicas) | Diz "Atualizado: 2026-07-02 (v0.51.0)", "CHANGELOG v0.1.0→v0.51.0", "ADR-1..20". Real: v0.67.0, ADR-1..29. O PR #89 adicionou as linhas 27-32 mas não re-carimbou o cabeçalho. |
| A2 | 🟡 média | `docs/index.md` (3 linhas de estado) | docs/19: "Bloco D (budget cap) **pendente**" → entregue v0.55.0/ADR-22. docs/21: "**pronto pra virar stories**" → entregue v0.56.0/ADR-23. docs/08: "medidor de custo **segue não entregue**" → entregue v0.54.0. O mapa afirma como faltando o que já existe. |
| A3 | 🟡 média | `docs/STATUS.md:48` | "Fontes canônicas: CHANGELOG (v0.1.0→**v0.55.0**) e ADR (**1..22**)" — 12 versões e 7 ADRs atrás; contradiz o topo do mesmo doc (v0.67.0). |
| A4 | 🟢 baixa | `docs/STATUS.md:185` | "554 testes (+19 skip)" — medido hoje: **605 coletados só no venv** (96 arquivos; os módulos gi nem entram nessa coleta) e ~16 marcadores reais de skip. Contador congelado de versão antiga. |
| A5 | 🟢 baixa | `docs/architecture.md` (nota do topo) | "ADRs canônicos e completos (ADR-1..**15**)" — contador congelado (29). |
| A6 | 🔵 processo | git tags | Última tag: **v0.46.0**. As 21 versões v0.47.0→v0.67.0 não têm tag (além de buracos antigos: 0.5-0.6, 0.13.0, 0.19-0.25, 0.26.0, 0.27-0.32, 0.37.0, 0.37.2). A política "tag SemVer só em release" nunca definiu o que conta como release → na prática o tagging parou. Decisão do usuário: retomar (e de onde), ou declarar formalmente que tag ficou opcional. |
| A7 | ⚪ registro | commits `#48`/`#49` | Mensagens carimbaram "v0.49.0" em trabalho que o CHANGELOG registra (corretamente) como 0.50.0/0.51.0. Histórico imutável — só registrar, nada a fazer. |
| A8 | 🟢 baixa | `CHANGELOG.md` (formato) | Cabeçalho promete "Keep a Changelog / Datas em 2026", mas nenhuma entrada carrega data. Ou datar as próximas, ou ajustar a promessa do cabeçalho. |
| A9 | ⚪ registro | `docs/STATUS.md` (precisão) | A lógica de `<ws>/pastes/` vive em `canvas.py` (`_pastes_dir`, ~5388), não em `paste.py` (que cuida de nome/quote/cap). Comportamento correto; só a localização difere do que o texto sugere. |
| A10 | 🟢 higiene | `.claude/worktrees/docs-paste-imagem/` | Worktree órfã da feature v0.67.0 já mergeada — remover (`git worktree remove`). |

### Confirmado OK (agregado)

- **CHANGELOG:** continuidade perfeita v0.1.0→v0.67.0 (67 minors + patches, ordem estrita),
  topo = pyproject, todo feat/fix mergeado tem entrada, nenhuma data impossível.
- **STATUS.md:** todos os 12 módulos citados existem com o papel citado; todos os 13 símbolos
  citados existem; comportamentos verificáveis (bwrap estrito, `--unshare-pid`, SIGKILL no
  unload, socket por agente, `CLAUDE_CONFIG_DIR`/`CODEX_HOME`, cap 8192px) conferem;
  SSH remoto de fato NÃO implementado (só placeholder "soon").
- **ADR-1..29:** zero violação. Spot-checks profundos passaram: sandbox fail-safe sem
  `--dangerously-*` default (ADR-6/19); socket pathname + nunca montar o pai das boxes
  (ADR-17); autoridade só por `_recruited_by`/`_own_recruit`, líder sem autoridade (ADR-18/21);
  `record_spend` monotônico + `budget_blocked` fora de `ABUSE_EVENTS` (ADR-22); SIGKILL +
  anti-race (ADR-23); dirty-flag + SIGTERM/SIGHUP→quit (ADR-25); `escalated_budget` + gate no
  LIVE (ADR-26); brief re-carimbado, sanitizado, nunca lido de volta (ADR-27); substituição de
  rw_paths + máscara tmpfs em todo spawn + resolvedor único nos 4 pontos de argv (ADR-28);
  nome hostil nunca toca o PTY + injeção sem `\r` (ADR-29).
- **prd.md / architecture.md:** notas de defasagem presentes e honestas (exceto A5).

### Fixes — estado

1. ✅ **Aplicado (2026-07-18, nesta branch):** `index.md` re-carimbado (cabeçalho v0.67.0,
   ADR-1..29, estados de docs/19/21/08 corrigidos pra "entregue").
2. ✅ **Aplicado:** `STATUS.md:48` (range → v0.67.0 / ADR-1..29) e `:185` (605+ testes medidos).
3. ✅ **Aplicado:** nota do `architecture.md` → ADR-1..29.
4. ✅ **Aplicado:** worktree órfã `.claude/worktrees/docs-paste-imagem` removida (limpa,
   conteúdo mergeado no PR #89) + branch local `docs/index-27-32` deletada.
5. ⏳ **Decisão do usuário pendente:** A6 (retomar tags de release ou declarar opcionais) e
   A8 (datar entradas do CHANGELOG ou ajustar o cabeçalho).

---

## Fase 2 — Código (correctness) — ⏳ pendente
## Fase 3 — Segurança — ⏳ pendente
## Fase 4 — Testes (ponto cego dos skipados) — ⏳ pendente
## Fase 5 — Runtime no device (prova real) — ⏳ pendente
## Fase 6 — UX por estado — ⏳ pendente
## Fase 7 — Veredito adversarial (Fable) — ⏳ pendente
