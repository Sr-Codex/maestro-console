# Contribuindo — fluxo de git/PR (maestro console)

Workflow leve mas profissional (GitHub Flow), calibrado para **solo + assistido por IA**.
Quem trabalha aqui (humano ou IA) segue isto. Versão para IA: ver `AGENTS.md`.

## Princípios
- **Nunca commitar direto na `main`.** Toda mudança passa por uma branch curta + PR.
- **1 branch = 1 unidade coerente.** Polimentos do mesmo tema acumulam na mesma branch (1 PR);
  temas diferentes → branches diferentes.
- **Nada de PR encadeado/dependente.** Se B depende de A não-mergeado: mergeie A primeiro **ou**
  faça tudo numa branch só. Não abra PR de B em cima de A aberto.
- **`main` sempre verde:** testes + lint passam antes do merge.

## Nomes de branch
`feat/<slug>` (novo) · `fix/<slug>` (conserto/polimento) · `docs/<slug>` · `refactor/<slug>` ·
`chore/<slug>` (infra/manutenção). Slug curto em kebab-case.

## Commits (Conventional Commits)
`feat(escopo): …` · `fix(escopo): …` · `docs:` · `refactor:` · `chore:` — imperativo; o **porquê**
no corpo. Vários commits pequenos na branch são bem-vindos (o merge squasha em 1).

## Antes de abrir o PR (checklist)
1. `.venv/bin/pytest -q` verde.
2. `.venv/bin/ruff check maestro tests` limpo (no que você tocou).
3. App roda (`./bin/maestro-canvas` quando for canvas).
4. **`CHANGELOG.md`** com a entrada da versão.
5. **1 bump de versão por PR** (`pyproject.toml`) — NÃO por commit.

## Abrir e mergear
```
git checkout main && git pull
git checkout -b feat/x
# … código + checklist acima …
gh pr create --base main --fill
gh pr merge <n> --squash --delete-branch   # squash = 1 commit limpo na main; apaga a branch
git checkout main && git pull
```
> Merge é feito por **`gh`** (cliques de merge no GitHub web costumam não pegar neste setup).

## Versão e tags (SemVer)
- **MINOR** (`0.X.0`): feature nova. **PATCH** (`0.X.Y`): conserto/polimento. **MAJOR**: quebra.
- **Tag no merge de cada release** (`git tag -a vX.Y.Z -m "…" && git push --tags`), não a cada commit.

## Testes / lint (como rodar)
- Testes: `.venv/bin/pytest -q`  ·  Lint: `.venv/bin/ruff check maestro tests`
- O canvas nativo usa o **python do sistema** (gi/GTK/VTE); rode via `./bin/maestro-canvas`.
- CI (GitHub Actions) roda `pytest` (+ `ruff`) em cada PR como rede de segurança.

## Depois do merge
Apague a branch (`--delete-branch` já faz), sincronize a `main` local, tag se for release.
