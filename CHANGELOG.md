# Changelog

Todas as versões do **maestro console**. Formato inspirado em *Keep a Changelog*;
versionamento incremental. Datas em 2026.

## [0.32.0] — Conectar NOTA por cabo (visual) — Fase 4a
- **Cabo nota↔nó:** no modo conectar (🔌 / Ctrl+Shift+L), clicar em **qualquer área** de um nó ou
  **nota** liga o cabo (usa `_elem_at`); `_connect_pick` generalizado p/ `(kind, id)`. O bezier é
  desenhado até a nota (`_cable_box` resolve posição/tamanho de nó ou nota).
- **Limpeza de cabos órfãos:** apagar nó/nota agora remove seus cabos do store (`_remove_edges_for`)
  — antes ficavam órfãos. Cabo IA↔IA mantém o aviso `maestro-ask`; nota↔nó usa hooks (corpo na 4b).
- Persistência sem migração (edges guardam ids string). Base p/ a 4b (ler/escrever + ciência do agente).

## [0.31.0] — Nota: ver markdown formatado (toggle "M") — Fase 3
- **Botão "M" na pílula** alterna a nota entre **editar** (texto cru com marcadores `**`, `- [ ]`…)
  e **ver** (markdown **renderizado**: negrito, itálico, tachado, código, títulos, listas e
  checkboxes). Antes os marcadores ficavam visíveis como texto.
