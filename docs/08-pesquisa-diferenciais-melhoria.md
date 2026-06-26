# Pesquisa de diferenciação — superar o Maestri (feedback real + categoria)

> Data: 2026-06-26 · PT-BR · Fontes: reviews/feedback do Maestri (Setapp, Product Hunt,
> agent-finder) + dores da categoria (orquestração de agentes, coding com IA) + tendências
> de UX 2026. Objetivo: NÃO copiar o Maestri — fazer melhor, com identidade própria, no
> contexto Linux/ARM/GTK4 open-source (uConsole), dev solo, engine já existente.

## Feedback REAL sobre o Maestri (dores → nossas oportunidades)
| Dor relatada por usuários | Fonte | Nossa oportunidade |
|---|---|---|
| **macOS-only** (exclui Windows/Linux) | reviews | já somos **Linux/ARM** — diferencial nato |
| **Teclado trava no meio da sessão** com vários terminais → perde trabalho | Setapp | robustez de input = confiabilidade |
| **RAM altíssima** (até **20 GB** com vários Claude Code) | reviews | somos **leves** (headless+bwrap+teto de agentes) |
| **Workspace trava / UI não responde** | reviews | confiabilidade |
| **Handoff só ~70% automático** (ainda gerencia na mão) | agent-finder | nosso handoff **mediado** (envelope/returncode) é mais confiável |
| **Agentes remotos (Raspberry Pi via LAN) difíceis de configurar** | reviews | nós **rodamos num Pi** → agentes remotos/SSH first-class |
| **Sem cloud sync** (backup manual de ~/.maestri) | reviews | temos backup/restore → export/sync fácil |
| **Delegação inconsistente** (cria sub-agente em vez de delegar) | reviews | nossos **cabos explícitos** são mais claros |

## Dores da CATEGORIA (orquestração/coding com IA) — grandes oportunidades
- **Custo/tokens "às cegas"**: sessões agênticas têm custo quadrático (no passo 20 paga o
  contexto 20×); ninguém atribui gasto. *(Vantage, Finout, Stevens)* → **medidor de custo**.
- **Loops/retries** queimam tokens (10 ciclos = 50× tokens). → **guardrails visíveis** (já
  temos nos cabos).
- **Teto de orçamento/turnos** (Claude Code tem `--max-budget-usd`/`--max-turns`; usuários
  querem isso à mão). → **budget cap com medidor**.
- **Perda de estado no crash** / retomar sessão. → **resume robusto + checkpoints**.
- **Observabilidade fraca** (não veem o prompt; querem **controlar sessão longa e injetar
  nudge/correção**). *(forum)* → **painel + nudge ao vivo**.

## UX / identidade (tendências 2026)
- *"Terminais de IA são quase idênticos (dark, monoespaçada); quem tratar o terminal como
  AMBIENTE DESENHADO, não 'uma caixa que renderiza texto', ganha o 'quero abrir esse app'."*
- **Per-session theming/identidade** (perde-se a noção de qual sessão é qual após 3–4). →
  cor/nome por agente (temos badges/roles/rename — reforçar).
- **Keyboard-first + paleta de comandos** poderosa (Kitty/Zellij elogiados; temos Ctrl-P).
- **Worktree por tarefa + diff review + preview** (Nimbalyst, Claude Squad). → temos floors;
  **diff review** é pedido recorrente.
- **Templates/Spaces** (Windsurf Agent Command Center). → presets de times/agentes.

## 🌟 Lista priorizada (DIFERENCIAIS = onde ganhamos)
1. **Medidor de custo/tokens por agente+sessão, com teto (budget) e alerta.** 🟢 viável (a
   engine roda os agentes → dá pra capturar uso). Resolve a dor #1 da categoria; **Maestri
   não tem.** ⭐⭐⭐ *(headline differentiator)*
2. **Confiabilidade & leveza como bandeira:** handoff mediado confiável + bwrap + baixa RAM +
   input robusto (Maestri trava). Surface isso na UI/README. ⭐⭐⭐
3. **Linux/ARM/open-source + agentes remotos/LAN first-class.** ⭐⭐⭐
4. **Observabilidade + nudge ao vivo** (ver estado/contexto; injetar correção em sessão
   longa). ⭐⭐
5. **Guardrails visíveis (anti-loop/turnos) + budget cap** aplicados também aos runs. ⭐⭐

## 🎨 UI/UX com SUA identidade (não cópia)
6. **Identidade visual própria** ("app que dá vontade de abrir"): paleta autoral, densidade
   p/ 1280×720, microinterações — ir além do dark genérico (UI-1 foi o começo). ⭐⭐
7. **Identidade por agente** (cor+nome) p/ não confundir sessões. ⭐⭐
8. **Paleta de comandos + keyboard-first** aprofundada. ⭐⭐
9. **Onboarding/empty-state** acolhedor. ⭐

## Paridade (manter): cabos, floors, notes, routines, multi-workspace, File Tree, temas.
## Reavaliar: diff/git review (estava na Fase D descartada — mas é pedido recorrente).

> Veredito: o **diferencial-âncora** é o **medidor de custo/tokens + budget** (dor real #1,
> ausente no Maestri, viável aqui). Combinado com **confiabilidade/leveza** e **Linux/ARM +
> remoto**, dá uma identidade própria — não uma cópia.
