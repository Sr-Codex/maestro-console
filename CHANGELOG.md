# Changelog

Todas as versões do **maestro console**. Formato inspirado em *Keep a Changelog*;
versionamento incremental. Datas em 2026.

## [0.49.0] — Orquestração de equipe (Fase C): editor visual de templates
Fecha o gap conhecido desde a Fase A: criar/editar/duplicar/excluir um `TeamTemplate` (grupos +
membros) inteiro pela UI, sem tocar no JSON manualmente.
- **`_team_edit_dialog`** (template) + **`_team_group_edit_dialog`** (grupo, aninhado): nome/
  descrição/grupos do template; nome/cor/líder/membros do grupo; membro = papel + agente
  (claude/codex) + instrução.
- **`_save_team_from_staging`**: lógica extraída (build via `to_dict`/`from_dict` do rascunho
  editável + `validate_team_template` + persiste) — testável sem GTK, espelha
  `_apply_team_decision` da Fase B. Erro de validação aparece na tela, não crasha.
- FAB "🧩 Montar equipe": botão **"+ Novo template"**; linhas custom ganham **"Editar"**;
  linhas built-in ganham **"Duplicar"** (clona pra editar uma cópia, já que built-in é
  só-leitura).

## [0.48.0] — Orquestração de equipe (Fase B): montar equipe por linguagem natural
Um manager em Maestro mode agora monta uma equipe inteira **descrevendo em linguagem natural**, sem
precisar recrutar um por um — mas a materialização nunca acontece sem confirmação humana explícita
(docs/14 §6).
- **`maestri team '<json>'`**: o manager (que já é o LLM interpretando o pedido) gera o `TeamTemplate`
  em JSON direto e chama o comando; o skill (`maestro_skill_text`) ensina o schema e as regras
  (2–5 por grupo, `instruction` com objetivo claro, sem inventar campo `manager`).
- **Confirmação humana obrigatória:** o host NUNCA materializa a partir de um pedido de agente sem
  humano decidir — `_hitl_team` valida a spec (JSON/estrutura/tamanho) e abre um diálogo mostrando
  grupos/papéis; só no "Montar" do humano a equipe é criada (reusa `_materialize_team` da Fase A,
  com os mesmos guard-rails de fleet-cap/tamanho de grupo).
- **Autoridade por canal, não por payload (ADR-17/18):** o manager que liga a equipe é sempre o `frm`
  derivado do socket que enviou o comando — um campo `manager` forjado no JSON é ignorado.
- `team` entra em `MUTATING_CMDS` (rate-limit) e é roteado antes do dispatch genérico (mesmo padrão do
  HITL de recrutamento acima do soft-cap), com a lógica de decisão extraída (`_apply_team_decision`)
  pra ser testável sem GTK.

## [0.47.0] — Orquestração de equipe (Fase A): Team Templates + materializador
Mandar UMA instrução e o maestro montar uma **organização inteira** — grupos do canvas +
terminais recrutados dentro deles, com papéis, de uma vez (docs/14, plano cirúrgico validado
com 2ª rodada de pesquisa comparando repos em crescimento rápido e grandes players como CrewAI,
Google ADK, OpenAI Agents SDK, Claude Agent SDK).
- **`TeamTemplate`** (`engine/team_templates.py`): `AgentSpec` (=`Role`) → `GroupSpec` (com
  `leader` opcional, schema-only por ora) → `TeamTemplate`. Persistência atômica (temp+
  `os.replace`), espelhando `roles.py:save_role_library`, em
  `~/.config/maestro-console/team_templates.json`. 2 built-ins (`dev-trio`; `equipe-projeto`,
  com placeholder).
- **Placeholders** (`{projeto}` etc.) via `str.format_map` tolerante (chave ausente não quebra):
  `render_team_template`/`placeholder_names` — reuso de template entre projetos, promovido da
  v2 pra já (padrão CrewAI `agents.yaml`, pesquisa 2026-07-01).