- Conversor **`md_to_pango`** (em `engine/notes.py`, puro/gi-free, **sem dependência nova**):
  escapa `&<>`, converte blocos (`#`, `- [ ]`/`- [x]`→☐/☑, `-`/`*`→•) e inline
  (`` ` ``→`<tt>`, `**`→`<b>`, `~~`→`<s>`, `*`→`<i>`) p/ markup do Pango.
- O corpo vira um `Gtk.Stack` (páginas **edit** = `TextView` / **view** = `Gtk.Label` com markup);
  cor e fonte da nota valem nas duas. Placeholder some no modo ver.
- Honesto: o modo "ver" é **read-only** (checkbox não clica ali; edita no "editar"); estado do
  toggle em memória (reabre em "editar"); conversor simples (cobre o que a pílula insere).
- **Fix:** a nota agora **seleciona ao clicar em qualquer área** (não só na barra superior) —
  `GestureClick` em fase CAPTURE no frame, espelhando o card de nó.

## [0.30.0] — Resize pela borda (nós e notas, 4 lados + cantos)
- **Redimensionar pelas BORDAS — detecção no nível do CANVAS** (mesmo mecanismo do resize de
  grupo). Ao selecionar um card (borda azul tracejada), o cursor vira o de resize quando entra
  numa **faixa de ~6px em volta da borda — por fora E por dentro** (`_resize_edge_at` via
  `compute_bounds`); arrasta nos **4 lados + cantos**. Arrastar pela borda **superior/esquerda**
  move a posição (borda oposta ancorada). **Sem nada visível** (nenhum widget/alça) e **sem tremor**
  (offset vem do plano, que não se move). Padrão p/ **todos os nós e notas**, existentes e futuros.
- **Nó (terminal):** remove o antigo grip "⤡" do rodapé. Tamanho **e** posição persistem
  (`set_node_size`/`set_position`).
- **Nota:** o **corpo rola** (não cresce). Novas colunas `notes.width/height` (migração idempotente,
  espelha `font`); tamanho e posição persistem; duplicar copia o tamanho.
- Integrado em `_pan_begin/update/end` (com `_resize_rect`/`_item_resize_*`); snap à grade; piso
  nó `240×120`, nota `160×90`. Folga de 3px da linha tracejada preservada.
- **Bug latente corrigido:** `file_to_note` (round-trip agent-to-note) descartava `font` — agora
  preserva `font`/`width`/`height` (além de `color`/`pinned`).

## [0.29.0] — Bloco de nota estilo sticky-note + seletor de cor (Maestri)
- **Nota INTEIRA colorida** (sticky-note): a cor pastel preenche o card todo — frame + corpo —
  com leve transparência. Cabeçalho = só uma **faixa fina superior** (tom que combina e contrasta
  de leve com a cor) p/ **mover** a nota; removidos título, 📌 pin, 🎨 do card, grip "≡" e ✕
  (cor/apagar ficam na pílula). Sem campo de título, a 1ª linha do corpo vira o título.
- **Cor da letra adaptativa:** texto preto em notas claras, branco em notas escuras (luminância);
  placeholder e faixa acompanham a direção do contraste. Mantém tudo legível em qualquer cor.
- **Placeholder "Clique para editar..."** (overlay clicável-através) some quando há texto; cor
  acompanha a tonalidade do card (tom escurecido).
- **Corpo rola em vez de crescer:** `Gtk.ScrolledWindow` de altura fixa + **barra de rolagem
  minimalista** à direita (slider fino, pontas arredondadas).
- **Seletor de cor estilo Maestri (pílula):** botão mostra a **cor atual numa bolinha**; abre um
  **popover escuro** (translúcido, cantos, sombra, seta) com **paleta de 10 cores em círculos**
  (`NOTE_PALETTE`) + **"🎨 Mais cores"** → seletor nativo (`Gtk.ColorDialog`) p/ **cor custom**.
  Cores das notas passam a ser guardadas em **HEX** (`note.color`), aplicadas por **provider CSS
  por-nota** (frame/faixa/corpo/placeholder); back-compat com nomes antigos. **Grupos seguem com a
  paleta `NOTE_COLORS`** (intactos).
- **Botão "Aa" de FONTE:** seletor nativo (`Gtk.FontDialog`) aplica família+tamanho+peso+estilo ao
  corpo; **persistido** em nova coluna `notes.font` (migração idempotente). Duplicar copia cor+fonte.
- **2ª pílula com mais respiro** (spacing 6, padding 3×9).
- Limpeza: import `..engine.notes` reordenado (corrige I001 herdado do PR #22).

## [0.28.0] — Barra de contexto da NOTA (2ª pílula, estilo Maestri) — Fase 1
- **2ª pílula flutuante** que aparece **ao selecionar uma nota** e some ao desselecionar
  (`_update_note_ctx` no `_select`), logo abaixo da barra principal. Espelha o Maestri: ao clicar
  no bloco de notas surge um menu de contexto com as ferramentas DAQUELA nota.
- **Menor que a barra principal** (`.note-ctx-bar`/`.note-ctx-btn`: cantos/padding/botões
  reduzidos) e com **folga vertical** clara em relação a ela (`margin_top=66`).
- Ferramentas (Fase 1): **🎨 cor** (5 presets, reusa `_set_note_color`) · **B / I / S / `</>`**
  (envolvem a seleção com markdown `**` / `*` / `~~` / `` ` ``) · **# heading · ☑ checklist ·
  • lista** (prefixam a linha do cursor) · **⧉ duplicar** · **🗑 apagar**.
- Edição via `Gtk.TextView` do corpo: funções puras `md_wrap`/`md_line_prefix` em
  `engine/notes.py` (gi-free, testadas) + glue GTK (`get_selection_bounds`/`select_range`); salva
  a nota após cada edição. **Markdown source** (marcadores visíveis; render WYSIWYG é Fase 2).
- Fase 2 (depois): imagem, exportar, opacidade/cor custom, toggle de render markdown, fonte,
  conectar por cabo.

## [0.27.0] — Barra flutuante de ferramentas (estilo Maestri)
- **Pílula flutuante no topo-centro** do canvas (`Gtk.Overlay`, igual ao minimapa) com 8 ícones
  line-art (symbolic), inspirada no Maestri. Passo 1: liga ao que já existe e deixa o resto como
  placeholder desabilitado ("em breve").
- Ativos: **▶ executar orquestrador** (`run_team`, azul) · **terminal** (novo terminal) ·
  **documento** (nova nota) · **pasta** (árvore de arquivos) · **Aa** (paleta de comandos).
