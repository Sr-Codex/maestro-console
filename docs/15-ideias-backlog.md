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
