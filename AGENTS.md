# Regras do repo maestro console (para IA — Claude/Codex)

Complementa a conduta global (`/home/kali/AGENTS.md`). Aqui ficam as regras ESPECÍFICAS
deste repositório. O fluxo completo está em `CONTRIBUTING.md` — siga-o.

## Fluxo de git/PR (obrigatório — é parte do "feito")
- **Nunca commitar na `main`.** Toda mudança numa branch curta + PR.
- **Branch:** `feat/` (novo) · `fix/` (polimento/conserto) · `docs/` · `refactor/` · `chore/`.
- **1 branch = 1 unidade coerente.** Polimentos do mesmo tema acumulam na mesma branch (1 PR).
  Tema diferente → branch separada. **Sem PR encadeado** (mergeie a base antes, ou tudo numa branch).
- **Commits:** Conventional Commits (`feat(canvas): …`), porquê no corpo.
- **Antes do PR:** `pytest` verde + `ruff` limpo no que tocou + app roda + `CHANGELOG.md` + **1 bump
  de versão por PR** (não por commit).
- **Merge:** via `gh pr merge <n> --squash --delete-branch` (squash; apaga a branch). O merge na
  `main` é decisão do usuário — proponha; ele autoriza/roda (a trava de merge é dele).
- **Release:** tag `vX.Y.Z` (SemVer) só no merge de release, não a cada commit.

## Ideias que surgem no meio de outra tarefa (obrigatório — não interromper o fluxo)
- **Ideia nova durante uma tarefa em andamento → NÃO implementar na hora.** Fluxo: (1) discutir
  rápido (2-3 frases: o que é, por quê, trade-off principal); (2) registrar **1 entrada** em
  `docs/15-ideias-backlog.md` (data + 1-2 linhas, status 🧊); (3) **continuar a tarefa atual sem
  desviar**.
- Só vira código quando o usuário puxar a ideia da fila explicitamente — aí sim: promover pra um
  doc de plano próprio (mesmo formato do `docs/14`) e seguir o protocolo normal (analisar→
  pesquisar→validar→codar).
- *Por quê:* ideias vão surgir o tempo todo numa sessão longa; implementar cada uma na hora quebra
  o foco da tarefa atual e gera trabalho não pedido. Capturar é rápido e não perde a ideia.
- **Sugerir** (nunca decidir sozinho) revisar a fila em pontos naturais: fim de fase/feature
  (todos os PRs de um plano fecharam), marco de release, ou quando o usuário perguntar "o que
  vem depois" sem ter algo específico em mente.

## Persistência de UI (obrigatório — "abre igual fechou")
- **Toda configuração de janela/UI feita pelo usuário DEVE persistir após fechar o app.** Reabrir =
  igual fechou. Vale para qualquer estado/preferência: modo, toggle, layout, escolha visual, tamanho,
  posição, tema, etc. **Proibido deixar estado "só em memória".**
- **Como:** persistir via `CanvasModel` + `Store.get_ui/set_ui` (tabela `ui_state`) — getter com
  default + setter chamado **na mudança**; carregar no `__init__` do canvas. Espelhar o padrão de
  `terminal_theme`/`native_zoom`/roster de terminais.
- É parte do "feito": uma config nova só está concluída quando **persiste e foi testada** reabrindo.

## Cápsulas de UI do canvas (arquitetura — obrigatório)
Padrão de toolbar do canvas nativo, decidido pelo usuário:
1. **Cápsula principal (FAB, topo):** **toda config de software + criação de elementos.** Cada
   feature nova / cada tipo de **nó novo** entra aqui (ex.: novo terminal, nova nota, novo grupo).
2. **Cápsula contextual por elemento:** aparece **ao SELECIONAR** um elemento (1 clique) e mostra as
   **config/ações DAQUELE elemento** (espelha a pílula da nota). **Todo elemento que tiver config
   deve ter a sua cápsula contextual** — generalize o padrão da nota, não crie UI ad-hoc por nó.
3. **Zoom** fica numa **cápsula inferior-esquerda** (rodapé).
4. **Sem menu "☰ ações" global** — as opções se distribuem entre (1) global e (2) por-elemento.
5. **Todo elemento novo criado pela cápsula principal nasce por CLIQUE-PRA-POSICIONAR — nunca
   por algoritmo adivinhando uma posição livre.** Fluxo: escolher o tipo (ex.: terminal/agente/
   nota/grupo/árvore) → prévia fantasma (contorno tracejado, tamanho real do item) segue o
   cursor → o clique no canvas cria ali; Esc cancela. Implementado em `_start_placing`/
   `_commit_placing`/`_draw_placing_preview_cr` (`maestro/native/canvas.py`); tamanho da prévia
   por tipo em `_PLACING_SIZES`. Generalizar esse padrão pra qualquer elemento novo — não criar
   posicionamento automático ad-hoc por feature. *Motivo:* tentar corrigir sobreposição com
   algoritmo (viewport-aware, força posição/tamanho contra id órfão) precisou de 4 rodadas de
   correção e ainda colidia na prática — deixar o humano apontar é simples e sempre certo.
   **Generalizado pra "Montar equipe":** o bloco inteiro da equipe (todos os grupos+membros)
   nasce onde o humano clica — prévia fantasma dimensionada dinamicamente pelo layout do
   template (`_team_layout_size`/`_team_group_footprint`), `origin` propagado até
   `_materialize_team`. **Única exceção que resta (decisão do usuário):** fluxo SEM clique
   humano possível — recrutar por agente via `maestri recruit`/`maestri team` (Fase B,
   confirmação humana mas sem ponto de clique no canvas) — continua com o posicionamento
   automático (`_free_region_origin`), só corrigido pra não herdar posição/tamanho de um id
   reciclado/órfão, sem garantia de zero sobreposição.

## Como rodar/testar
- Testes: `.venv/bin/pytest -q` · Lint: `.venv/bin/ruff check maestro tests`
- Canvas nativo (GTK/VTE): python do SISTEMA, via `./bin/maestro-canvas` (não o `.venv`).
- ADRs versionados em `docs/ADR.md`.