- Placeholders (em breve): **clipe** (contexto/anexos) · **globo** (web/pesquisa) · **⦸** (autonomia).
- Reusa os callbacks de `_action_spec`; helper `_fab_icon` (symbolic + fallback emoji). A toolbar
  `☰ ações` do topo segue intacta.

## [0.26.1] — Polimento: seleção (borda azul) + entrar/sair de grupo pelo cursor
- **Seleciona clicando em QUALQUER área do card**, não só no cabeçalho (o corpo/VTE
  consumia o clique). Via `Gtk.GestureClick` na fase CAPTURE (não claima — terminal/arraste seguem).
- **Re-clique funciona:** card → clicar fora → card de novo volta a selecionar (antes a seleção
  por foco-enter só disparava em MUDANÇA de foco; re-clicar um card já focado falhava).
- **Folga de 3px** na borda (`outline-offset: 3px`) — a linha tracejada não fica colada no card.
- **Grupos: entrar/sair pelo CURSOR (simétrico).** Item ENTRA no grupo quando o cursor entra
  no retângulo (não só por sobreposição — acabou o "entra rápido" quando ficava um pedaço
  dentro); **Ctrl + arrastar** congela o grupo e o item SAI assim que o cursor deixa a caixa.
  Pertença interativa via `_group_excluded` alternado por cruzamento de cursor (`_group_at_cursor`).

## [0.26.0] — Cabo "estilo Maestri": pergunta digitada no terminal VIVO + captura
- **Modo live (default):** ao perguntar por um cabo (`maestro-ask`), o prompt é **digitado no
  terminal VIVO do agente destino** (`Vte.feed_child`) — você VÊ a pergunta aparecer e o agente
  responde lá, como no Maestri. Antes era headless/invisível (uma cópia separada respondia; o
  terminal aberto ficava intocado, mostrando o placeholder "explain this codebase").
- **Captura por quiescência + estado-da-TUI:** o host monitora o terminal do destino (só quando
  **desfocado**, igual Maestri), detecta o fim do turno (silêncio + sumiço do "esc to interrupt")
  e devolve a resposta a quem perguntou (pelo mailbox → `Answer from <nó>: ...`).
- **Fallback headless:** se a captura falhar (sem terminal, destino focado, timeout, vazio), cai
  no mecanismo mediado anterior — quem perguntou **sempre** recebe algo. `MAESTRO_ASK_MODE=headless`
  força o modo antigo.
- Protocolo do mailbox e guardrails reaproveitados (sem mudança em `ask_bus`/`ask_router`/cliente).
- Heurística de captura pura e testável em `maestro/native/ask_capture.py` (+ `tests/test_ask_capture.py`).
- Honesto: injeção é confiável (provada em VTE real); captura de TUI full-screen é best-effort
  (~nível Maestri, ~70%) com fallback. Vai precisar de ajuste fino com os TUIs reais.

## [0.25.0] — Canvas: abre igual fechou (persistência completa do estado)
- **Roster de terminais persistido (a grande lacuna):** o startup recriava SÓ os agentes
  instalados; terminais criados em runtime (➕ shell ou instância extra de agente) **sumiam**
  ao reabrir. Agora a lista de terminais é persistida (`ui_state canvas_nodes`: nid/kind/base)
  e **recriada ao abrir** — shells e instâncias extras voltam na posição/tamanho. 1ª vez
  semeia com os agentes instalados. **✕ fecha = remove de vez** (sai do roster).
- **Grupos — WYSIWYG:** o grupo agora reabre **exatamente** no tamanho/posição em que estava
  (antes salvava o "manual" e o auto-fit encolhia/crescia ao reabrir). Persiste o retângulo
  EXIBIDO (`_persist_group`) e o auto-fit fica suspenso no startup (`_loading`).
