# Plano — Briefing persistente por grupo (brief + objetivo atual)

> **✅ ENTREGUE (2026-07-12) — v0.65.0 / ADR-27.** Implementado como especificado pós-emendas
> (bloco `BRIEF` via `engine/briefs.py`; nascimento host-side em `node_cfg birth_group`;
> re-carimbo no `_do_respawn` e no save; sanitização + caps; delete limpa tudo). Decisões do
> §10 validadas pelo usuário ("segue as recomendações do Fable").
>
> Data: 2026-07-12 · PT-BR · Origem: `docs/15` (item 2026-07-02, da pesquisa de comunidade
> `docs/17` — dor "usei um dia e esqueci o plano"). Protocolo do `AGENTS.md`: **analisar →
> planejar → pesquisar → validar → codar.** A proposta original foi submetida a **pesquisa de
> validação + revisão adversarial (Fable 5, 2026-07-12)**: veredito **APROVADA COM EMENDAS** —
> a emenda central (E1) **inverteu o mecanismo** (injeção em prompt → bloco em arquivo no
> workspace, o mesmo trilho dos papéis). Ver §9.
> **Não codar antes da validação do usuário (§10 lista as decisões em aberto).**

## 1. Objetivo (o quadro de avisos do grupo)

Hoje, o contexto de projeto ("objetivo desta empreitada, decisões tomadas, o que NÃO fazer")
vive **na cabeça do humano** e se dilui a cada agente novo: quem nasce no grupo recebe só o
**cargo** (instrução do role) e a **tarefa** (prompt/intenção) — nunca o **projeto**. Este plano
dá a cada grupo do canvas um **brief persistente** + um campo curto **"objetivo atual"**:

1. **Brief por grupo** — texto curto (decisões/contexto), editado SÓ pelo host, persistido.
2. **Entrega automática** — todo agente que **nasce no grupo** (FAB, recruit, montar equipe)
   recebe o brief **por arquivo no workspace** (o CLI lê sozinho ao iniciar) — cobrindo também
   headless (`run_team`) e reattach/respawn de graça.
3. **Visível pro humano** — o "objetivo atual" acessível na cápsula/diálogo do grupo (ataca o
   "esqueci o plano" também do lado humano).

## 2. O que já existe (REUSAR — não reinventar) — mapeado no código 2026-07-12

- **O trilho do mecanismo (a descoberta que define o design):** os papéis JÁ entregam contexto
  por arquivo — `install_role_block`/`remove_role_block` (`roles.py:156-169`) escrevem um **bloco
  MARCADO** em `CLAUDE.md` **e** `AGENTS.md` do workspace isolado do agente ("a IA lê no start",
  `roles.py:136`; claude lê CLAUDE.md, codex lê AGENTS.md — `roles.py:5-6`). O brief usa o MESMO
  padrão (bloco `BRIEF` próprio, append seguro, idempotente).
- **Headless lê de graça:** `agent_run.py:32-35` — o plano de execução roda com
  **`cwd = workspace`** → o CLI headless (`claude -p`/`codex exec`) carrega o CLAUDE.md/AGENTS.md
  do workspace igual ao terminal vivo. Um mecanismo cobre os dois mundos.
- **Como os agentes nascem (os funis a interceptar):** FAB clique-pra-posicionar
  (`_start_placing`/`_commit_placing`); recruit do Maestro mode → `_new_agent_terminal` com
  `_place_below(manager)` (`canvas.py:4779`); montar equipe → `_materialize_team`
  (`canvas.py:6523+`). **Nos caminhos FAB/recruit NÃO existe "primeiro prompt"** — o spawn é um
  CLI num VTE (`_spawn_into`, `canvas.py:374`); por isso a via prompt era inimplementável (E1).
- **Pertença a grupo é GEOMÉTRICA e efêmera:** `_group_members` (`canvas.py:7106-7112`) =
  sobreposição ≥25% da área do item, computada on-the-fly. Serve pra desenhar/arrastar junto —
  NÃO serve como fonte de autoridade/semântica (arrastar 3px muda a resposta; recruit cai
  `_place_below` e pode ficar FORA do retângulo). → E2.
- **Workspace é gravável pelo agente** (política declarada, `workspace.py:5-7`) → o espelho do
  brief no workspace é rabiscável pelo próprio agente. → E3.
- **Template já tem semente:** `TeamTemplate.description` (`team_templates.py:55`) — campo
  existente, serializado; serve de brief-semente sem criar campo novo.
- **UI pronta pra receber:** grupo tem cápsula contextual desde a v0.63.0 (`docs/28`) e o padrão
  de diálogo/`_dialog_footer` da v0.62.0; persistência por chave `ui_state` é o padrão do budget
  (ADR-22) — sem migração de schema.

