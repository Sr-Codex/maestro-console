# Estado atual — maestro console

> Doc-âncora de "o que existe HOJE". Atualizado: **2026-07-12 · v0.65.0**.
> Recente: **v0.65.0** — briefing persistente por GRUPO (`docs/30`, ADR-27): objetivo atual +
> brief editados no diálogo do grupo (host-only, sanitizado, cap 1000/80) e entregues por bloco
> marcado em CLAUDE.md/AGENTS.md do workspace de cada agente que NASCE no grupo (FAB pelo ponto
> do clique · recruit herda do manager · montar equipe com `description` do template como
> semente) — o CLI lê no start; headless e reattach cobertos de graça; re-carimbo a cada
> respawn desfaz rabisco de agente. Grupo de nascimento = decisão host (`birth_group`), nunca
> geometria. (v0.64.0 = budget cap pausa/retomada, PR #77.)
> **v0.63.0** — cápsula contextual de GRUPO (`docs/28`, fecha a conformidade do
> AGENTS.md): selecionar grupo (1 clique na faixa) → outline cairo tracejado + cápsula
> `[⚙][●][🗑]`; apagar grupo passa SEMPRE por confirmação; **hierarquia de cápsulas** (regra
> nova de design: FAB > pílula > popover — popovers de cor do grupo E da nota em nível 3).
> Revisado pelo Fable (9 emendas); validado no device.
> **v0.62.0** — UX dos diálogos Nível 2 (`docs/26`, fecha o plano): `_budget_dialog`
> migrado pro helper; helper `_dialog_footer` (rodapé padrão + **Enter→primário** pela API canônica)
> adotado em 7 diálogos form-heavy; scroll opt-in (`_dialog(scroll=True)`) nos diálogos de team.
> Validado por teste visual no device. **v0.61.0** — cor própria do `blocked` (Mocha red `#f38ba8`,
> proposta Fable): separa "bloqueado" do âmbar de `waiting` nas 3 paletas; alinhamento semântico na
> web (que não tinha `waiting` → `NEEDS_INPUT` caía em `blocked`).
> **v0.60.0** — UI do canvas Fase B (`docs/27`): header do card redesenhado em UMA LINHA
> — nome do terminal (com ellipsize) + agente em cápsula de cor fixa à esquerda; custo/token/mem
> em chips separados (some quando vazio) à direita; estado só no dot.
> **v0.59.0** — UI do canvas Fase A (auditoria Fable): fim do tofu na FAB,
> ✕ fechar-nó com confirmação, FAB com separadores + kill no fim, paleta com ícone, "enquadrar
> tudo" (⛶ + Ctrl+Shift+F). **v0.58.0** — UX dos diálogos Nível 1 (`docs/26`).
> **Fontes de verdade canônicas:** [`CHANGELOG.md`](../CHANGELOG.md) (histórico completo
> v0.1.0→v0.55.0) e [`docs/ADR.md`](ADR.md) (decisões, ADR-1..22). Este arquivo resume o
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

### Orquestração de equipe — Fases A+B+C+D (v0.47.0→v0.51.1), ver [`docs/14-plano-orquestracao-equipe.md`](14-plano-orquestracao-equipe.md)
- **Team Templates** (`engine/team_templates.py`): `TeamTemplate`→`GroupSpec`(+`leader` schema)→
  `AgentSpec`(=`Role`), placeholders (`{projeto}`), persistência atômica, built-ins.
- **`_materialize_team()`**: monta Grupos do canvas + recruta os membros DENTRO de cada um (grid,
  pertinência geométrica), guard-rails (fleet-cap, tamanho de grupo), WYSIWYG, auditado.
- **FAB "🧩 Montar equipe"** (Fase A, humano): lista built-in+salvos, preview, Montar (com
  placeholder), orquestrador opcional (cabo automático), Excluir.
- **`maestri team '<json>'`** (Fase B, agente): manager descreve a equipe em JSON; **confirmação
  humana obrigatória** antes de materializar (`_hitl_team`→`_confirm_team_from_agent`→
  `_apply_team_decision`); autoridade sempre pelo canal (`frm`), nunca por campo do JSON.
- **"Montar equipe" (FAB) segue clique-pra-posicionar** (v0.49.0, generaliza AGENTS.md §5): o
  bloco inteiro da equipe nasce onde o humano clica, com prévia fantasma dimensionada
  dinamicamente (`_team_layout_size`/`_team_group_footprint`) — única exceção que resta é o
  fluxo Fase B (`maestri team`, sem clique humano possível).
- **Editor visual de template** (Fase C, v0.50.0): `_team_edit_dialog`/`_team_group_edit_dialog` —
  criar/editar/duplicar/excluir grupos+membros pela UI (`_save_team_from_staging` valida antes de
  persistir); FAB ganhou "+ Novo template"/"Editar"/"Duplicar".
- **Líder de grupo** (Fase D, v0.51.0): grupo com `leader` vira caixa-preta coordenada por ele
  (orquestrador/T1 ↔ líder ↔ demais membros); sem líder, comportamento anterior inalterado.
  Líder não ganha poder de comando extra nem Maestro mode automático — **corrigido em v0.51.1**
  (revisão adversarial pós-merge achou que a fiação visual (`edges`) para o líder também virava
  autoridade (`_recruited_by`) de fato, dando dismiss/reassign de graça; agora fiação e
  autoridade são separadas — autoridade continua com quem já a tinha antes da Fase D).

### Estado por nó "precisa de você" (v0.52.0), ver [`docs/18-plano-estado-por-no.md`](18-plano-estado-por-no.md)
- **Estados do nó viraram ícones Lucide** pré-coloridos (`maestro-state-*`, reusando o bundle
  Lucide + `STATE_COLORS`) no lugar de glyphs unicode. Estado **"aguardando (é sua vez)"** distinto
  de bloqueado/erro: monitor de quietude + envelope `NEEDS_INPUT` → `waiting` (âmbar, circle-pause).
- **Contador "⚠ N" = união envelope ∪ estado visual** (`attention_nids`): o monitor de quietude
  agora entra na conta e no "pular pro próximo" (Ctrl+Shift+A); o "⚠ N" é **clicável**; o
  **minimapa realça** os nós em atenção com a cor do estado. Monitor com **toggle de som** (OFF por
  padrão — só dot visual).
- **Monitor padrão-ON nos nós-agente** (Bloco 3, v0.53.0): o "aguardando" aparece **sozinho** em
  todo agente (detecção por `kind` do roster; tri-estado da cfg `monitor`; shell fica opt-in pra um
  bash ocioso não virar "waiting" à toa). Som segue OFF por padrão.

### Medidor de custo/tokens por nó — F1 Blocos A+B+C (v0.54.0), ver [`docs/19-plano-medidor-custo.md`](19-plano-medidor-custo.md)
- **Preço vendorizado** (`engine/pricing.json`, subset LiteLLM estático, sem dep do pacote) +
  `cost_from_tokens` (3 baldes de cache). Claude = `total_cost_usd`; Codex = tabela.
- **`on_usage`** no orquestrador acumula o uso por agente no `UsageLedger` (persiste) a cada turno
  headless; **display lean por nó** ($ no header, ao vivo via `usage_bus`). Absorve o PR #9.
- **Budget cap** (Bloco D, v0.55.0, ADR-22): teto de $ que avisa (soft) e barra (hard) o gasto;
  contador monotônico host-side (anti-laundering), barra no `delegate`, HUD + config/reset (botão 💰).

### Unload de nó — liberar RAM no CM4 (v0.56.0, Blocos A′+B+C+D), ver [`docs/21-plano-unload-no-ram.md`](21-plano-unload-no-ram.md) + ADR-23
- **Ciclo completo medir→decidir→descarregar→retomar**, rota kill-and-resume por CAPTURA de
  sessão (Congelar/CRIU descartados; injeção de `--session-id` fixo derrubada pelo Fable).
- **A′ (captura):** JSONL mais novo no dir de projeto exclusivo do nó (`_node_ws`) → chave
  própria `nodecfg_{nid}_session` no `ui_state` (NÃO a tabela `sessions` do F1); limpa no ✕.
- **B (⏏ Descarregar):** cápsula contextual; confirmação sempre (guard `tui_busy` reforça);
  SIGKILL direto (ADR-23: bwrap não repassa SIGTERM) + anti-race do respawn em voo; flag
  `unloaded` persiste ("abre igual fechou").
- **C (Retomar):** clique no terminal morto (hint ensina) ou ⏏ de novo; claude `--resume
  <capturada>`, codex via picker; argv ONE-SHOT (nunca muta `_base_argv`) → **"Reiniciar" =
  do zero**; **startup sem spawn** (nó descarregado nasce sem processo — o maior ganho).
- **D (visibilidade):** badge de RAM por nó (PSS + tooltip com Private; árvore via
  `engine/proc_ram.py` em worker thread, jamais na main loop — revisão Fable §8.5); vista
  "descarregado" derivada (idle+flag → ⏏; sem estado novo na máquina); minimapa cinza;
  **limiar de notificação de RAM configurável** no 💰 "Limites" (histerese 0.9×X anti-flapping).

### Reattach de nós órfãos pós-crash (v0.57.0, R1+R2+R3), ver [`docs/25-plano-reattach-orfaos.md`](25-plano-reattach-orfaos.md) + ADR-25
- **Dor P2** (a mais universal do nicho, `docs/23-24`): crash do app ≠ perder trabalho. Completa o
  ciclo do unload (unload = de propósito; reattach = recuperar de um crash). Plano revisado pelo Fable.
- **R1 (sentinela de crash):** `engine/crash_flag.py` — dirty-flag `ui_state["dirty_run"]` (durável
  via WAL) distingue fechamento limpo de crash; **handler `SIGTERM/SIGHUP → quit`** (correção do
  Fable) impede que logout/desligamento vire falso-crash. Premissa "1 instância" (sem flock).
- **R2 (detecção):** `engine/orphans.py` — no boot, órfão = **crash ∧ agente ∧ ¬descarregado ∧
  transcript-no-disco** → recebe `unloaded=1` (reusa dormência/reload) + flag **`orphan`** própria
  (distingue de descarregado-de-propósito; sobrevive a boots); nasce dormente (RAM zero).
- **R3 (recuperação):** órfão **âmbar** (estado `waiting` → entra no ⚠) com tooltip/hint
  "recuperável"; 3 ações na cápsula — **Reanexar** (⏏ → `--resume`), **Novo agente** (✧, só em
  órfão → do zero, descarta a sessão), **Arquivar** (🗑, preserva o workspace). Todas limpam `orphan`.
- **Fora de escopo (decidido):** R4 (reconciliação de git worktree órfão) — 2º PR/backlog.

## O que NÃO está feito (lacunas conhecidas)
- **F1 completo** (v0.52→0.55): medidor + budget cap entregues. Extensões possíveis: teto por-linhagem,
  estimativa pré-turno, teto de tokens p/ Codex sem preço (ver docs/20 §4).
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
- **554 testes** (pytest, +19 skip; os gi rodam no python do sistema) + live opt-in (bwrap:
  socket-em-sandbox, drill do kill-switch); lint **ruff**.

## Como navegar a documentação
- **Estado atual:** este arquivo. · **Histórico de versões:** `CHANGELOG.md`. · **Decisões:** `docs/ADR.md`.
- **Índice de todos os docs (o que é atual vs histórico):** `docs/index.md`.
- **Planejamento original do MVP** (PRD/arquitetura/epics): `_bmad-output/` (congelado) +
  cópias versionadas em `docs/prd.md` / `docs/architecture.md`.
