# Roadmap por fases — ideias escolhidas (catálogo docs/09)

> ⚠️ **PARCIALMENTE DEFASADO.** As **Fases 1-3** (descoberta/velocidade, geometria, organização —
> minimapa, grupos, grid, notas) **já foram entregues** (v0.19→v0.23); são apresentadas aqui como
> futuras. As **Fases 4-7** (steering, timeline, diff/commit, kanban, escala, blocos Warp) seguem
> válidas/futuras. Estado real: [`STATUS.md`](STATUS.md) e `CHANGELOG.md`.

> Data: 2026-06-26 · PT-BR · Critério de ordem: valor alto × esforço baixo primeiro;
> dependências respeitadas; pesados (engenharia/VTE) por último. Workflow: **PR-por-fase**,
> cada fase no processo benefícios → plano → busca rápida → implementação → PR.
> Contexto: hardware migrando p/ **CM5 16GB** → A3/A4 viáveis (ver memória).

## Fase 1 — Descoberta & velocidade (UX de teclado, leve)
- **B2** Barra que ensina atalhos (rodapé contextual por modo).
- **D1** Paleta de comandos com fuzzy (turbinar o Ctrl-P; ações + atalhos + recentes).
- **E3** Status proativo no card ("● claude · editando arquivo").
> Maior salto de "sei o que fazer / sei o que está acontecendo" com menor risco.

## Fase 2 — Geometria do canvas
- **C3** Grid de pontos + snapping (imã ao soltar/redimensionar).
- **C5** Cabos curvos (bezier) **ancorados à geometria do C3** (curva alinha ao grid) + cor por estado.
> C5 SEGUE C3 (decisão do usuário): mesma geometria. C3 entra primeiro/junto.

## Fase 3 — Organização do canvas
- **C1** Minimapa (overview + clique navega).
- **C2** Grupos/áreas (retângulo rotulado que move os nós juntos).
- **C4** Notas reforçadas (cor escolhível + fixar/pin).
> Domar canvas cheio numa tela 1280×720.

## Fase 4 — Controle de sessões longas (observabilidade)
- **E1** ⭐ Steering: pausar / cutucar / corrigir agente em execução (via ask bus existente).
- **E2** Timeline de atividade por nó (iniciou → perguntou → editou → terminou).
> Controlar/corrigir rumo sem matar a sessão; diagnóstico rápido.

## Fase 5 — Fluxo de trabalho com agentes
- **A1** Diff/review por agente + comitar (git no workspace do nó).
- **A2** Kanban de sessões (colunas por estado, reusa idle/busy/blocked/done).
- **B4** Snippets/prompts salvos (gaveta reutilizável; evolui as routines).
> "Less typing, more directing": revisar e dirigir o trabalho dos agentes.

## Fase 6 — Escala (aproveita o CM5 16GB)
- **A3** Espalhar 1 tarefa p/ N agentes ("manager view" / preset de time enxuto), teto configurável.
- **B3** Floating pane / scratchpad (terminal sobreposto, descartável).
> Viável com o CM5; rodar um time de verdade em paralelo.

## Fase 7 — Pesados (engenharia avançada, por último)
- **B1** Blocos de comando (Warp-like) — depende de integração de shell OSC 133 no VTE.
- **A4** Worktree git por nó — isolamento real por branch; mexe na engine.
> Maior custo de implementação; hardware (CM5) deixa de ser bloqueio.

---

## Reservado (não descartado)
- **F1 — Medidor de custo/tokens** (PR #9, parser+ledger prontos): usuário não viu valor agora;
  fica em pausa, pode voltar como item de dashboard junto da E2 (timeline).
