# Estado atual — maestro console

> Doc-âncora de "o que existe HOJE". Atualizado: **2026-06-29 · v0.37.0**.
> **Fontes de verdade canônicas:** [`CHANGELOG.md`](../CHANGELOG.md) (histórico completo
> v0.1.0→v0.37.0) e [`docs/ADR.md`](ADR.md) (decisões, ADR-1..15). Este arquivo resume o
> estado; em caso de divergência, o CHANGELOG/ADR mandam. Os artefatos em `_bmad-output/`
> são o **planejamento do MVP** (histórico, congelado) — ver [`docs/index.md`](index.md).

## O que está entregue (na `main`)

### Engine (fundação — MVP, Épicos 1–5)
- Runner **headless** (`claude -p`/`codex exec`) + returncode + timeout (asyncio).
- **Orquestrador-mediado** A→B→A (envelope **JSON estrito** validado por schema; retry).
- **SQLite (WAL)** como única camada de estado; **mutex por sessão**; sessões `--resume`.
- **Sandbox bwrap** estrito (workspace rw, `/tmp` privado, resto read-only) — sem bypass.
- Adapters **TOML** declarativos (claude/codex); registry; message bus; task queue.

### Interfaces
- **TUI** (terminal), **Web UI** (aiohttp + SSE, canvas web), e o **canvas nativo GTK4+VTE**
  (carro-chefe — rodado pelo python do sistema via `./bin/maestro-canvas`).

### Canvas nativo (o grosso do trabalho pós-MVP, v0.13→v0.37)
- **Canvas infinito** (modelo câmera; pan por SELECT+trackball; zoom real) — ADR-12.
- **Cabos interativos** (`maestro-ask`, ADR-11) + **modo LIVE** (injeta no terminal vivo, ADR-13).
- **Física do cabo** (corda Verlet / catenária / bezier+mola, Ctrl+Shift+P) — ADR-14;
  ímã de 8 pontos, bolinha nas pontas, fluxo animado no sentido do dado.
- **Notas sticky**: cor/fonte, resize pela borda, cabo nota↔nó (agente lê/escreve a nota),
  **editor markdown in-place** (estilo ao vivo, H1/H2/H3, toggle de formatação, checkbox
  auto-continua, auto-scroll) — ADR-15.
- **Minimapa**, **grupos/áreas**, grid+snapping, **multi-workspace**, file tree, foco rápido
  por teclado, barra flutuante de ferramentas, paleta de comandos (Ctrl-P).
- **Persistência de UI** ("abre igual fechou") — toda config de janela persiste (ADR/AGENTS).

### Outras fases (paridade Maestri)
- **Floors** (git worktree por agente + merge preview), **papéis** (role.json), **routines**
  (prompts agendados), **attention** ("o que precisa de você"), backup/restore.

## O que NÃO está feito (lacunas conhecidas)
- **Medidor de custo/tokens + teto de orçamento** — diferencial-âncora de `docs/08`; parser/ledger
  existem (PR #9) mas a feature de produto está **reservada/não entregue** (F1 em `docs/10`).
- **Rodar agente direto pela nota** — removido temporariamente na v0.37 (método `_run_note` fica).
- **Hardware CM5** — planejado (16GB); device atual é **CM4** (ver `docs/uconsole.md`).
- Fases 4–7 do roadmap de canvas (`docs/10`): steering, timeline, diff/commit por agente,
  kanban, snippets, escala N-agentes, blocos Warp, worktree-por-nó — em aberto.

## Stack / device
- **Linux aarch64** (Kali) no **ClockworkPi uConsole / CM4**; **Python ≥3.11**.
- Canvas: **GTK4 + VTE-gtk4** (PyGObject), python do sistema. Engine: venv.
- **435 testes** (pytest) + alguns live opt-in; lint **ruff**.

## Como navegar a documentação
- **Estado atual:** este arquivo. · **Histórico de versões:** `CHANGELOG.md`. · **Decisões:** `docs/ADR.md`.
- **Índice de todos os docs (o que é atual vs histórico):** `docs/index.md`.
- **Planejamento original do MVP** (PRD/arquitetura/epics): `_bmad-output/` (congelado) +
  cópias versionadas em `docs/prd.md` / `docs/architecture.md`.
