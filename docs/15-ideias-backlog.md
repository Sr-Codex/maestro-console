# Ideias / Backlog — maestro console

> Doc VIVO (não point-in-time): fila de ideias que surgem NO MEIO de outras tarefas. Regra de
> processo (ver `AGENTS.md`): ideia nova → discussão rápida (vale a pena?) → **1 entrada aqui** →
> continuar a tarefa atual sem interromper. Nada aqui vira código até o usuário puxar da fila
> explicitamente e virar um plano de verdade (estilo `docs/14`).

## Como usar

1. Ideia nova surge enquanto outra coisa está em andamento → **não implementar na hora**.
2. Discutir em 2-3 frases: o que é, por que, trade-off principal.
3. Registrar 1 entrada nesta fila (data + 1-2 linhas) — status inicial 🧊.
4. Continuar a tarefa que estava em andamento.
5. Quando o usuário quiser trabalhar numa ideia da fila: promover pra um doc de plano próprio
   (`docs/NN-...md`, mesmo formato do `docs/14`) e seguir o protocolo normal (analisar→pesquisar→
   validar→codar). Atualizar o status aqui pra 📋 (linka o doc do plano) e depois ✅ (linka o PR).

**Status:** 🧊 icebox · 🔬 em pesquisa · 📋 planejada (virou doc próprio) · ✅ entregue (link do PR).

## Quando revisar a fila (proativo, não só quando pedido)
O assistente deve **sugerir** (não decidir sozinho) revisar a fila nestes momentos naturais:
- **Fim de fase/feature** — quando todos os PRs de um plano (estilo `docs/14`) fecham/mergeiam.
- **Marco de release** — ao publicar uma versão (bump + tag).
- Quando o usuário perguntar "o que vem depois?"/"o que fazer agora?" sem ideia específica.
Fora esses pontos, a fila fica parada — não interromper uma tarefa em andamento pra revisá-la.

## Fila