- **Fit ao abrir:** a câmera **centraliza no conteúdo** — tudo visível, sem caçar card fora da tela.
- Posições/tamanhos de cards, notas (texto/cor/pin), grupos, cabos e zoom já persistiam e continuam.

## [0.24.0] — Canvas infinito funcional no CM4 (pan por SELECT+trackball + seleção)
- **Canvas infinito agora roda no CM4** (reverte o "adiado pro CM5"): a GPU aguenta o
  modelo-câmera (testado em runtime, sem OOM); os testes anteriores que "provaram"
  inviabilidade estavam contaminados por GPU travada.
- **Fix do crescimento da janela no pan:** o `_Plane` (`Gtk.Fixed`) mede a caixa dos
  filhos incluindo o `set_child_transform` (câmera assada), então ao panar o mínimo
  crescia e, com `ScrolledWindow` em policy **NEVER** (que exige o mínimo inteiro do
  filho), **empurrava o toplevel** (janela inchava/descia/saía da tela; maximizar
  quebrava). Trocado para policy **EXTERNAL** (rola programaticamente, sem barra, e
  **recorta** na viewport) + `Viewport.set_scroll_to_focus(False)` (evita deslize ao focar
  um filho). Diagnóstico ancorado em medição ao vivo (`xprop`/`xwininfo` + log de `measure`).
- **Pan por SELECT + trackball:** no uConsole, SELECT+bola gera eventos de **scroll**; um
  `EventControllerScroll` traduz os deltas em movimento da câmera — pan suave sem clicar.
- **Seleção + borda azul tracejada:** clicar num nó/nota/árvore o seleciona (outline azul
  `#89b4fa`); clicar no fundo limpa. Indica qual elemento está ativo.
- **Roteamento do scroll (fase CAPTURE):** SELECT+track **sempre pana** — o scroll é
  interceptado antes do VTE, então passar o cursor por cima de uma janela **não rouba** o
  pan. O scroll só **entra** num elemento quando ele é o **selecionado e está sob o cursor**
  (ex.: scrollback do terminal).

## [0.23.0] — Grupos/áreas (Fase 3c: C2) — fecha a Fase 3
- **C2 — Grupos/áreas:** ☰ → **⬚ novo grupo** cria um retângulo rotulado e colorido
  **atrás** dos nós (desenhado via cairo, sob cabos e nós). **Arrastar o grupo pela faixa
  do título move os nós contidos junto** (estilo ComfyUI/Blender). Alça no canto inferior
  direito **redimensiona**; **duplo-clique no título** abre o diálogo (renomear, escolher
  **cor** entre 5, **apagar** — sem apagar os nós). Tudo imanta à grade e persiste.
- Engine: `engine/groups.py` (Group + Groups CRUD) + tabela `groups` (no backup/restore).
- Hit-test próprio (faixa do título arrasta, canto redimensiona, corpo deixa passar o
  clique p/ nós/pan). Grupos também entram no cálculo da área rolável.
- **Auto-fit (abraça o conteúdo):** o grupo **cresce E encolhe** pra envolver os itens
  contidos com **margem** (16px laterais/topo + faixa do título; **50px na base**), ao
  vivo durante o arrasto. Item conta como "dentro" ao **sobrepor ~25%** (não precisa 100%).
  Mede o **card inteiro** (cabeçalho+corpo+rodapé), então a margem vale igual p/ terminal,
  nota e árvore. Resize **manual** vira piso (primeira opção). **Alça de resize visível**
  no canto.
- **Fix de render no pan:** a superfície cairo passou a cobrir o **conteúdo** (grupos+cabos)
  em vez da viewport — ao rolar não some mais metade do desenho (o GTK desloca o snapshot).
- **+7 testes** (suíte **386**) + probe ao vivo. Validado por busca (UX de grupos em
  editores de nó). **Conclui a Fase 3** (C1 minimapa + C4 notas + C2 grupos).

## [0.22.0] — Notas com cor e pin (Fase 3b: C4)
- **C4 — Cor da nota:** botão 🎨 no cabeçalho abre uma paleta de **5 cores** (amarelo,
  verde, azul, rosa, lilás) pra categorizar visualmente (estilo Post-it). A cor pinta o
  cabeçalho e é persistida.
