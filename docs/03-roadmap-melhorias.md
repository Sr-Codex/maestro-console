# Roadmap de Melhorias — maestro console (vs Maestri)

> Gap analysis Maestri (themaestri.app, features até ~v0.30/2026) × maestro console **v0.6.0**.
> Pesquisa: `docs/01-pesquisa-maestri.md` + inventário do código (2026-06-22).
> **Foundation = decisão do usuário.** Este é um roadmap *proposto*: a ordem/escopo das fases é decisão sua.
> Princípio de filtro: alvo é o **uConsole** (ARM, 3.7 GB sem swap, tela 1280×720) → priorizar **leve + valor central**; adiar **pesado** (WebKit, LLM local).

---

## 1. Gap analysis (o que o Maestri tem × o que o console tem)

Legenda: ✅ tem · 🟡 parcial · ❌ não tem · ⚖️ peso no uConsole (🟢 leve / 🟡 médio / 🔴 pesado)

| # | Funcionalidade do Maestri | Console v0.6.0 | Peso | Valor | Notas |
|---|---|---|---|---|---|
| 1 | **Comunicação agente↔agente via cabo** (Agent Skill + PTY) | 🟡 orquestração **mediada** por envelope (sem cabo direto) | 🟢 | ⭐⭐⭐ | Coração do Maestri. Console já tem o motor robusto; falta o **gesto do cabo** + handoff disparado por ele |
| 2 | **Detecção de fim por quiescência** (monitorar terminal não-focado) | 🟡 usa `returncode` headless | 🟢 | ⭐⭐ | Necessário p/ cabo entre terminais **interativos** (idle do VTE) |
| 3 | **Terminais interativos conectados que conversam** | 🟡 VTE interativo (nativo); web read-only; **não conectados** | 🟢 | ⭐⭐⭐ | Decorre de #1 + #2 |
| 4 | **Floors** — branches/ambientes isolados (APFS COW) | ❌ | 🟢 | ⭐⭐⭐ | No Linux = **git worktree** (barato). Setup/Run/Teardown hooks, merge preview |
| 5 | **Roles ricos** — role.json + CLAUDE.md/AGENTS.md por subdir + badge/cor | 🟡 teams/roles existem; **sem** role.json/arquivos/badge | 🟢 | ⭐⭐ | Console já tem cor por **estado**; falta cor por **papel** + sidecar portável |
| 6 | **Notes no canvas + agent-to-note** (nota persistente lida/escrita por agente) | ❌ | 🟢 | ⭐⭐ | Colaboração leve e persistente; encaixa no canvas nativo |
| 7 | **Routines** — prompts agendados em intervalos (multi-step `&&`) | ❌ | 🟢 | ⭐⭐ | Timer/cron + reusa orchestrator. Pause/resume/run-count |
| 8 | **Attention dots / notificações** ("o que precisa de você") | 🟡 envelope tem `NEEDS_INPUT`/`BLOCKED` | 🟢 | ⭐⭐ | Falta o **realce visual** + notificação no canvas |
| 9 | **Command palette (Batuta)** — fuzzy file/workspace search (⌘P) | ❌ | 🟢 | ⭐ | UX; leve |
| 10 | **Múltiplos workspaces/projetos** | 🟡 dir de workspace; sem multi-projeto na UI | 🟡 | ⭐⭐ | Trocar de projeto preservando layout |
| 11 | **Backup & Restore** de workspace | 🟡 SQLite + node_positions | 🟢 | ⭐ | Export/import JSON do estado |
| 12 | **Temas de terminal** (Dracula/Catppuccin; formato Ghostty/iTerm2) | ❌ (VTE cor padrão) | 🟢 | ⭐ | VTE suporta paleta; cosmético |
| 13 | **Diff viewer / git no file tree / code review** | ❌ | 🟡 | ⭐⭐ | Útil p/ dev; média complexidade na tela pequena |
| 14 | **Parallel agent requests (batch)** | 🟡 `queue.py`+ceiling (não integrado) | 🟢 | ⭐ | Integrar a fila já existente |
| 15 | **Sketch/whiteboard, node groups, snapping** | ❌ | 🟡 | ⭐ | Canvas-candy; pouco valor no 1280×720 |
| 16 | **Portals** — browser embutido controlável por agente | ❌ | 🔴 | ⭐⭐ | WebKitGTK pesado; avaliar depois |
| 17 | **Ombro** — companheiro IA local on-device | ❌ | 🔴 | ⭐⭐ | Apple Foundation Models → no Linux precisaria Ollama/llama.cpp (RAM!) ou reusar `claude -p` como "ombro" |
| 18 | **Maestro Mode** (pin preset "manager") | ❌ | 🟢 | ⭐ | Pequeno preset |
| 19 | **File editor embutido** (syntax, multi-cursor, tabs) | ❌ | 🟡 | ⭐ | Existem editores nativos no uConsole; baixa prioridade |