### 2026-07-09 — Cor própria do `blocked` (Fase B, PR 2) — separar do âmbar do `waiting`
Fatiado da Fase B do header (`docs/27`, v0.60.0 fez só o LAYOUT). Hoje `waiting` e `blocked` são a
MESMA cor âmbar `#f59e0b` (`agents.py` STATE_COLORS) — só a forma do ícone difere. Proposta do
Fable (revisão adversarial): **`blocked` → Mocha red `#f38ba8` com texto escuro** (7.1:1, passa AA
e sobrevive a daltonismo; melhor que `#e64553`, que falha AA e colide com `failed #ef4444`). Por
que é PR próprio (não entrou no layout): **a Web UI não tem estado `waiting`** — `canvas.js:10`
mapeia `NEEDS_INPUT → blocked` (âmbar), então recolorir mecanicamente inverteria a semântica na
web. É **alinhamento semântico**, unidade coerente: tocar `agents.py` STATE_COLORS + `canvas.js`
COLORS + `style.css` vars + recolorir o SVG `maestro-state-blocked.svg` (pré-colorido) + o fallback
âmbar hardcoded do minimapa (`canvas.py:_mm_items`) + decidir o caso do órfão (reusa o ícone
`maestro-state-waiting`). Status: ✅ entregue — v0.61.0 (PR #72, branch `feat/blocked-color-mocha`)
(decisões: órfão fica âmbar/`waiting`; fallback do minimapa mantido como default de estado
desconhecido; `teams.py "reviewer"` não tocado por ser cor de papel).

### 2026-07-08 — Emoji-como-UI ainda tofa em 2 lugares fora da FAB (mesmo bug do A1)
Achado ao fazer o A1 (fim do tofu na FAB, v0.59.0). O device não tem fonte de emoji, então
qualquer glifo emoji usado como UI vira caixinha ▦. A FAB/título/HUD foram resolvidos, mas
sobraram 2 pontos: (a) o **seletor de ícone do nó** (`canvas.py:211`, grade de ~emoji 🤖🚀🐳…
que o usuário atribui ao card) — a grade inteira tofa; migrar pra ícones bundled Lucide
(há 264 no bundle) seria o certo; (b) o botão **"🤖 criar agente"** no diálogo de workspaces
(`canvas.py:~5420`). Fora do escopo da Fase A (que era a FAB). Sweep único: `grep` glifos > U+2FFF
usados como UI e trocar por bundled. Status: ❌ DESCARTADO (2026-07-11) — medido (Pango
`get_unknown_glyphs_count`) que **emoji NÃO tofa mais no SD/OS atual**: a fonte `fonts-noto-color-emoji`
entrou num upgrade do Kali rolling. O tofu do A1 era em OUTRO cartão/OS sem a fonte. Decisão do
usuário: não migrar (emoji funciona no OS principal; migrar perderia a variedade de 6000+ emojis com
busca). Se um cartão futuro tofar, a cura é instalar a fonte, não mexer no app.

### 2026-07-08 — Cápsula contextual de Grupo (e Árvore?) — conformidade com AGENTS.md
Da auditoria de UI (Fable, 2026-07-08). A regra do AGENTS.md pede cápsula contextual pra TODO
elemento com config; grupos hoje só configuram por **duplo-clique → `_group_dialog`** (nome/cor/
apagar), sem a pílula que nó e nota têm. **Adiado desta rodada de UI** (só Fases A+B entraram) por
ser M/G e mexer em caminho sensível. Notas técnicas do Fable pra retomar: grupo é **cairo, não
widget** → `_select(("group",gid))` NÃO funciona (sem frame; `.selected` não se aplica). Exige (a)
outline de seleção desenhado no `_draw_groups_cr`; (b) hit-test de seleção em `_pan_begin` ANTES do
`_select` (`canvas.py:2687-2813` — caminho quente de drag/resize/detach, risco médio de regressão);
(c) `_confirm_dialog` no apagar (o `_group_dialog:6947` deleta sem confirmação — paridade com o ✕ do
nó). Migrar nome/cor/apagar do diálogo pra pílula. Árvore de arquivo: provavelmente FORA (só tem
posição, sem config). PR isolado, depois de A+B validadas no device. Status: ✅ entregue —
v0.63.0, plano `docs/28` (revisado pelo Fable, 9 emendas), branch `feat/capsula-grupo`.
Decisões: pílula ENXUTA `[⚙][●][🗑]` (renomear fica no diálogo); corpo do grupo segue sendo
fundo; árvore de arquivo FORA (sem config). Bônus: hierarquia de cápsulas (FAB > pílula >
popover) virou regra de design, aplicada também ao popover de cor da nota.

### 2026-07-05 — UX dos diálogos/cards do canvas (📋 planejada → `docs/26`)
Gatilho: o card "Limites" (💰) abria "quase tela cheia"; usuário pediu melhorar a UX de TODOS os
diálogos. Causa-raiz geral: label `wrap=True` sem `max_width_chars` estica a `Gtk.Window` (no GTK4
não há clamp de janela). O card Limites já foi tapado inline (v0.56.0); ~15 labels seguem latentes
(os `_confirm_*` são os expostos). Plano **revisado pelo Fable** (cortou clamp-de-janela e
scroll-automático por não terem base no GTK4; rebaixou form-row/SizeGroup como YAGNI). Quick-win:
`_hint_label` + `_confirm_dialog` + guarda de regressão no fonte (roda no CI). Plano cirúrgico
completo em [`docs/26-plano-ux-dialogos.md`](26-plano-ux-dialogos.md). Status: ✅ entregue —
Nível 1 na v0.58.0; **Nível 2 completo (itens 4+5+6) na v0.62.0** (branch `feat/ux-dialogos-completo`),
validado por teste visual no device.

### 2026-07-04 — Auto-unload pós-tarefa: nó descarregado "acorda" pro cabo e volta a dormir sozinho
Ideia do usuário (durante o Bloco D do unload, `docs/21`): nó descarregado que recebe tarefa via
cabo executa o trabalho e **volta a ficar descarregado automaticamente** ao terminar — a menos que
tenha sido o USUÁRIO quem o acordou (clique no terminal / ⏏). "Descarregado" vira estado *pegajoso*
pra automação: trabalho delegado nunca deixa o nó permanentemente vivo comendo RAM; só ação humana
explícita "liga de verdade". Nota técnica: o handoff via cabo JÁ roda headless (`claude -p` próprio,
morre ao fim do turno — o PTY não ressuscita), então o núcleo da ideia é **formalizar o contrato**:
(a) delegação em nó descarregado nunca respawna o PTY; (b) a flag `unloaded` + camada de vista
(eject) sobrevivem ao ciclo busy→idle do handoff; (c) só clique humano limpa a flag. O pedaço
genuinamente NOVO: **auto-unload por ociosidade de nós VIVOS** ("suspender após X min sem uso
humano" — timeout configurável + guard de ociosidade). Trade-off: resume relê o transcript
(re-ingestão de tokens a cada ciclo) e auto-unload arrisca matar nó que o usuário ia usar já já.
**Detalhe do usuário (2026-07-12): opt-in em DOIS níveis** — (a) toggle GLOBAL na config
("habilitar para todos os terminais": todo terminal novo já nasce com o padrão) e (b) override
POR TERMINAL na config do nó (ativar só naquele terminal, ou desativar um específico com o
global ligado). Mesmo padrão do `monitor_sound` (`node_cfg` por nó) + default global em
`ui_state` — nunca forçado sem o usuário habilitar.
Status: 🧊 icebox.

### 2026-07-03 — Novos candidatos vindos da pesquisa de dores da concorrência (análise cruzada)
Da análise `docs/24-analise-dores-vs-app.md`
(cruzamento dos 2 relatórios de dores — Maestri + 29 concorrentes — com o STATUS v0.55.0). Itens
NOVOS que não estavam na fila (os já existentes — reattach órfãos, FIFO, briefing, modo compacto,
profiles, nerd fonts — foram PROMOVIDOS em prioridade lá, não duplicados aqui):
- **Budget cap: pausa graciosa + notificação + retomada 1-clique** ao esgotar o teto — dor validada
  (RunMaestro #235: run de 24h parado 4h em silêncio; Cursor sem guardrails). Extensão do Bloco D
  (docs/20 §4 já previa). ✅ ENTREGUE (2026-07-11, **v0.64.0**/ADR-26) →
  [`29-plano-budget-pausa-retomada.md`](29-plano-budget-pausa-retomada.md) (plano v2 pós-Fable;
  os gates das brechas LIVE/floor entraram no mesmo PR).
- **Contagem do gasto do modo LIVE do cabo** — o GATE do budget no LIVE entrou na v0.64.0, mas o
  gasto da sessão viva ainda NÃO alimenta o contador (sessão viva tem JSONL próprio; exige mapear
  o session_id do PTY). Lacuna documentada no ADR-26. 🧊 (2026-07-11)
- **Paste/drag de imagem pro nó** — dor em 5+ concorrentes (supacode, AoE, Maestro OSS, Clave com
  caminho temp deletado): screenshot do clipboard → salvar em arquivo estável do workspace e colar
  o caminho; drag de arquivo → caminho estável. Verificar comportamento atual do VTE primeiro. 🧊
- **Teste de runtime de teclado internacional** (dead keys/acentos PT-BR + CJK) no VTE — dor em 4
  concorrentes; provavelmente já funciona, mas PROVAR e registrar (público PT-BR). 🧊
- **Perfis de agente = conta/ambiente isolado por nó → REFORMULADO (2026-07-12, revisão
  adversarial Fable + pesquisa de mercado):** derrubado o preset básico de flags (redundante:
  `agent_argv` só varia auto-approve; ⚙ por nó + Team Templates cobrem o resto — preset sem knob
  é menu vazio) e **fundido com este item de multi-conta**, que a pesquisa validou FORTE: 10+
  issues duplicadas no anthropics/claude-code pedindo perfis (jan–abr/2026, sem entrega nativa) e
  ecossistema dedicado (Claude Switch, AgentsRoom). **Correção do docs/24: "ninguém entrega"
  DESATUALIZADO** — a Clave fechou a #22 (PR #23 mergeado 2026-06-06, macOS); o diferencial que
  resta é canvas/Linux-ARM. Recorte: **perfil = nome + config dir isolado
  (`CLAUDE_CONFIG_DIR`/`CODEX_HOME`, mecanismos oficiais aceitos pela Anthropic) + env extra**,
  escolhido ao criar o nó, badge no card. Guardas do plano futuro: **NUNCA rotação automática de
  conta** (é o padrão que a Anthropic bane — evasão de limite; perfil = escolha humana explícita
  por nó); rw-bind por nó no sandbox (hoje o dir alternativo ficaria read-only — `sandbox.py`);
  **usage.py precisa seguir o config dir do nó** senão o budget cap fica cego (`~/.claude/projects`
  hardcoded — regressão silenciosa no ADR-22). Demanda é do upstream (nenhum pedido direto ao
  maestro-console ainda). **PUXADO da fila 2026-07-12** → 📋 planejado em
  [`31-plano-contas-por-no.md`](31-plano-contas-por-no.md) (conceito renomeado pra **CONTA**
  — "profile" colide com AgentProfile dos adapters; prova de isolamento no device; design v2
  pós-revisão adversarial Fable com 12 emendas — inclusive: rw_paths por SUBSTITUIÇÃO, os 4
  call-sites de argv, session_capture/orphans hardcoded, resolvedor engine-side; decisões
  D1-D8 VALIDADAS pelo usuário
  2026-07-12). ✅ **ENTREGUE — v0.66.0 (PR #82,
  squash-merge 2026-07-13)**, prova de runtime 8/8 no device (isolamento de credencial,
  usage na conta, boot, E8a/E8b; placar completo no comentário do PR).
- **Guardas de projeto (não-features)**: manter kanban de sessões cortado (Windsurf confirma
  "orchestration theater"); nunca auto-atualizar/embutir CLI do agente (Jean #460); não escalar
  N agentes antes de UX de review (P12). 🧊 (regras, avaliar incorporar no AGENTS.md quando
  fizer sentido)

### 2026-07-18 — Vigia de atualização do CLI (canário pós-upgrade)
Ideia do usuário, motivada pela regressão do transcript (entrada abaixo): o CLI auto-atualiza
sozinho (2.1.207→208 no meio de uma investigação) e pode quebrar premissas do app em silêncio.
Proposta: o app registra a versão do CLI a cada boot (`claude --version` → `ui_state`); ao
detectar upgrade, (a) avisa no canvas ("CLI atualizou X→Y") e (b) roda um CANÁRIO barato das
premissas que o app depende — ex.: headless `-p` mínimo com config-dir isolado → transcript
aparece? — e reporta ✅/⚠️. Casa com o ADR-24 (o CLI pertence ao usuário; o app OBSERVA, nunca
atualiza/embute). Trade-off: o canário gasta um turno mínimo de API → rodar só com opt-in do
usuário, ou modo "só avisar" sem canário. 🧊

### 2026-07-13 — CLI claude 2.1.207+: TUI interativa com CLAUDE_CONFIG_DIR custom PERDE o transcript (upstream) — INVESTIGADO 2026-07-18, causa fechada
Investigação por medição (matriz A/B no device, claude 2.1.208): **TUI + config default grava
normal** (transcripts reais do mesmo dia); **TUI + `CLAUDE_CONFIG_DIR` custom NÃO grava EM LUGAR
NENHUM** (turno completado e provado na tela via sonda PTY, SEM sandbox — o bwrap não é a causa);
**headless `-p` + config custom grava certo** (provado na entrega das contas, v0.66.0). O CLI 2.1.x
roda um daemon (`claude daemon run`, sockets em `/tmp/cc-daemon-<uid>/`) — o `--tmpfs /tmp` do
sandbox ainda o torna inacessível nos nós (agravante paralelo pra nó default). Upstream sem issue
idêntica (buscado 2026-07-18; área em obra: release 2.1.208 cita fixes de daemon; #69140/#49903
são perdas de transcript relacionadas). **Impacto no app:** budget/medidor INTACTOS (bebem do
headless); captura de sessão interativa (unload A′/reattach R2) degrada pro fallback "começar do
zero" — pior pra NÓ DE CONTA (interativo nunca persiste). **Consequência da triagem (Fable
2026-07-18): auto-unload segue viável, mas o RETOMAR de sessão interativa não é confiável até fix
upstream — re-escopo é decisão do usuário.** **Issue upstream ABERTA (2026-07-18):
[anthropics/claude-code#78843](https://github.com/anthropics/claude-code/issues/78843)** —
acompanhar o fix; quando corrigir, retirar o asterisco do auto-unload. 🔬
### 2026-07-02 — Paralelizar implementação de features independentes com sub-agentes
Usar o `Agent` tool (`isolation: "worktree"`, cada sub-agente numa cópia isolada do repo) ou o
`Workflow` tool (fan-out mais estruturado, só com pedido explícito do usuário) pra implementar
VÁRIAS features/fases independentes ao mesmo tempo — cada uma vira seu próprio PR — em vez de
sequencial (como fizemos com as Fases C e D da orquestração de equipe). Só funciona bem se as
tarefas forem **genuinamente independentes** (sem PR encadeado); se uma depender da outra, o
paralelismo vira ilusão e o certo continua sendo sequencial. Status: 🧊 icebox.

### 2026-07-02 — Checklist de "hora certa" pra encerrar a sessão + recap via BMad na sessão nova
Formalizar um checklist prático de QUANDO fechar a sessão atual (evitar contexto grande demais) em
vez de tentar medir tokens diretamente (o assistente não tem esse número exato) — usar sinais
indiretos: (a) feature/PR atual fechou (checkpoint natural, já usado pra sugerir revisão da fila
— ver seção acima), (b) a conversa já sofreu 1 auto-compactação (sinal de que já está grande),
(c) troca de tema grande (ex.: terminar uma fase e começar outra não-relacionada). Na sessão NOVA,
rodar um passo de "recap" no início — reaproveitar `bmad-help` e/ou ler os doc-âncora
(`docs/STATUS.md`, `CHANGELOG.md`, o `docs/NN-plano-*.md` da feature em andamento) — em vez de
confiar só na memória automática. Trade-off principal: um checklist manual exige o usuário (ou o
assistente) notar os sinais e agir; não tem gatilho automático de "contexto grande" hoje. Status:
🧊 icebox.

### 2026-07-02 — F1 (medidor de custo/tokens + budget) NÃO é só feature pausada: é controle de segurança do ADR-17 sem implementação
Achado da revisão adversarial do Fable 5 (2026-07-02) sobre `docs/16`. O F1 (parser/ledger já
existem no PR #9, pausado em ~26/06 por "não vi valor") ganhou um argumento novo que a pausa não
considerava: o **ADR-17 (Etapa 3) lista "budget por CUSTO REAL de tokens" como controle de
segurança OBRIGATÓRIO do Maestro mode**, mas o `STATUS.md` lista a feature como "reservada/não
entregue" → um controle declarado no modelo de segurança está como promessa sem implementação.
E a pausa (~26/06) é **anterior** ao ADR-17 (30/06) e ao Maestro mode virar real — com agentes
recrutando agentes, custo às cegas deixou de ser dashboard e virou guardrail. Nuance: provável que
exista teto-proxy por contagem de agentes (fleet-cap); falta o budget por custo real (o próprio
ADR-17 chama contagem de agente de "teatro parcial"). Também é a dor #1 da categoria (`docs/08`),
ausente no Maestri. Trade-off: reabrir contradiz a decisão de pausa do usuário — por isso fica no
backlog, não promovido. Status: 🧊 icebox (candidato forte a retomar o PR #9).

### 2026-07-02 — Revisar docs/10 (roadmap): sobreposição Floors↔Fase 7-A4 + kanban (Fase 5-A2) como cargo-cult
Achado do Fable 5 (2026-07-02). (a) A **Fase 7 "A4 — worktree por nó"** parece **já parcialmente
entregue**: o `STATUS.md` lista *Floors = git worktree por agente + merge preview* como feito, mas
o `docs/10` só marca as Fases 1-3 como defasadas e não sinaliza essa sobreposição → re-escopar ou
riscar o A4. (b) O **kanban de sessões (Fase 5-A2)** é provável cargo-cult de SaaS/time grande
(Nimbalyst/Windsurf) — dev solo com meia dúzia de nós numa 1280×720 já vê os estados no canvas;
candidato a cortar. Contraste: a **Fase 4 (steering + timeline) o Fable endossou** como
prioridade certa (casa com "controlar sessão longa + nudge", `docs/08`). Status: 🧊 icebox
(revisão de doc, não feature).

### 2026-07-02 — Antes de aprofundar o líder-de-grupo (delegate-mode/"ondas"), testar via PROMPT primeiro
Achado do Fable 5 (2026-07-02), reforça o que a pesquisa (`docs/16`) já apontava: o datapoint mais
forte (compilador Anthropic, confirmado 3-0) **não tinha manager central** — agentes escolhiam a
própria tarefa via lock de arquivo; e `docs/02` diz que codificação acoplada não ganha com
multi-agente + o padrão manager hierárquico falha no CrewAI. Logo, aprofundar o líder (ex.: "ondas"
do Kiro, delegate-mode com mailbox) **dobraria a aposta no padrão que a própria pesquisa desafia**.
Saída barata antes de escrever orquestração nova (lição Beast Mode, `docs/16` §5, 3-0): ajustar o
comportamento do líder **só via prompt** e medir. Status: 🧊 icebox (regra de cautela, não tarefa).

### 2026-07-02 — Melhorias da pesquisa de comunidade (docs/17) — restante do ranking, a entender melhor
Da pesquisa de comunidade (`docs/17`, Opus 4.8 + Codex). O **#1 (estado por nó / "precisa de você")
foi puxado** → `docs/18`. O restante fica aqui pra o usuário entender melhor antes de puxar. Tema
comum: *less babysitting* (menos babá). Cada um mapeia à arquitetura atual (canvas GTK4+VTE, cabos,
Team Templates/líder, Maestro mode, bwrap):
- **"Unload" de nó** — matar o processo VTE/PTY mantendo o nó + estado no `CanvasModel`/`ui_state`;
  reabrir sob demanda. Ataca a dor de RAM (Maestri: 20GB → unload na v0.29), **decisiva no CM4**.
  Alto valor no nosso hardware. ✅ **PUXADO 2026-07-03 → investigação + TR + spike + plano
  revisado pelo Fable em `docs/21-plano-unload-no-ram.md`** (rota kill-and-resume por CAPTURA de
  sessão; Congelar/CRIU descartados). Pronto pra virar stories.
- **Recuperação/reattach + "arquivar em vez de fechar"** — ao abrir, detectar nós/worktrees órfãos
  (pós-crash) e oferecer reanexar / novo agente no worktree / arquivar. Casa com "abre igual fechou"
  e com os Floors já existentes. ✅ **ENTREGUE 2026-07-05 (v0.57.0, R1+R2+R3)** — plano
  `docs/25-plano-reattach-orfaos.md` (revisado pelo Fable). Detecção de nó-agente órfão (crash ∧
  ¬descarregado ∧ transcript-no-disco) → âmbar "recuperável" + Reanexar/Novo/Arquivar. **Restou:**
  reconciliação de git worktree órfão (R4, adiada — 2º PR/backlog).
- **Fila FIFO de follow-ups por nó/cabo** — empilhar instruções enquanto o agente roda, reordenar,
  cancelar; enviar ao VTE só quando pronto. Maestro mode enfileira sem perder mensagem. 🧊
- **Briefing persistente por grupo/template** — brief de "objetivo/decisões/contexto" entregue
  automaticamente a cada agente novo do grupo + campo "objetivo atual". Resolve "usei um dia e
  esqueci o plano". ✅ ENTREGUE (2026-07-12, **v0.65.0**/ADR-27) →
  [`30-plano-briefing-grupo.md`](30-plano-briefing-grupo.md) (pesquisa de validação + revisão
  adversarial Fable: mecanismo invertido de "injeção no 1º prompt" pra bloco marcado em
  CLAUDE.md/AGENTS.md do workspace, o trilho dos roles; decisões validadas no §10).
- **Modo compacto pro canvas lotado (1280×720)** — colapsar grupos, mini-cartões de nó, atalhos por
  teclado; camada de visualização sobre os mesmos nós (não muda o orquestrador). Essencial p/ 8+ nós.
  🧊 **(2026-07-12: usuário avaliou — sem utilidade no uso atual; STAND BY deliberado, não
  promover sem ele pedir.)**
- **Consciência read-only entre nós irmãos** — um agente lê status/branch/diff-resumido/notas de
  outro nó do MESMO grupo, sem escrever; mediado pelo orquestrador, escopo por cabo/grupo (CLI/MCP
  local). 🧊
- **Profiles de agente (presets nomeados)** — ❌ DERRUBADO como item isolado (2026-07-12,
  Fable): sem knobs de spawn pra embalar, preset é redundante com ⚙ por nó + Team Templates.
  Fundido no item "Perfis de agente = conta/ambiente isolado por nó" (lista de 2026-07-03 acima).
- **Custo/tokens por nó (versão lean)** — um número discreto no header do nó, sem dashboard. **Já
  está no backlog acima como F1** (triplo-confirmado: docs/16 + Fable + docs/17); é o mesmo item —
  não duplicar, só reforça a prioridade. 🧊
- Menores: **Nerd Font** no terminal (expor no `terminal_theme`/`ui_state`); botão "fim ao vivo" +
  indicador de "lendo histórico enquanto o agente produz"; **diff desde o último feedback**. 🧊
- **Já ENTREGUE (não confundir com pendência):** paleta de comandos (Ctrl-P), worktree por agente
  (Floors), grupos, minimapa, monitorar atividade — a pesquisa pediu, o projeto já tem.
