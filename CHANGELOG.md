# Changelog

Todas as versões do **maestro console**. Formato inspirado em *Keep a Changelog*;
versionamento incremental. Datas em 2026.

## [0.19.0] — Descoberta & velocidade (Fase 1: ideias de apps parecidos)
Primeira fase do roadmap de melhorias com identidade própria (não cópia do Maestri),
colhido de apps da categoria (Warp, Zellij, Linear/Raycast) — ver `docs/09`/`docs/10`.
- **B2 — Barra que ensina atalhos (estilo Zellij):** rodapé que mostra os atalhos do
  modo atual; ao entrar no modo conectar, troca para "clique na ORIGEM → no DESTINO ·
  Esc cancela". Mata o "não sei os atalhos".
- **D1 — Paleta de comandos turbinada (estilo VS Code/Linear/Raycast):** o Ctrl-P agora
  lista AÇÕES do app (novo terminal, conectar, workspaces, notas, floors, routines,
  próxima atenção…) além da navegação por entidades, com **fuzzy** e o **atalho exibido
  à direita** (ensina enquanto usa).
- **E3 — Status proativo no card:** rótulo discreto ao lado do título dizendo o que o
  agente faz agora ("trabalhando…", "esperando você", "concluído"), derivado do estado.
- Validado por busca (GTK4 `SearchEntry`/`Popover`) + probe ao vivo. Suíte: 370 testes.

## [0.18.0] — Foco rápido por teclado entre terminais (Fase A.2)
- **Ctrl+Shift+1…9** foca o terminal N (número discreto no cabeçalho, renumerado ao
  adicionar/fechar). **Ctrl+Shift+A** pula pro próximo terminal que precisa de você
  (atenção), ciclando a partir do foco atual. Centraliza o card + dá foco ao terminal.
  Usa Ctrl+Shift (livre) em vez do Shift+A/segurar-número do Maestri (que roubariam
  teclas do terminal).
- Encerra o roadmap de paridade com o Maestri das fases leves (A, A.2, B, C). Pesados
  (Portals, Maestro Mode, diff/git) e **Ombro** (IA local) ficam fora por decisão.
- Suíte: 366 testes.

## [0.17.0] — UX do terminal, árvore de arquivos e multi-workspace (paridade Maestri)
- **Fase A — UX do terminal:** **Ctrl+Shift+W** fecha o terminal em foco; **duplo-clique no
  título** renomeia (persistido). Terminal já vira shell ao sair da IA (v0.16.0).
- **Fase B — Árvore de arquivos (File Tree):** menu ☰ → 📁 cria um nó navegável dos arquivos
  do projeto (lazy-load por pasta; clicar num arquivo copia o caminho). Raiz = projeto do
  workspace ou `$HOME`.
- **Fase C — Multi-workspace:** ☰ → 🗂️ workspaces (listar/criar/abrir). Cada workspace tem
  estado **isolado** (DB próprio); o `default` preserva o estado legado. Abrir = relança o app
  no workspace (`os.execv`). O File Tree enraíza no projeto do workspace.
- Base da auditoria de comportamento do Maestri em `docs/06`. **Ombro** (IA local) e demais
  pesados (Portals/Maestro Mode/diff-git) ficam para o futuro.
- Suíte: 366 testes.

## [0.16.0] — Cabos interativos (agentes que conversam) + novo terminal
- **Cabos interativos (`maestro-ask`, ADR-11):** ligue um cabo entre dois terminais e
  um agente CONSULTA o outro com `maestro-ask <nó> "<prompt>"` — roteado pelo motor
  MEDIADO (headless + bwrap + envelope), e a resposta volta no terminal. Skill instalada
  no workspace (CLAUDE.md/AGENTS.md); guardrails contra *echoing* (limite de turnos por
  par, refresh de identidade, anti-loop), calibráveis por env (`MAESTRO_ASK_*`). Mailbox
  de arquivos via `shared_paths`; cliente stdlib no PATH do sandbox.
- **➕ novo terminal em runtime:** menu ☰ ações → ➕ cria um terminal **shell** OU uma
  **nova instância de agente** (claude/codex) que participa de cabos.
- **Terminal vira shell ao sair da IA** (comportamento do Maestri): a IA roda dentro de
  um shell; ao sair (`/exit`, Ctrl-D), o card continua como terminal normal.
- **Conexões:** desconectar sem depender da ordem dos cliques; removida a auto-conexão
  por ordem (terminal não nasce mais conectado).