- **`_materialize_team()`** (canvas): cria os Grupos + recruta os membros DENTRO de cada um
  (posicionamento em grid, pertinência é **geométrica** — sobreposição ≥25%, não "add_member").
  Guard-rails: total ≤ `MAESTRO_FLEET_CAP`; grupo > 8 agentes bloqueia; > 5 avisa (recomendado:
  3-4, dado empírico de dois papers de 2026). WYSIWYG (`_autofit_group`+`_persist_group`).
  Auditado (`team_materialize`).
- **FAB "🧩 Montar equipe"**: lista templates (built-in + salvos), preview de grupos/papéis,
  Montar (pede valores de placeholder quando há) e Excluir (custom).
- Fase B (linguagem natural → confirma → materializa) fica para uma próxima fatia.

## [0.46.0] — Auto-aprovar comandos do agente (sem prompt de permissão)
O terminal **interativo** do agente pode rodar comandos **sem os prompts de permissão** do CLI,
quando o nó pede. Seguro por construção: o **ADR-6** já cravou que as flags de permissão do CLI
"só evitam prompts, não confinam — o limite efetivo é o bwrap"; então isto **só remove o atrito**,
sem afrouxar o sandbox nem a autoridade-no-host do Maestro mode.
- **Fase 1 — Maestro mode sem prompt:** ao ligar o Maestro mode, o manager passa a rodar
  `maestri recruit/list/…` sem pedir permissão a cada comando (era a dor: o CLI perguntava toda vez).
- **Fase 2 — toggle "Permissão total" por nó** (aba Detalhes): auto-aprova **qualquer** agente
  (não só managers), on-demand — usar claude/codex sem aprovar comando a comando. Persiste (`node_cfg`).
- **Flags declarativas** no `[interactive].auto_approve` de cada `adapters/*.toml` (ADR-4), **verificadas
  nos binários instalados**: claude 2.1.197 → `--permission-mode bypassPermissions`; codex 0.142.4 →
  `--dangerously-bypass-approvals-and-sandbox` (o `--full-auto` saiu; a sandbox interna do codex
  aninhada no bwrap quebra → essa flag desliga a interna dele, o bwrap externo é o confinamento).
- **Provado em runtime** (dentro do bwrap real, sem mock): claude e codex rodaram um `echo` sem prompt.
  Decisão em **ADR-19**. Supervisão de fleet (HUD, auditoria, kill-switch, anomalia) permanece.

## [0.45.0] — Editar Terminal (Fase 6): Maestro mode SEGURO (sub-orquestração)
**Maestro mode** — um terminal de **agente** pode virar **manager** e montar/coordenar uma equipe
no próprio canvas, sem sair do shell. Feature **original** (diverge do Maestri, que é orquestração
só-humana — ver ADR-16), construída sob a regra de ouro de multi-agente: **toda autoridade é imposta
pelo HOST a partir de estado que só ele controla, nunca de campos que o agente preenche** (ADR-17).
- **Toggle "Maestro mode"** (aba Detalhes, só nós de agente) → injeta a **manager-skill** no workspace
  isolado e reinicia. Shim **`maestri`**: `recruit <agente> [papel]` · `list` · `reassign` · `wire` ·
  `dismiss`. Cada comando cria um terminal de agente real **conectado por cabo ABAIXO** do manager.
- **Identidade por canal (anti-spoofing por construção):** o transporte agente↔host é um **socket
  Unix *pathname* por agente** (`<bus>/box/<nó>/sock`, bind-montado só naquele agente); o host deriva
  o remetente de QUAL listener aceitou a conexão e **ignora** o `frm` do payload. Shims em `<bus>/bin`
  (RO) chamados por `$MAESTRO_BIN/...` (imune ao reset de PATH). Sandbox com `--cap-drop ALL`.
- **Kill-switch global** ("⛔ Parar tudo" na cápsula principal): SIGKILL via pidfd em todo o fleet —
  cada agente é seu bwrap `--unshare-pid`, então o sinal **colapsa a árvore inteira** (ceifa a
  subárvore) — e **desarma** o Maestro mode de todos (re-armar = gate humano).