- **C4 — Pin (📌):** botão fixa a nota — quando fixada, ela **não arrasta** (evita mover
  sem querer); 📍↔📌 indica o estado. Persistido.
- **Migração de schema:** colunas `color`/`pinned` adicionadas à tabela `notes` de forma
  idempotente (ALTER TABLE p/ DBs antigos; `_SCHEMA` p/ novos) — sem perder notas.
- **Grid liso (cairo → CSS/GPU):** o grid de pontos saiu do desenho cairo por frame (que
  dava **lag no pan** no ARM) para um **`radial-gradient` no fundo do plano**, composto na
  **GPU** — rola junto com o canvas sem custo por frame. Espaçamento = 20·zoom (atualizado
  só no zoom); pontos a 50% de opacidade; somem em zoom muito baixo.
- Validado por busca (GTK4 GSK/GPU vs cairo) + probe ao vivo. Suíte: 379 testes.
- Fase 3 quase fechada: falta **C2 (grupos)**.

## [0.21.0] — Minimapa (Fase 3a: navegação)
- **C1 — Minimapa:** visão geral sobreposta no canto inferior-direito (estilo editores de
  nó) mostrando todos os nós (azul), notas (amarelo) e árvores (verde) em miniatura, mais
  um retângulo branco indicando **onde você está** (viewport). **Clicar** no minimapa
  **move a vista** pra aquele ponto. Atualiza ao rolar/pan/zoom e ao criar/mover/fechar.
- Helper gi-free testável `minimap_layout` (escala+offset pra encaixar o "mundo").
- **Conserto do tremor no PAN:** o gesto de arrasto passou da `_Plane` (que ROLA no pan)
  para a `ScrolledWindow` (que não rola) — mesma causa/cura do tremor do nó (referência
  estável). Kinetic scrolling desligado p/ não brigar com o pan. Coords do pick traduzidas
  somando o scroll. Node drag e minimapa intactos.
- Validado por busca (DrawingArea+Overlay) + probe ao vivo. Suíte: 376 testes.
- Fase 3 continua: C4 (notas cor/pin) e C2 (grupos) em PRs seguintes.

## [0.20.0] — Geometria do canvas (Fase 2: grid+snapping + cabos curvos)
- **C3 — Grid + snapping:** grade de pontos sutil no fundo do canvas (desenhada só na
  viewport, leve no ARM); ao soltar um nó/nota ele **imanta** ao ponto mais próximo da
  grade, e ao redimensionar o card o tamanho vira **múltiplo da grade**. Alinhamento
  automático, sem cards "tortos".
- **C5 — Cabos curvos (tipo corda):** os cabos viram **cubic bezier** (`cr.curve_to`) com
  pontos de controle horizontais (direção do fluxo), em vez de linha reta — leitura de
  quem→quem muito melhor. Cor por estado mantida. Ancorado à geometria do C3 (pontas
  saem de nós já alinhados).
- **Arrasto estável + magnético (correção de tremor):** o arrasto de nó/nota/árvore
  passou a ser medido pelo **gesto do plano** (que não se move) em vez de um gesto preso
  ao próprio cabeçalho — elimina a realimentação que fazia a janela **tremer** (agravado
  pelo trackball). Padrão recomendado pela comunidade (gist KurtJacobson). Agora a janela
  **anda de ponto magnético em ponto magnético** durante o arrasto (snap ao vivo).
- **Desenho só da viewport:** o `do_snapshot` parou de criar uma superfície cairo do
  plano inteiro (~80 MB) a cada frame; desenha só a parte visível — bem mais leve no ARM.
- Helpers gi-free testáveis em `state.py`: `snap_to_grid`/`snap_point`/`cable_bezier`.
- Validado por busca (bezier + drag jitter) + probes ao vivo. Suíte: 374 testes.

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