---

## 2. Roadmap proposto (em fases / versões)

A ordem segue: **(1) fechar o diferencial central do Maestri** → **(2) maior valor de dev com baixo peso** → **(3) UX/observabilidade** → **(4) pesados opcionais**.

### 🎯 Fase 1 — v0.7.0 · "Cabos que conversam" (o coração do Maestri)
O maior gap e o que define o Maestri. O console já tem o motor (envelope, orchestrator, sandbox); falta o **gesto do cabo** disparando o handoff.
- Cabo **interativo** no canvas nativo: ligar nó-A → nó-B (criar/remover, persistir).
- **Handoff por cabo**: ao acionar, o output/resultado de A vira input de B — reusando o orchestrator mediado (robusto, logável, recuperável) em vez de `send-keys` frágil.
- **Detecção de quiescência (idle)** no VTE p/ saber quando um terminal interativo "terminou" (estabilização do output), espelhando o "monitorar terminal não-focado" do Maestri.
- Cor do cabo refletindo o estado do handoff (já temos cor por estado nos nós).
- *Saída:* arrastar cabo entre dois agentes → A delega a B → resposta volta, tudo registrado no envelope_log.

### 🧱 Fase 2 — v0.8.0 · "Floors" (ambientes isolados)
Equivalente Linux das Floors via **git worktree** (barato; sem COW de filesystem).
- Criar/destruir um *floor* = worktree + branch real por agente/experimento.
- **Lifecycle hooks** (Setup/Run/Teardown) com env vars (`MAESTRO_FLOOR_*`).
- **Merge preview**: diff stats + detecção de conflito antes de integrar.
- *Saída:* rodar 2 agentes em branches isoladas sem conflito; revisar e integrar.

### 👥 Fase 3 — v0.9.0 · "Roles & Notes"
- **Roles ricos**: `role.json` (nome, cor/badge, prompt) + `CLAUDE.md`/`AGENTS.md` por subdiretório; badge de cor por papel no nó.
- **Sticky notes** no canvas + **agent-to-note** (nota persistente que o agente lê/escreve via cabo).
- *Saída:* montar um time com papéis visuais + uma nota compartilhada de contexto entre eles.

### ⏰ Fase 4 — v0.10.0 · "Routines"
- Prompts **agendados** (intervalo) num agente; multi-step sequencial (`&&`).
- Pause/resume/edit/delete + histórico com contagem de execuções.
- Reusa orchestrator + timer leve.
- *Saída:* uma rotina "rodar testes a cada N min e reportar".

### 🔔 Fase 5 — v0.11.0 · "Observabilidade & UX"
- **Attention/notificações**: realce visual + aviso quando agente fica `NEEDS_INPUT`/`BLOCKED` ("o que precisa de você").
- **Command palette** (fuzzy) p/ navegar agentes/teams/arquivos.
- **Backup & Restore** (export/import do estado).
- **Temas de terminal** (paleta VTE: Dracula/Catppuccin…).
- (Opcional) integrar **fila/batch** já existente para parallel requests.

### 🌐 Fase 6 — futuro/opcional · "Pesados" (avaliar no hardware)
- **Portals**: browser embutido controlável por agente via **WebKitGTK** — só se o uConsole aguentar.
- **Ombro**: companheiro IA. Em vez de LLM local pesado, avaliar **reusar `claude -p`/`codex exec`** como "ombro" sob demanda (resumir/avisar), evitando carregar modelo local em 3.7 GB.
- **Diff viewer / git no file tree**, file editor embutido — se houver demanda real.

---

## 3. Recomendação de priorização

1. **Fase 1 é a que mais aproxima do Maestri** (cabos que conversam) e aproveita 90% do motor já pronto → melhor relação valor/esforço.
2. **Fase 2 (Floors)** é o segundo maior salto de valor para dev real, e é leve no Linux (worktree).
3. Fases 3–5 são incrementos leves de UX/colaboração — bom para amadurecer antes de publicar na comunidade.
4. Fase 6 fica explicitamente **adiada/condicional** ao orçamento de RAM do uConsole.

> **Decisão sua (foundation):** confirmar a ordem das fases, ou repriorizar. Sugestão padrão: seguir 1→6 na ordem acima.