- **Tetos impostos pelo host:** **global** (12 agentes), **profundidade** da árvore de recrutamento
  derivada da linhagem (máx. 2), **por-manager** (6) e **rate-limit** (token-bucket 5/60s). Recruta
  **nasce sem poder recrutar** (promover exige o toggle humano → mata o fork-bomb). Acima do soft-cap
  (8), recrutar **pausa e PERGUNTA ao humano** (HITL).
- **Observabilidade que AGE:** **HUD do fleet** (nº/profundidade/ciclo), **auditoria append-only**
  (`<bus>/audit.jsonl`) e **vigilância ativa** — rajada de recrutamentos bloqueados dispara o
  kill-switch **automaticamente**. **Detecção de ciclo** nos cabos (union-find).
- **Provas de runtime (sem mocks):** probe de socket através de bind-mount bwrap real + identidade
  por canal; **tabletop drill** do kill-switch (SIGKILL via pidfd reapeia toda a subárvore, 0
  sobreviventes); app sobe limpo. **Testes:** socket/identidade, anti-spoofing no canvas, fleet-cap,
  profundidade, rate-limit, HITL, kill-all, anomalia, ciclo, auditoria (+E2E pelo socket).
- **Risco residual registrado (ADR-17):** proveniência/tainting de conteúdo, validação semântica plena
  e egress allow-list de rede ficam para depois (controles compensatórios: caps + kill-switch + HITL +
  auditoria). Mapa de cobertura OWASP ASI no ADR.

## [0.44.0] — Editar Terminal (Fase 5): Responsabilidades (roles) + hardening defensivo
**Fase 5 — roles por terminal** (aba Agente do editor):
- **Biblioteca de papéis** reusável (`~/.config/maestro-console/roles.json`, built-in coder/reviewer/
  planner) + **criar/editar** (nome, cor, prompt) + **Atribuir/buscar** (picker com swatch) + **Remover**.
- **Injeção:** ao atribuir, escreve um **bloco MARCADO** (`<!-- maestro-role -->`, append seguro —
  não sobrescreve o seu projeto) no `CLAUDE.md`/`AGENTS.md` **do workspace ISOLADO do agente** (a IA
  lê no start). **Respeita o seu projeto:** nunca toca no `AGENTS.md` do seu cwd. Sidecar portátil
  `.maestri/role.json` + cor accent = badge do role. **Auto-reinicia** o agente p/ reler.
- **Descobrir:** varre o cwd por `role.json`/`.maestri/` (multi-import). Engine `roles.py` testado.

**Hardening defensivo** (auditoria com pesquisa + revisão adversarial):
- **Respawn — state machine** (1 filho por vez; duplo Salvar coalesce; respawn só no `child-exited`,
  deferido): fecha o **duplo-spawn** e o **PID reciclado** (handler persistente zera o `_child_pid`;
  sinaliza via **pidfd** à prova de reciclagem; nunca mata PID nulo) e o **crash ao fechar durante o
  respawn** (`_destroyed` + cancela timers no close).