- **Docs:** pesquisa de cabos interativos (`docs/05`) + especificação de comportamento
  do Maestri e matriz de auditoria do clone (`docs/06`). ADRs 10/11.
- Suíte: 355 testes.

## [0.15.0] — Redimensionar cards no canvas (por nó)
- **Redimensionar terminais arrastando a alça ⤡** no canto inferior-direito de cada
  card. O ajuste muda o tamanho **real** do terminal (`set_size_request`), então o VTE
  reflui as colunas/linhas e o PTV do agente (SIGWINCH) — mais espaço de verdade, não
  só ampliação. Tamanho **por card**, com piso 240×120, **persistido** (volta igual ao
  reabrir). Ortogonal ao zoom (zoom = escala visual do plano; tamanho = alocação real).
- **Cabos** passam a conectar nas bordas reais de cada card, suportando tamanhos
  diferentes (`cable_segments` agora recebe boxes `(x,y,w,h)` por nó); `_resize_plane` e
  `_center_on` também respeitam o tamanho por nó.
- Persistência via `CanvasModel.node_size`/`set_node_size`. Suíte: 319 passed; resize
  verificado em runtime (tamanho/terminal/clamp/persistência).

## [0.14.1] — Guard idempotente do on_activate (W5)
- **`on_activate` idempotente:** numa 2ª ativação do `Gtk.Application`, a janela
  existente é trazida à frente em vez de reconstruir `controller`+`store` — evitando
  vazar a conexão SQLite anterior (fechada só no `shutdown`). Defesa em profundidade;
  inalcançável hoje (`NON_UNIQUE`, sem `app.activate()`/D-Bus). Fecha o último deferred
  do code review do canvas GTK4. Suíte: 317 passed.

## [0.14.0] — Fechar nós/notas + atalho do modo conectar
- **Botões ✕ de fechar:**
  - **Nó-terminal:** ✕ no cabeçalho fecha o terminal nesta sessão — remove o widget,
    fecha o PTY do agente (SIGHUP) e limpa o tracking (`terms`/`frames`/`order`/
    `_base_pos`). Cabos para nós ausentes já são ignorados no desenho, então não sobra
    cabo solto. Posição/cabos persistem no Store → relançar restaura o nó.
  - **Nota:** ✕ apaga a nota de vez (`Notes.delete`, persistente) e remove o widget.
- **Atalho do modo conectar — Ctrl+Shift+L:** alterna o modo conectar pelo teclado
  (não usa Esc nem Ctrl-L para não conflitar com o terminal — Esc interrompe a IA,
  Ctrl-L limpa a tela). Esc só cancela o modo quando ele está ativo; sem modo ativo,
  o Esc é repassado ao terminal.
- Verificado em runtime (8/8 checks: fechar nó/nota, terminal removido de `terms`, nó
  vizinho intacto, nota apagada do Store, Ctrl+Shift+L liga, Esc cancela, Esc livre
  quando ocioso). Suíte: 317 passed.

## [0.13.1] — Consertos do code review do canvas GTK4
- **W1 — plano dinâmico:** o plano agora cresce (`_resize_plane`) para caber nós/notas
  no zoom atual; antes, arrastar um nó para longe e dar zoom o jogava para fora da
  área rolável (inacessível). `_center_on` passou a centralizar no **centro** do nó
  escalado (antes mirava o canto superior-esquerdo e era clampado).
- **W2 — Esc fecha diálogos:** diálogos modais (paleta Ctrl-P, floors, routines) fecham
  com Esc (o GTK4 não dá isso de graça como o antigo `Dialog.run`). Escopo modal — não
  interfere no Esc dentro do terminal.
- **W4 — falha de spawn visível:** `make_terminal` trata o callback de `spawn_async`
  (antes `None`): falha ao iniciar o agente (fora do PATH, bwrap ausente, argv inválido)
  agora é logada e avisada no próprio terminal, em vez de deixar o nó em branco e mudo.
- **P3:** `to_display` usa `round()` (arredondamento sem viés) em vez de `int()` (que
  truncava em direção à origem).
- **P1:** `to_base` trata zoom negativo (o `or` só capturava `0.0`).
- Testes: suíte em **317 passed**; novos casos para o guard de zoom negativo e round vs int.

