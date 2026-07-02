# Ideias / Backlog — maestro console

> Doc VIVO (não point-in-time): fila de ideias que surgem NO MEIO de outras tarefas. Regra de
> processo (ver `AGENTS.md`): ideia nova → discussão rápida (vale a pena?) → **1 entrada aqui** →
> continuar a tarefa atual sem interromper. Nada aqui vira código até o usuário puxar da fila
> explicitamente e virar um plano de verdade (estilo `docs/14`).

## Como usar

1. Ideia nova surge enquanto outra coisa está em andamento → **não implementar na hora**.
2. Discutir em 2-3 frases: o que é, por que, trade-off principal.
3. Registrar 1 entrada nesta fila (data + 1-2 linhas) — status inicial 🧊.
4. Continuar a tarefa que estava em andamento.
5. Quando o usuário quiser trabalhar numa ideia da fila: promover pra um doc de plano próprio
   (`docs/NN-...md`, mesmo formato do `docs/14`) e seguir o protocolo normal (analisar→pesquisar→
   validar→codar). Atualizar o status aqui pra 📋 (linka o doc do plano) e depois ✅ (linka o PR).

**Status:** 🧊 icebox · 🔬 em pesquisa · 📋 planejada (virou doc próprio) · ✅ entregue (link do PR).

## Quando revisar a fila (proativo, não só quando pedido)
O assistente deve **sugerir** (não decidir sozinho) revisar a fila nestes momentos naturais:
- **Fim de fase/feature** — quando todos os PRs de um plano (estilo `docs/14`) fecham/mergeiam.
- **Marco de release** — ao publicar uma versão (bump + tag).
- Quando o usuário perguntar "o que vem depois?"/"o que fazer agora?" sem ideia específica.
Fora esses pontos, a fila fica parada — não interromper uma tarefa em andamento pra revisá-la.

## Fila

### 2026-07-02 — Paralelizar implementação de features independentes com sub-agentes
Usar o `Agent` tool (`isolation: "worktree"`, cada sub-agente numa cópia isolada do repo) ou o
`Workflow` tool (fan-out mais estruturado, só com pedido explícito do usuário) pra implementar
VÁRIAS features/fases independentes ao mesmo tempo — cada uma vira seu próprio PR — em vez de
sequencial (como fizemos com as Fases C e D da orquestração de equipe). Só funciona bem se as
tarefas forem **genuinamente independentes** (sem PR encadeado); se uma depender da outra, o
paralelismo vira ilusão e o certo continua sendo sequencial. Status: 🧊 icebox.

### 2026-07-02 — Checklist de "hora certa" pra encerrar a sessão + recap via BMad na sessão nova
Formalizar um checklist prático de QUANDO fechar a sessão atual (evitar contexto grande demais) em
vez de tentar medir tokens diretamente (o assistente não tem esse número exato) — usar sinais
indiretos: (a) feature/PR atual fechou (checkpoint natural, já usado pra sugerir revisão da fila
— ver seção acima), (b) a conversa já sofreu 1 auto-compactação (sinal de que já está grande),
(c) troca de tema grande (ex.: terminar uma fase e começar outra não-relacionada). Na sessão NOVA,
rodar um passo de "recap" no início — reaproveitar `bmad-help` e/ou ler os doc-âncora
(`docs/STATUS.md`, `CHANGELOG.md`, o `docs/NN-plano-*.md` da feature em andamento) — em vez de
confiar só na memória automática. Trade-off principal: um checklist manual exige o usuário (ou o
assistente) notar os sinais e agir; não tem gatilho automático de "contexto grande" hoje. Status:
🧊 icebox.

### 2026-07-02 — F1 (medidor de custo/tokens + budget) NÃO é só feature pausada: é controle de segurança do ADR-17 sem implementação
Achado da revisão adversarial do Fable 5 (2026-07-02) sobre `docs/16`. O F1 (parser/ledger já
existem no PR #9, pausado em ~26/06 por "não vi valor") ganhou um argumento novo que a pausa não
considerava: o **ADR-17 (Etapa 3) lista "budget por CUSTO REAL de tokens" como controle de
segurança OBRIGATÓRIO do Maestro mode**, mas o `STATUS.md` lista a feature como "reservada/não
entregue" → um controle declarado no modelo de segurança está como promessa sem implementação.
E a pausa (~26/06) é **anterior** ao ADR-17 (30/06) e ao Maestro mode virar real — com agentes
recrutando agentes, custo às cegas deixou de ser dashboard e virou guardrail. Nuance: provável que
exista teto-proxy por contagem de agentes (fleet-cap); falta o budget por custo real (o próprio
ADR-17 chama contagem de agente de "teatro parcial"). Também é a dor #1 da categoria (`docs/08`),
ausente no Maestri. Trade-off: reabrir contradiz a decisão de pausa do usuário — por isso fica no
backlog, não promovido. Status: 🧊 icebox (candidato forte a retomar o PR #9).

### 2026-07-02 — Revisar docs/10 (roadmap): sobreposição Floors↔Fase 7-A4 + kanban (Fase 5-A2) como cargo-cult
Achado do Fable 5 (2026-07-02). (a) A **Fase 7 "A4 — worktree por nó"** parece **já parcialmente
entregue**: o `STATUS.md` lista *Floors = git worktree por agente + merge preview* como feito, mas
o `docs/10` só marca as Fases 1-3 como defasadas e não sinaliza essa sobreposição → re-escopar ou
riscar o A4. (b) O **kanban de sessões (Fase 5-A2)** é provável cargo-cult de SaaS/time grande
(Nimbalyst/Windsurf) — dev solo com meia dúzia de nós numa 1280×720 já vê os estados no canvas;
candidato a cortar. Contraste: a **Fase 4 (steering + timeline) o Fable endossou** como
prioridade certa (casa com "controlar sessão longa + nudge", `docs/08`). Status: 🧊 icebox
(revisão de doc, não feature).

### 2026-07-02 — Antes de aprofundar o líder-de-grupo (delegate-mode/"ondas"), testar via PROMPT primeiro
Achado do Fable 5 (2026-07-02), reforça o que a pesquisa (`docs/16`) já apontava: o datapoint mais
forte (compilador Anthropic, confirmado 3-0) **não tinha manager central** — agentes escolhiam a
própria tarefa via lock de arquivo; e `docs/02` diz que codificação acoplada não ganha com
multi-agente + o padrão manager hierárquico falha no CrewAI. Logo, aprofundar o líder (ex.: "ondas"
do Kiro, delegate-mode com mailbox) **dobraria a aposta no padrão que a própria pesquisa desafia**.
Saída barata antes de escrever orquestração nova (lição Beast Mode, `docs/16` §5, 3-0): ajustar o
comportamento do líder **só via prompt** e medir. Status: 🧊 icebox (regra de cautela, não tarefa).
