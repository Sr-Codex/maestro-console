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
`maestro-state-waiting`). Status: 🧊 icebox (pronto p/ promover — o plano já está no `docs/27`).

### 2026-07-08 — Emoji-como-UI ainda tofa em 2 lugares fora da FAB (mesmo bug do A1)
Achado ao fazer o A1 (fim do tofu na FAB, v0.59.0). O device não tem fonte de emoji, então
qualquer glifo emoji usado como UI vira caixinha ▦. A FAB/título/HUD foram resolvidos, mas
sobraram 2 pontos: (a) o **seletor de ícone do nó** (`canvas.py:211`, grade de ~emoji 🤖🚀🐳…
que o usuário atribui ao card) — a grade inteira tofa; migrar pra ícones bundled Lucide
(há 264 no bundle) seria o certo; (b) o botão **"🤖 criar agente"** no diálogo de workspaces
(`canvas.py:~5420`). Fora do escopo da Fase A (que era a FAB). Sweep único: `grep` glifos > U+2FFF
usados como UI e trocar por bundled. Status: 🧊 icebox.

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
posição, sem config). PR isolado, depois de A+B validadas no device. Status: 🧊 icebox.

### 2026-07-05 — UX dos diálogos/cards do canvas (📋 planejada → `docs/26`)
Gatilho: o card "Limites" (💰) abria "quase tela cheia"; usuário pediu melhorar a UX de TODOS os
diálogos. Causa-raiz geral: label `wrap=True` sem `max_width_chars` estica a `Gtk.Window` (no GTK4
não há clamp de janela). O card Limites já foi tapado inline (v0.56.0); ~15 labels seguem latentes
(os `_confirm_*` são os expostos). Plano **revisado pelo Fable** (cortou clamp-de-janela e
scroll-automático por não terem base no GTK4; rebaixou form-row/SizeGroup como YAGNI). Quick-win:
`_hint_label` + `_confirm_dialog` + guarda de regressão no fonte (roda no CI). Plano cirúrgico
completo em [`docs/26-plano-ux-dialogos.md`](26-plano-ux-dialogos.md). Status: 📋 planejada (aguarda
o usuário escolher escopo: quick-win vs completo).

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
Status: 🧊 icebox.

### 2026-07-03 — Novos candidatos vindos da pesquisa de dores da concorrência (análise cruzada)
Da análise `docs/24-analise-dores-vs-app.md`
(cruzamento dos 2 relatórios de dores — Maestri + 29 concorrentes — com o STATUS v0.55.0). Itens
NOVOS que não estavam na fila (os já existentes — reattach órfãos, FIFO, briefing, modo compacto,
profiles, nerd fonts — foram PROMOVIDOS em prioridade lá, não duplicados aqui):
- **Budget cap: pausa graciosa + notificação + retomada 1-clique** ao esgotar o teto — dor validada
  (RunMaestro #235: run de 24h parado 4h em silêncio; Cursor sem guardrails). Extensão do Bloco D
  (docs/20 §4 já previa). 🧊
- **Paste/drag de imagem pro nó** — dor em 5+ concorrentes (supacode, AoE, Maestro OSS, Clave com
  caminho temp deletado): screenshot do clipboard → salvar em arquivo estável do workspace e colar
  o caminho; drag de arquivo → caminho estável. Verificar comportamento atual do VTE primeiro. 🧊
- **Teste de runtime de teclado internacional** (dead keys/acentos PT-BR + CJK) no VTE — dor em 4
  concorrentes; provavelmente já funciona, mas PROVAR e registrar (público PT-BR). 🧊
- **Perfis com diretório de config isolado por nó** (conta Claude trabalho × pessoal simultâneas —
  dor Clave #22, ninguém entrega) — ampliação do item "Profiles de agente" já na fila. 🧊
- **Guardas de projeto (não-features)**: manter kanban de sessões cortado (Windsurf confirma
  "orchestration theater"); nunca auto-atualizar/embutir CLI do agente (Jean #460); não escalar
  N agentes antes de UX de review (P12). 🧊 (regras, avaliar incorporar no AGENTS.md quando
  fizer sentido)

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
- **Briefing persistente por grupo/template** — `brief.md` de "objetivo/decisões/contexto" injetado
  automaticamente em cada agente novo do grupo (nota conectada + líder). Resolve "usei um dia e
  esqueci o plano". Pode incluir um campo "objetivo atual" fixado no header do grupo. 🧊
- **Modo compacto pro canvas lotado (1280×720)** — colapsar grupos, mini-cartões de nó, atalhos por
  teclado; camada de visualização sobre os mesmos nós (não muda o orquestrador). Essencial p/ 8+ nós. 🧊
- **Consciência read-only entre nós irmãos** — um agente lê status/branch/diff-resumido/notas de
  outro nó do MESMO grupo, sem escrever; mediado pelo orquestrador, escopo por cabo/grupo (CLI/MCP
  local). 🧊
- **Profiles de agente (presets nomeados)** — "Claude sandbox", "Codex yolo" etc. na cápsula
  principal ao criar nó; persistidos em `ui_state`, injetados no comando de spawn. 🧊
- **Custo/tokens por nó (versão lean)** — um número discreto no header do nó, sem dashboard. **Já
  está no backlog acima como F1** (triplo-confirmado: docs/16 + Fable + docs/17); é o mesmo item —
  não duplicar, só reforça a prioridade. 🧊
- Menores: **Nerd Font** no terminal (expor no `terminal_theme`/`ui_state`); botão "fim ao vivo" +
  indicador de "lendo histórico enquanto o agente produz"; **diff desde o último feedback**. 🧊
- **Já ENTREGUE (não confundir com pendência):** paleta de comandos (Ctrl-P), worktree por agente
  (Floors), grupos, minimapa, monitorar atividade — a pesquisa pediu, o projeto já tem.
