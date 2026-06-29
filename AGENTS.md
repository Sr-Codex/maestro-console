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

## Persistência de UI (obrigatório — "abre igual fechou")
- **Toda configuração de janela/UI feita pelo usuário DEVE persistir após fechar o app.** Reabrir =
  igual fechou. Vale para qualquer estado/preferência: modo, toggle, layout, escolha visual, tamanho,
  posição, tema, etc. **Proibido deixar estado "só em memória".**
- **Como:** persistir via `CanvasModel` + `Store.get_ui/set_ui` (tabela `ui_state`) — getter com
  default + setter chamado **na mudança**; carregar no `__init__` do canvas. Espelhar o padrão de
  `terminal_theme`/`native_zoom`/roster de terminais.
- É parte do "feito": uma config nova só está concluída quando **persiste e foi testada** reabrindo.

## Como rodar/testar
- Testes: `.venv/bin/pytest -q` · Lint: `.venv/bin/ruff check maestro tests`
- Canvas nativo (GTK/VTE): python do SISTEMA, via `./bin/maestro-canvas` (não o `.venv`).
- ADRs versionados em `docs/ADR.md`.