## 3. Pesquisa ao vivo (2026-07-12, Fable 5) — o que a comunidade validou

- **A dor é real e sem dono no concorrente:** vibe-kanban #3424 — usuário pede literalmente
  *"ability to give a 'context brief' for a worktree that is automatically injected into each
  new session"* (aberta, verificada 2026-07-12). — github.com/BloopAI/vibe-kanban/issues/3424
- **Padrão consolidado da indústria:** instruções por projeto/container injetadas em toda
  sessão — CLAUDE.md (Claude Code: carregado no início de TODA sessão; root **re-lido do disco
  pós-compactação**; guia oficial: "specific and concise", <200 linhas — code.claude.com/docs/en/memory),
  AGENTS.md (Codex, mesmo padrão), Cursor/Copilot rules, Claude/ChatGPT **Projects** (instruções
  por container, automáticas, escritas pelo dono). "Grupo = Projeto" é analogia consolidada.
- **Injeção única em prompt DECAI** ("rule amnesia" pós-compactação — comunidade Claude Code:
  issue #24460, projeto post_compact_reminder re-injetando via hooks). A via ARQUIVO se
  re-ancora sozinha (re-lido no start e pós-compact). Reforça a E1.
- **Brief curto > brief longo (evidência):** Chroma "Context Rot" (2025, 18 modelos) — degradação
  não-uniforme com o tamanho do input, mesmo em tarefas simples (research.trychroma.com/context-rot).
  → cap de tamanho (E4).
- **Vetor de ataque documentado:** "Rules File Backdoor" (Pillar Security, mar/2025; CSA "README
  Injection", mar/2026) — instruções maliciosas escondidas em arquivos de regras via **Unicode
  invisível** (zero-width/bidi). → sanitizar no save (E3).
- **O que NÃO copiar:** memória compartilhada mutável-por-agente de CrewAI/LangGraph/AutoGen
  (store/typed state que agentes escrevem) — é exatamente o canal de contaminação que o ADR-17
  proíbe. O recorte certo: brief **read-only para agentes, escrito pelo host**.

## 4. Design v1 (pós-Fable) — bloco em arquivo, fonte da verdade no host

```
host (humano edita no diálogo do grupo — ÚNICO escritor)
        │  fonte da verdade: Store (chave ui_state por gid, padrão budget/ADR-22)
        ▼
grupo.brief + grupo.objetivo ──(re-carimbo a cada spawn/respawn/reattach)──►
                                          workspace do membro
                                          ├─ CLAUDE.md  ◄── claude lê no start
                                          └─ AGENTS.md  ◄── codex lê no start
(arquivo = ESPELHO descartável, bloco marcado BRIEF; NUNCA lido de volta pro Store)
```

### 4.1 Dado + edição (host-only)
- Duas chaves por grupo no Store (`ui_state`, padrão ADR-22 — sem coluna nova/migração):
  `group_brief_<gid>` (~800–1000 chars, cap exato = decisão §10) e `group_goal_<gid>` (~80 chars).
- Edição no **diálogo do grupo** (e botão na cápsula contextual — nível §10): editor multi-linha
  com **contador de caracteres** e **sanitização no save** (strip de zero-width/bidi/Unicode-tags
  — precedente Rules File Backdoor). Mostrar **data da última edição** (mitiga brief obsoleto).
- **Host-only por construção:** nenhum comando `maestri` lê/escreve brief; retomar o princípio
  do budget ("zerar só na UI do host") — agente NUNCA edita o quadro (ADR-17).

### 4.2 Entrega (bloco `BRIEF` no workspace — espelha o mecanismo dos roles)
- Novo par `install_brief_block`/`remove_brief_block` em `roles.py` (ou módulo irmão), MESMO
  formato de bloco marcado com delimitadores próprios (`BRIEF_BEGIN/END`), append seguro,
  idempotente (re-instalar substitui o bloco, não duplica).
- **Re-carimbo em todo start:** spawn (nascimento), respawn, reload/reattach de órfão — o host
  sobrescreve o bloco ANTES do CLI subir. Rabisco do agente no espelho dura só até o próximo
  start e contamina só a si mesmo (workspaces isolados). O arquivo **nunca** é lido de volta.
- Conteúdo do bloco: objetivo atual + brief + data da última edição (o agente sabe a idade do
  contexto que recebeu).

### 4.3 "Grupo de nascimento" = decisão HOST-SIDE, nunca geometria (E2)
Coerente com o ADR-21 (autoridade/semântica nunca nasce de layout visual):
- **FAB (clique-pra-posicionar):** grupo cujo retângulo contém o **ponto do clique** (decisão no
  momento do gesto humano, não da posição final do card).
- **Recruit (`maestri recruit`):** o grupo **do manager** no momento do recruit (mesma pertença
  host-side; se o manager não está em grupo, o recrutado nasce sem brief).
- **Montar equipe:** o(s) grupo(s) **que a materialização criou** — com `TeamTemplate.description`
  como brief-semente (campo já existente).
- Nó **arrastado** pra dentro do grupo depois: re-carimbo na mudança de pertença, **válido no
  próximo start** (o CLI só lê o arquivo ao iniciar) — documentado, sem fingir efeito
  mid-session (E5).

### 4.4 Visibilidade pro humano
- "Objetivo atual" na **cápsula contextual** do grupo (tooltip ou linha no popover — decisão
  §10). **Fora do v1:** desenhar no header cairo do grupo (tela 1280×720, header já apertado —
  corte E6b).

## 5. O que fica FORA do v1 (cortes YAGNI — E6)

- **Vínculo `run_team`↔grupo:** o engine (`orchestrator.py`) **não conhece grupos** (conceito do
  canvas). Criar o vínculo é encanamento novo sem valor — a via arquivo já entrega o brief no
  headless (cwd = workspace). CORTADO.
- **Objetivo desenhado no header cairo do grupo:** apertado demais em 1280×720; fica na cápsula.
- **Campo novo de brief em template:** usar `description` existente como semente. Sem campo novo.
- **Re-injeção no reattach como item separado:** vem DE GRAÇA pela via arquivo (o CLI relê no
  start). Não é trabalho, é consequência.

## 6. Segurança (modelo ADR-17 aplicado)

- **Escrita:** só o host, só pela UI. Espelho no workspace é sobrescrito a cada start; nunca
  lido de volta. Sanitização de Unicode invisível no save.
- **Riscos residuais ACEITOS (documentar, não fingir que fecha):**
  1. **Fan-out de brief envenenado** — se o humano colar texto malicioso/errado no brief, propaga
     a todo recém-nascido do grupo (o brief é um amplificador). Mitigação: cap curto + legível
     (revisão humana de relance) + sanitização. Coerente com ADR-17 (o dono não é o adversário).
  2. **Brief obsoleto** — sem fix técnico; a data de edição visível é o alerta.
  3. **Auto-edição mid-session** — o agente pode rabiscar o próprio espelho durante a sessão;
     corrige no próximo start; sem escrita cruzada entre workspaces.
  4. **Escopo silencioso:** o brief (como os roles) só materializa quando há workspace — nó-shell
     puro fica fora. Documentar pra não virar "bug" percebido.

## 7. Pontos no código

- `roles.py` (ou irmão `briefs.py`) — `install_brief_block`/`remove_brief_block` (bloco marcado
  próprio, espelho de `install_role_block:156`).
- `canvas.py` — funis de nascimento: `_commit_placing` (FAB, grupo pelo ponto do clique),
  dispatch do recruit (`:4757-4800`, grupo do manager), `_materialize_team` (`:6523+`, semente
  do template); re-carimbo no respawn/reload (`_do_respawn`) e reattach; diálogo do grupo +
  cápsula (editor, contador, sanitize, data).
- `store.py`/`CanvasModel` — chaves `group_brief_<gid>`/`group_goal_<gid>` (get/set, padrão
  `ui_state`); limpeza no delete do grupo (E7 — junto do caminho `_close_group`).
- Sanitizador puro (gi-free, testável): strip de zero-width/bidi/tags + cap.

## 8. Definition of done (rascunho)

- Testes `.venv` (gi-free): sanitizador (zero-width/bidi/tags removidos; cap); bloco BRIEF
  instalado/atualizado/removido idempotente; conteúdo com objetivo+brief+data.
- Testes gi (python do SISTEMA): grupo de nascimento por caminho (FAB pelo clique / recruit pelo
  manager / equipe pelo grupo criado — mock só de widget); re-carimbo no respawn; delete do grupo
  limpa chaves + blocos dos membros.
- **E2E (a prova central):** para CADA caminho de nascimento, o CLAUDE.md/AGENTS.md do workspace
  do membro CONTÉM o brief após o spawn (ler o arquivo real, não mock).
- Persistência: fechar/reabrir → brief/objetivo do grupo intactos ("abre igual fechou").
- **Teste visual no device** (antes do merge): editar brief num grupo → criar agente pelo FAB
  dentro dele → perguntar ao agente qual o objetivo → ele responde o brief.
- `ruff` + suite + boot smoke + CHANGELOG + 1 bump. Avaliar ADR curto (brief = contexto
  host-only por grupo via bloco de arquivo; agente nunca escreve).

## 9. Pesquisa de validação + revisão adversarial (Fable 5, 2026-07-12)

**Veredito: APROVADA COM EMENDAS.** A dor é real (re-verificada na fonte primária) e o padrão é
consenso da indústria — mas a proposta original tinha um **furo fatal de mecanismo**. Emendas:

1. **E1 (CRÍTICA — inverteu o design):** "injetar no 1º prompt" é **inimplementável** nos
   caminhos FAB/recruit — não existe 1º prompt (spawn = CLI no VTE). Trocar pela via ARQUIVO
   (bloco marcado em CLAUDE.md/AGENTS.md do workspace, trilho dos roles). Bônus: headless lê de
   graça (cwd=workspace), reattach/`--resume` relê no start, sobrevive à compactação (rule
   amnesia documentada na via prompt). **O "nível avançado" original era o alicerce; o "básico"
   (prompt) morre.**
2. **E2 (CRÍTICA):** "nasce no grupo" não pode ser geometria (`_group_members` = sobreposição
   ≥25%, efêmera; recruit cai `_place_below`, pode ficar fora do retângulo). Grupo de nascimento
   = decisão host no momento do gesto (clique/manager/equipe). Coerência ADR-21.
3. **E3 (ALTA):** "host-only escreve" sozinho não fecha — o espelho vive em workspace GRAVÁVEL
   pelo agente. Regras: Store é a verdade; re-carimbo a cada start; nunca ler de volta;
   sanitizar Unicode invisível no save (Rules File Backdoor).
4. **E4 (MÉDIA):** cap de tamanho (~800–1000 chars; objetivo ~80) — evidência Context Rot +
   guia oficial ("concise adere mais"). Contador na UI.
5. **E5 (MÉDIA):** drag-in não tem efeito mid-session (arquivo lido só no start) — re-carimbar
   na mudança de pertença e DOCUMENTAR a latência, não fingir efeito imediato.
6. **E6 (YAGNI):** cortar do v1 — vínculo run_team↔grupo (engine não conhece grupo); objetivo
   no header cairo (tela apertada); campo novo em template (usar `description`); "re-injeção no
   reattach" como item (vem grátis).
7. **E7 (BAIXA):** ciclo de vida — delete do grupo remove blocos dos membros + limpa chaves;
   `ui_state` por gid evita migração de schema.

**Riscos que sobram** (mesmo com host-only): fan-out de brief envenenado (amplificador — colar
texto sugerido por agente propaga; mitigação: curto+legível+sanitize; residual aceito, ADR-17),
brief obsoleto (data visível como alerta), auto-edição mid-session (contamina só a si; corrige
no start), nó-shell sem workspace fica fora (documentar).

**Fontes** (consultadas 2026-07-12): code.claude.com/docs/en/memory · github.com/BloopAI/
vibe-kanban/issues/3424 · research.trychroma.com/context-rot · CSA "README Instruction
Injection" (mar/2026) · Pillar Security "Rules File Backdoor" (mar/2025) ·
github.com/Dicklesworthstone/post_compact_reminder · claude-code issue #24460 · comparativos de
memória CrewAI/LangGraph/AutoGen e Claude vs ChatGPT Projects. Código citado verificado:
`roles.py:5-6,51,136,156-169` · `agent_run.py:32-35` · `workspace.py:5-7` ·
`team_templates.py:55` · `canvas.py:374, 4576, 4779, 6523+, 7106-7112`.

## 10. DECISÕES — VALIDADAS com o usuário (2026-07-12, "segue as recomendações do Fable")

- ✅ **Design v1 como um todo** (via arquivo E1 + nascimento host-side E2 + segurança E3 +
  cortes E6).
- ✅ **Cap:** brief 1000 chars · objetivo 80 (contador na UI; corte no salvar).
- ✅ **"Objetivo atual" pro humano:** no diálogo do grupo (⚙) — opção (c), a recomendada como
  mínimo digno; header cairo segue fora (E6).
- ✅ **Armazenamento:** chaves `ui_state` por gid (`group_goal_/group_brief_/group_brief_ts_`)
  — padrão budget/ADR-22, sem migração de schema.
- ✅ **Cápsula:** SEM botão 📋 novo — a pílula do grupo continua enxuta `[⚙][●][🗑]` (decisão
  de design da v0.63.0); o brief mora no ⚙.

Implementado na branch `feat/briefing-grupo` (mesmo PR deste plano, padrão docs/28) com testes
gi-free + gi e teste visual no device antes do merge.
