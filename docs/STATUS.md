# Estado atual — maestro console

> Doc-âncora de "o que existe HOJE". Atualizado: **2026-07-01 · v0.46.0**.
> **Fontes de verdade canônicas:** [`CHANGELOG.md`](../CHANGELOG.md) (histórico completo
> v0.1.0→v0.46.0) e [`docs/ADR.md`](ADR.md) (decisões, ADR-1..20). Este arquivo resume o
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

### Editar Terminal (Fases 1–6, v0.38→v0.45)
- Diálogo "⚙ Editar Terminal" (abas **Detalhes / Aparência / Agente**): fonte, cor, ícone (Lucide),
  tema por-nó (66 esquemas iTerm2), comando/cwd/env, atalho automático (Ctrl+N), **monitorar
  atividade** (dot + som), **papéis por terminal** (biblioteca + injeção em bloco marcado no
  workspace isolado) + hardening defensivo (respawn state-machine, pidfd, `--unshare-pid`).

### Maestro mode SEGURO + auto-aprovação (v0.45–v0.46) — ADR-16..20, ver [`docs/13-maestro-mode.md`](13-maestro-mode.md)
- **Maestro mode**: um agente vira **manager** e recruta/conecta/dispensa outros via `maestri`.
  Feature original (diverge do Maestri, que é só-humano) — ADR-16.
- **Segurança (autoridade no host):** identidade por **socket por agente** (anti-spoofing), **kill-switch**
  que ceifa a subárvore, tetos por linhagem + rate-limit + HITL, **HUD + auditoria + anomalia→kill-switch**,
  autoridade por linhagem (não pelos cabos), anti-DoS do socket. Provas de runtime viraram `tests/*_live.py`.
- **Auto-aprovação** (ADR-19): Maestro mode / toggle "Permissão total" por nó → o CLI roda sem prompts
  (o bwrap é o confinamento). **Cabo por headless** por padrão (ADR-20): resposta completa + contexto.

## O que NÃO está feito (lacunas conhecidas)
- **Medidor de custo/tokens + teto de orçamento** — diferencial-âncora de `docs/08`; parser/ledger
  existem (PR #9) mas a feature de produto está **reservada/não entregue** (F1 em `docs/10`).
- **Rodar agente direto pela nota** — removido temporariamente na v0.37 (método `_run_note` fica).
- **Hardware CM5** — planejado (16GB); device atual é **CM4** (ver `docs/uconsole.md`).
- Fases 4–7 do roadmap de canvas (`docs/10`): steering, timeline, diff/commit por agente,
  kanban, snippets, escala N-agentes, blocos Warp, worktree-por-nó — em aberto.
- **Risco residual do Maestro mode (ADR-17, aceito):** proveniência/tainting de conteúdo,
  validação semântica plena e **egress allow-list de rede** — adiados, com controles
  compensatórios (caps + kill-switch + HITL + auditoria).
- **SSH remoto (Fase 7 do Editar Terminal)** — ainda não iniciado.

## Stack / device
- **Linux aarch64** (Kali) no **ClockworkPi uConsole / CM4**; **Python ≥3.11**.
- Canvas: **GTK4 + VTE-gtk4** (PyGObject), python do sistema. Engine: venv.
- **495 testes** (pytest) + live opt-in (bwrap: socket-em-sandbox, drill do kill-switch); lint **ruff**.

## Como navegar a documentação
- **Estado atual:** este arquivo. · **Histórico de versões:** `CHANGELOG.md`. · **Decisões:** `docs/ADR.md`.
- **Índice de todos os docs (o que é atual vs histórico):** `docs/index.md`.
- **Planejamento original do MVP** (PRD/arquitetura/epics): `_bmad-output/` (congelado) +
  cópias versionadas em `docs/prd.md` / `docs/architecture.md`.