## [0.13.0] — Canvas GTK4 + zoom real do plano
- **Migração do canvas nativo de GTK3/VTE-2.91 → GTK4/VTE-3.91.**
- **Zoom real do plano infinito** via `Gsk.Transform` (escala visual dos terminais
  sem mexer na alocação do widget — grid colunas×linhas e PTY do agente ficam
  intactos), no lugar do `set_font_scale` do GTK3. Coordenadas-base independentes
  do zoom (`to_display`/`to_base`); posições persistidas em coords-base.
- **Fix:** zoom e arraste não resetam mais a posição de nós/notas para o canto
  superior-esquerdo. No `Gtk.Fixed`, posição (`put`/`move`) e `set_child_transform`
  dividem o mesmo slot de transform — então um `scale` puro apagava a translação.
  Agora translação+escala vão num **único** transform e `_base_pos`/`_note_base`
  são a fonte de verdade da posição (sem depender de `get_child_position`).
- `doctor.sh` e README atualizados para as deps GTK4 (`gir1.2-gtk-4.0`,
  `gir1.2-vte-3.91`, `libvte-2.91-gtk4-0`).

## [0.12.0] — Lapidação (polish/hardening)
- **Polish/hardening** do que já existe (sem nova feature de produto):
  - Correção de bugs da revisão adversarial: **deadlock** de `asyncio.Lock` entre
    event loops (orquestração nativa agora usa um loop compartilhado); exceções de
    thread não são mais engolidas; HEAD destacado no merge de floor; `resume_chain`
    robusto; sem leak no attention; drain concorrente de stdout/stderr no runner.
  - `doctor.sh` checa canvas (gi/GTK/VTE), `notify-send` e `git`.
  - Toolbar do canvas descongestionada (menu **☰ ações** + tooltips).
  - README reescrito + este CHANGELOG.

## [0.11.0] — Observabilidade & UX (Fase 5)
- **Attention** "o que precisa de você": realce/contagem de agentes em
  BLOCKED/FAILED/NEEDS_INPUT + notificação de desktop opcional.
- **Command palette** (Ctrl-P): busca fuzzy sobre agentes/teams/floors/notas/routines.
- **Backup & Restore** de todo o estado em JSON (`maestro backup`/`restore`).
- **Temas de terminal** (default/dracula/catppuccin/gruvbox), persistidos.

## [0.10.0] — Routines (Fase 4)
- Prompts **agendados** multi-step (`&&`), mediados; scheduler in-app (`serve` +
  tick no canvas); CLI `maestro routine`; painel de routines no canvas.

## [0.9.0] — Roles & Notes (Fase 3)
- **Papéis ricos**: cor/badge + `role.json` + `CLAUDE.md`/`AGENTS.md` no workspace.
- **Notas** colaborativas no canvas + **agent-to-note** (a nota alimenta o agente
  e a resposta volta para a nota). Badges de papel nos nós.

## [0.8.0] — Floors (Fase 2)
- Ambientes isolados via **git worktree** (branch `floor/<nome>`); rodar agente num
  floor (sandbox); **lifecycle hooks**; **merge preview** + integração; CLI
  `maestro floor` e painel no canvas.

## [0.7.0] — Cabos que conversam (Fase 1)
- Conectar agentes A→B por **cabo** no canvas e disparar **handoff mediado**
  (envelope + bwrap); nós e cabo coloridos por estado; cabos persistidos.

## [0.6.0] — App nativo GTK+VTE *(sem tag)*
- **Canvas nativo** na tela do dispositivo: terminais reais (VTE) num plano
  infinito (pan/zoom), cabos de rota, "rodar time" refletindo estados.

## [0.5.0] — Canvas web ao vivo *(sem tag)*
- Terminais read-only ao vivo (streaming → SSE) + canvas infinito (pan/zoom) na Web UI.

## [0.4.0] — Web UI controlável + canvas visual
- `maestro web` (aiohttp + SSE): executar/cancelar/retomar teams, canvas SVG de
  agentes/handoffs, segurança (bind local, token, CORS).

## [0.3.0] — Robustez + gestão de teams
- CRUD de teams na TUI; continuidade real do Codex (captura de session-id);
  recuperação de cadeia (checkpoint/resume/swap/reprompt); dashboard ao vivo.

## [0.2.0] — Orquestração multiagente pela TUI
- `Teams`/`Roles`, `run_team` com progresso por etapa, dashboard, cancelamento
  seguro, observabilidade via tmux.

## [0.1.0] — MVP
- Engine: runner headless, sandbox bwrap, sessão+mutex, envelope JSON estrito,
  orchestrator (handoff A→B→A), SQLite (WAL), TUI, observabilidade tmux.