- **Sandbox `--unshare-pid`:** SIGKILL no bwrap colapsa o namespace → não vaza mais o processo interno
  (bubblewrap#529).
- **`roles.json` atômico** (temp + `os.replace`): crash no meio não apaga a biblioteca.
- Accent do usuário **não** é sobrescrito pelo role; role em **shell** não cria `.maestri`/reinicia à
  toa; monitor **não** dá falso "parou" pós-restart; **cwd** inexistente herda (não falha o spawn).

## [0.43.0] — Editar Terminal (Fase 4): Monitorar atividade (+ som)
- **Monitorar atividade** por terminal (toggle na aba Detalhes + tempo de quietude): observa o
  `contents-changed` e, quando o terminal **para de produzir output estando FORA de foco** (e não
  está "pensando" / `tui_busy`), dispara: **dot de atenção** (▲) + entra no **⚠N** + **notificação
  de desktop** com **resumo** (últimas linhas do output, estilo Ombro). Ao **focar** o terminal, o
  alerta limpa. Persistido (`node_cfg` `monitor`/`monitor_ms`); reaplicado na criação.
- **Som de alerta:** `notify()` agora também toca um som (`paplay`/`pw-play` do
  `freedesktop/complete.oga`, best-effort não-bloqueante) — vale p/ o monitor e p/ a atenção.
- **Limpeza:** removido o botão 🎨 de tema da cápsula superior (o tema global é definido pelo
  editor → aba Tema → "Aplicar a TODOS").

## [0.42.1] — Atalho automático Ctrl+<n> + fix do foco global
- **Atalho automático:** ao abrir um terminal ele recebe **Ctrl+<n>** (menor dígito 1–9 livre),
  salvo em `node_cfg 'shortcut'` → aparece na config (Detalhes → Atalho) e pode ser alterado/limpo.
- **Fix:** o controller de teclado global virou **CAPTURE** — os atalhos (Ctrl+1.., Ctrl+Shift+W/A/L/P)
  são vistos **antes** do VTE focado; antes, com um terminal em foco, o terminal "comia" a tecla e o
  atalho não trocava o foco. Teclas não-tratadas seguem indo pro terminal (digitação normal intacta).

## [0.42.0] — Editar Terminal (Fase 3): Comando + Diretório + Variáveis + Atalho
Aba **Detalhes** do diálogo "Editar Terminal", tudo por terminal e persistido (`node_cfg`).
- **Comando custom** (qualquer nó): `bash -lc "<cmd>; exec bash -i"`; vazio = shell/agente padrão.
- **Diretório de Trabalho** (cwd): no `spawn_async` (`working_directory`) + botão **Procurar…**
  (`Gtk.FileDialog` de pasta).
- **Variáveis de ambiente** (KEY=VALUE, uma por linha): mescladas ao ambiente herdado.
- **Atalho (foco):** captura **qualquer combinação** (Ctrl/Alt/Shift+tecla, via `Gtk.accelerator_*`)
  → foca aquele terminal de qualquer lugar (prevalece sobre o Ctrl+Shift+1-9 por ordem); **Limpar**.
- **Respawn no mesmo widget** (pesquisa VTE 0.84): SIGHUP no process group → respawn no
  `child-exited` (`reset` + `spawn_async`). Botão **↻ Reiniciar** + **auto-respawn no Salvar** se
  comando/cwd/env mudarem. `make_terminal(argv, cwd, envv)` + `_spawn_into` reusável.

## [0.41.0] — Editar Terminal (Fase 2): Tema por terminal (+ global, Sistema/Escuro/Claro)
- **70 temas:** os 4 base + **66 esquemas populares** (iTerm2-Color-Schemes, formato **ghostty**,
  MIT) parseados em `term_themes/schemes.json` (50 escuros + 16 claros: TokyoNight, Nord, One Dark,
  Solarized Dark/Light, Catppuccin Mocha/Latte, Dracula, Gruvbox, Monokai, GitHub Dark/Light,
  Everforest, Rose Pine, Ayu, Kanagawa, Flexoki…). **Parser ghostty** reusável.
- **Import do usuário:** arquivos no formato ghostty soltos em `~/.config/maestro-console/
  terminal-themes/` aparecem na lista (igual ao `~/.maestri/terminal/themes`).
- **Tema por terminal (override) ou global:** na aba **Tema** do editor, seleciona um tema e o
  **toggle "Aplicar a TODOS (global)"** decide o alcance (ligado = vira o tema global; desligado =
  só este terminal). **"Seguir o global"** tira o tema próprio. **Sistema/Escuro/Claro** via portal
  XDG (`org.freedesktop.appearance/color-scheme`; fallback escuro no uConsole). Preview "Atual:" com
  nome + alcance + swatch; busca **🔎 Mais temas** (swatch por tema).
- **FAB:** o combo de 70 itens virou um **picker 🎨 com busca + swatches** (tema global).
- `_apply_theme` agora aplica **por nó** (override prevalece). `theme_is_dark`/`DEFAULT_DARK`/
  `DEFAULT_LIGHT` em `themes.py`. `LICENSE-iterm2-color-schemes` incluído.

## [0.40.0] — Editar Terminal (Fase 1): Aparência — Fonte + Cor + Ícone (por terminal)
Aba **Aparência** do diálogo "Editar Terminal", tudo **por terminal** e persistido (`node_cfg`).
- **Fonte (avançada):** família+tamanho por terminal via `Gtk.FontDialog` **filtrado p/ monospace**
  (`CustomFilter`), **zoom de fonte** por terminal (`Vte.set_font_scale`, A−/A+, clamp 0.25–4.0) e
  **default global** (`terminal_font`) com override por nó. Precedência: nó → global → monospace
  do sistema. Aplicado na criação do nó e no Salvar.
- **Cor accent:** tint da faixa do cabeçalho por terminal — paleta da nota (`.csw`/`.palsw-i`),
  **∅ sem cor** e **🎨 Mais cores** (`Gtk.ColorDialog`). Provider de CSS próprio.
- **Ícone:** **256 ícones Lucide (ISC) focados em dev** bundlados em `maestro/native/icons` (cor
  fixada #cdd6f4, SVG planos — GTK não recolore stroke-`currentColor`; ver pesquisa). No editor:
  grid rápido (24) + **"🔎 Mais ícones…"** com **busca por nome+tags** (índice `dev-icons.json`) +
  **preview "Atual:"**. **Emoji:** grade rápida (24) + **"🔎 Mais emojis…"** com busca em ~1777
  (catálogo via `unicodedata` — o `Gtk.EmojiChooser` nativo abre vazio em `en_US`, sem `en.gresource`).
  Picker de busca genérico (`_search_picker`, ícone+emoji). Ícone no cabeçalho do nó. `LICENSE-lucide`.
- **Diálogo:** mais largo (560px) + **abas roláveis** (cap 320px) p/ caber na tela do uConsole;
  botões Cancelar/Salvar sempre visíveis. Transacional (aplica no Salvar).

## [0.39.0] — Editar Terminal (Fase 0): diálogo de abas + fundação
Início do clone do diálogo **"Editar Terminal"** do Maestri (Detalhes/Aparência/Agente).
- **Botão ⚙ Editar** na cápsula contextual do terminal → abre o **diálogo de abas**
  (`Gtk.StackSwitcher`: Detalhes / Aparência / Agente). Decisão de arquitetura: cápsula = ações
  rápidas, diálogo = config completa (mantém a regra de cápsulas do `AGENTS.md`).
- **Nome** ligado (edita → Salvar → atualiza o cabeçalho + persiste). Demais campos são
  **placeholders datados por fase** (ex.: "Comando — Fase 3"), comunicando o roadmap na própria UI.
- **Persistência por-nó:** `CanvasModel.node_cfg`/`set_node_cfg` (`nodecfg_{nid}_{key}`) — base
  genérica das próximas fases.
- **Doc-spec:** novo `docs/11-maestri-editar-terminal.md` — pesquisa completa (docs oficiais do
  Maestri + auditoria do código), as 13 capacidades × 3 abas, divergências do nosso modelo
  (Maestro mode mediado pela ask-bus; tema por-nó como override; roles via `role.json`) e o plano
  de 8 fases. Fecha a lacuna: o diálogo não estava documentado em lugar nenhum.

## [0.38.0] — Cápsulas de UI do canvas + conexão por cápsula + zoom ancorado
Rework da toolbar do canvas pro padrão de **cápsulas flutuantes** (arquitetura, ver `AGENTS.md`):
- **Barra superior removida.** Tudo migrou pra **cápsula principal (FAB, topo-centro)** — toda
  config de software + criação de elementos: rodar time, novo terminal/nota/grupo, handoff,
  conectar, árvore, workspaces, floors, routines, tema dos terminais, paleta, indicador de atenção.
  O antigo menu **`☰ ações` saiu**.
- **Zoom virou cápsula inferior-esquerda** (pílula compacta) — saiu da barra de cima.
- **Cápsula contextual por elemento:** ao **selecionar um terminal** (1 clique) aparece a 2ª pílula
  com as ações DAQUELE nó (**renomear**, **centralizar**, **fechar**), espelhando a pílula da nota.
  Generaliza o padrão (`_build_node_ctx` + `_update_ctx`), não cria UI ad-hoc por nó.
- **Conexão por cápsula:** botão **Conectar** padrão em toda cápsula contextual — a origem já é
  o elemento selecionado; um **cabo-fantasma** (mesma corda/física/cor do cabo real) **segue o
  cursor** até o 2º clique fechar a conexão em qualquer área do outro nó/nota. One-shot (faz 1 cabo
  e sai); o conectar global da FAB segue persistente.
- **Zoom ancorado (fix):** o zoom não escorrega mais pro canto — **sem seleção** escala em torno do
  **centro da tela**; **com um nó/nota selecionado**, leva ele pro **centro da viewport** (zoom
  "vai até o nó"). Antes mudava só a escala sem ajustar a câmera (escalava na origem do mundo).
- **Ícone próprio de conexão:** `maestro-connect-symbolic` (symbolic, "2 nós + linha") **empacotado
  no app** (`maestro/native/icons/`) + registro do search path — recolore pra cor da pílula e
  **independe do tema** do usuário (isola o volátil). Renomear passou a usar `document-edit-symbolic`
  (era um emoji ✏ de texto, destoava).

## [0.37.2] — Nota: margem da barra de scroll + scroll acompanha as setas
- **Margem da barra de scroll:** o texto da nota ganha **~14px à direita** (TextView e Label) p/
  não passar mais **por baixo** da barra de rolagem.
- **Auto-scroll com as setas:** mover o cursor com **↑/↓** agora rola o corpo junto (antes só a
  seta saía da vista) — `notify::cursor-position` também chama o `_note_autoscroll`.

## [0.37.1] — Organização da documentação + conserto do drift de versão
- **Fix: `maestro --version` reportava 0.18.0** (hardcoded em `maestro/__init__.py`) — agora a
  versão é **resolvida do pacote/`pyproject.toml`** (acaba o drift; o status da Web UI também).
- **Documentação organizada** (auditoria completa de currency): novo **`docs/STATUS.md`** (estado
  atual / o que foi entregue) e **`docs/index.md`** (índice mestre marcando cada doc atual/histórico).
  **PRD e architecture** ganharam **cópia versionada em `docs/`** (antes só no `_bmad-output/`
  gitignored). **Notas de defasagem datadas** nos roadmaps/auditorias congelados no MVP
  (`docs/03/06/07/10`) e nos artefatos BMad. README atualizado (435 testes, features v0.21→v0.37).
- Memória do projeto enxugada (diário de ~42 KB → sumário + ponteiros).

## [0.37.0] — Nota: checkbox auto-continua + auto-scroll + tira "rodar agente" da nota
- **Checkbox/lista continua sozinha:** numa linha `- [ ]`/`- `, **Enter** cria o próximo item
  (checkbox novo desmarcado); item **vazio** + Enter **sai** da lista; **Shift+Enter** = quebra
  normal. Função pura `md_enter_continuation` (`engine/notes.py`, testada).
- **Auto-scroll ao digitar:** o corpo da nota **acompanha o cursor** (não some no fim do bloco),
  com **~10px de respiro** abaixo. Como o TextView fica dentro de um Stack, o scroll é feito no
  `vadjustment` do ScrolledWindow pela posição do cursor (`get_iter_location`).
- **Removido (por enquanto) o "rodar agente com a nota"** — o seletor de agente + botão **▶ rodar**
  saíram do card da nota (o método `_run_note` fica p/ re-religar depois).

## [0.36.0] — Nota: edição in-place com estilo ao vivo (negrito/H1-H2-H3) + formata ao sair
- **Editar direto no card:** clicar a nota entra no modo editar (texto markdown), o cursor foca;
  **clicar fora** (fundo, outro nó/nota) **formata** (renderiza limpo, marcadores somem).
- **Estilo markdown AO VIVO ao editar:** negrito/itálico/tachado/código e títulos já aparecem
  estilizados enquanto digita (marcadores visíveis) — então clicar **B** mostra o negrito **na
  hora**, sem o vai-e-volta. `md_spans` (puro) → `Gtk.TextTag` no buffer; estilo some no render.
- **H1/H2/H3 com tamanhos distintos** (xx-large > x-large > large), **tolerante**: `#`/`##`/`###`
  viram título **com ou sem espaço** depois do `#` (tipo Notion); `####`+ e `#` no meio da linha
  ficam literais. `md_to_pango` reescrito; tags `h1/h2/h3` com `scale` no editor ao vivo.
- **Botões de formatação alternam (toggle):** `md_wrap_toggle` — clicar **B** numa seleção já em
  negrito **remove** os `**` (antes só acumulava). Vale p/ B/I/S/código.
- **Stack:** in-place NATIVO (GTK4 puro). Avaliados e descartados GtkSourceView 5 e WebKitGTK 6.0
  (Toast UI) — spike do WebKit ficou pesado/espremido no card; o nativo entrega mais p/ sticky
  simples (ver ADR). Pesquisa com fontes registra a decisão.
- Testes: `md_spans`, `md_wrap_toggle`, headings H1/H2/H3 (com/sem espaço). Suíte verde.

## [0.35.0] — Persistência de config de UI ("abre igual fechou") + modo de física do cabo
- **Regra do projeto:** toda configuração de janela/UI feita pelo usuário **persiste após fechar**
  (reabrir = igual fechou). Codificada em `AGENTS.md`; aplicada via `CanvasModel`/`ui_state`.
- **Modo de física do cabo persiste:** a escolha do Ctrl+Shift+P (verlet/catenária/mola) é salva
  (`CanvasModel.cable_phys`/`set_cable_phys`) e **recarregada na abertura** — antes voltava sempre
  pro verlet. Guarda contra valor inválido salvo (cai pro verlet).

## [0.34.0] — Cabo: física (Verlet/3 modos) + ímã de 8 pontos + bolinha + fluxo + connect/cursor
- **Física no cabo — corda Verlet + 3 modos comutáveis (Ctrl+Shift+P):** o cabo deixou de ser
  estático e ganhou **física orgânica** (ADR-14). Modos: **Verlet** (padrão — corda que cai,
  balança e assenta com inércia), **catenária** (sag estático elegante, sem balanço) e
  **bezier+mola** (caída leve + atraso suave ao mover, mais esticado). O usuário cicla a gosto;
  um rótulo **pisca ~2 s** ao trocar e some. Núcleo **puro/testável** em `maestro/native/rope.py`
  (Jakobsen/GDC 2001; `tests/test_native_rope.py`); desenho via **spline Catmull-Rom**.
- **Bateria (uConsole):** a simulação roda num `add_tick_callback` (frame clock GTK4) que **dorme
  ~0,5 s depois de assentar** — canvas parado = sem tick. Passo de tempo **fixo** (estável p/ Verlet).
- **Troca de âncora suavizada:** ao mover o card e o ímã trocar de borda/canto, a ponta do cabo
  **escorrega** até a nova âncora em vez de teleportar (acaba o "tranco"). Pesquisa: `docs/12`.
- **Auto-roteamento tipo ÍMÃ por 8 pontos:** o cabo gruda no **par de âncoras mais
  próximas entre si** — 4 meios de borda + 4 cantos de cada card. Lado a lado usa os meios (↔/↕),
  na diagonal usa os **cantos** que se encaram; segue os cards ao mover. Antes era fixo
  direita→esquerda (volta feia quando o destino estava atrás/acima). `cable_anchors`/`_magnet_pair`
  (funções puras em `state.py`); controles saem na direção da âncora.
- **Bolinha na ponta do cabo:** cada extremidade ganha uma bolinha (miolo branco + anel na cor do
  cabo), visível **só após conectar**. Tamanho fixo de tela.
- **Âncoras alinhadas na borda real:** `_cable_box` passa a usar os limites REAIS do frame
  (`compute_bounds` = cabeçalho + corpo) em vez do tamanho do terminal — antes as âncoras de baixo
  flutuavam acima da borda. Vale p/ nós e notas.
- **Conectar clicando em QUALQUER área do card:** o connect agora é tratado pelo gesto CAPTURE do
  frame (`_on_frame_press`), que pega o clique **antes do VTE/TextView consumir** — não precisa
  mais mirar na barra superior. Fora do modo conectar, terminal/seleção/arraste seguem normais.
- **Fluxo animado no SENTIDO REAL do dado:** durante um handoff/`maestro-ask` ativo (`busy`) o cabo
  vira **tracejado correndo de quem ENVIA → quem RECEBE** (`_edge_flow`), independente de como o
  cabo foi criado (é bidirecional). Só anima enquanto há `busy` e **se desliga sozinho** via
  `add_tick_callback` (frame clock GTK4) — sem tick em canvas parado (poupa bateria no uConsole).
  *Nota:* hoje dispara em agente↔agente; cabo nota↔nó ainda não marca `busy`.
- **Fix: cursor de resize voltou a aparecer nas bordas.** Temas de cursor incompletos (ex.:
  **Windows-10-Icons**, sem `Inherits=`) não têm os nomes CSS `ns/ew/nwse/nesw-resize` →
  `new_from_name` caía na seta padrão. Agora cada cursor tem **fallback pro nome legado X11**
  (`v_double_arrow`/`h_double_arrow`/`bd_double_arrow`/`fd_double_arrow`). A detecção da borda
  nunca esteve quebrada (confirmado por medição ao vivo); era só o render do cursor. Faixa de
  resize ajustada p/ **5px**.
- Testes do `cable_bezier` cobrindo horizontal, vertical, destino-à-esquerda e **diagonal→cantos**.

## [0.33.0] — Nota conectada: agente lê/escreve + sabe que tem nota — Fase 4b
- **O agente lê e escreve a nota conectada:** cada nota ligada a um nó vira o arquivo
  `<workspace>/notes/<id>.md` (markdown) no workspace do agente — ele lê/edita como arquivo normal.
- **O agente SABE que tem nota conectada:** bloco delimitado (`<!-- maestro-notes -->`) no
  `AGENTS.md`/`CLAUDE.md` do workspace lista as notas ligadas (título + caminho) — regravado quando
  as conexões mudam (`install_connected_notes_skill`).
- **Sincronização nos 2 sentidos:** edição do usuário no canvas reescreve o(s) arquivo(s)
  (`_save_note` → fan-out); edição do agente no arquivo volta pra nota por **poll de 500ms**
  (`_note_files_tick` → `file_to_note`), com a UI atualizando (sem clobber se você está digitando).
- **Conflito:** last-writer por mtime (só adota o arquivo se `mtime > a que gravamos`). **Isolamento:**
  o `notes/` de um nó só tem as notas ligadas a ele. Nota em vários nós = cópia por nó (fan-out).
- **Limpeza:** desconectar/apagar poda o arquivo e atualiza o manifesto (`_prune_node_note_files`).
- Reusa `note_to_file`/`file_to_note`, o padrão do `install_ask_skill` e do `start_ask_watcher`.
  Funções puras `connected_notes`/`nodes_for_note` (`state.py`). Nó shell-only não recebe notas.

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
