# Pesquisa de diferenciais — n8n + frameworks/metodologias de agente (2026-07-02)

> Data: 2026-07-02 · PT-BR · Deep research (workflow adversarial, 112 subagentes, 120 claims
> extraídos → 25 verificados por voto 3x + 1 rodada de complemento focado) + 1 pesquisa focada
> de complemento (gstack/CrewAI, sem voto 3x, mas fonte primária + comunidade real).
> Objetivo: o usuário quer transformar o maestro console num **painel de orquestração visual
> estilo n8n** (canvas de nós/cabos) para terminais/agentes de codificação IA, dev solo — esta
> pesquisa colhe ideias concretas de n8n e de frameworks/metodologias de agente que o usuário
> admira (BMAD, spec-driven dev, GSD, Beast Mode, Claude Code Agent Teams, gstack, CrewAI).
> **NÃO copiar** nenhuma ferramenta — extrair mecanismo e adaptar à arquitetura já existente
> (canvas GTK4+VTE, cabos interativos, Team Templates c/ líder de grupo, Maestro mode, bwrap).
> Complementa (não duplica) `docs/02`, `docs/08`, `docs/09` — só o que é NOVO fica aqui.

## Resumo executivo

A pesquisa cobriu 8 alvos em duas fases (fonte oficial → comunidade). O achado mais valioso
não foi uma feature isolada, mas uma **confirmação estrutural**: o bug de escalada de
privilégio que corrigimos hoje no líder de grupo (PR #52 — `_recruited_by` do líder virava
autoridade de fato) tem **parentesco** com um bug documentado publicamente no CrewAI (issue
#4783, fechada como "not planned"). **Correção pós-revisão adversarial (Fable 5, 2026-07-02) —
alinha com o ADR-21:** os dois **não são a mesma classe** — o nosso é *over-grant/derivação de
autoridade* (o líder ganha poder que não devia); o do CrewAI é *under-provision/visibilidade*
(o manager hierárquico não enxerga os colegas e faz tudo sozinho). O eixo comum, mais abstrato,
é "comportamento emergindo de um detalhe incidental de construção em vez de um contrato
explícito" — registrar como **analogia direcional**, não como "mesma classe validada em
produção". Isso reforça que a regra já aplicada no projeto (autoridade nunca deriva de
fiação/decisão do agente, sempre de estado controlado pelo canvas) é o diferencial certo a
**generalizar** — mas ela se sustenta pelo **nosso próprio** bug, não pelo paralelo externo.

As ideias mais transplantáveis, por afinidade arquitetural: (1) o par Error Trigger +
payload estruturado do n8n vira um handler de falha por grupo; (2) os atalhos de teclado do
canvas do n8n (agrupar, pin, desativar) generalizam o modelo de grupo/líder já entregue; (3)
os primitivos de coordenação por arquivo dos Claude Code Agent Teams (lock de tarefa, mailbox
assíncrono) são o próximo passo natural do Maestro mode; (4) o caso real da própria Anthropic
(compilador Rust→C, 16 agentes paralelos) valida o isolamento por bwrap como formato correto
em escala, não só no contexto ARM/dev-solo; (5) a memória persistente por "party" do BMAD
v6.9.0 estende a regra de persistência de UI do projeto para **estado de agente**, não só UI.

---

## 1. n8n — UX do canvas (a referência explícita do usuário)

**O que faz de diferente:**
- **Error Trigger + error workflow por fluxo**: cada workflow pode ter um "error workflow"
  dedicado, disparado automaticamente quando a execução principal falha; o nó Error Trigger
  recebe um payload estruturado (ID de execução, mensagem de erro, stack trace, último nó
  executado, identidade do workflow). Fonte: [docs.n8n.io/build/flow-logic/handle-errors-gracefully](https://docs.n8n.io/build/flow-logic/handle-errors-gracefully),
  [docs.n8n.io/integrations/.../errortrigger](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.errortrigger) — 02/07/2026. `confirmado 3-0`
- **Atalhos nativos no canvas**: `Ctrl/Cmd+G` agrupa / `Ctrl/Cmd+Shift+G` desagrupa nós
  selecionados; `P` fixa ("pin") a saída de um nó pra inspeção sem re-rodar o fluxo; `D`
  desativa um nó no lugar (fica no canvas, mas é pulado na execução — distinto de deletar).
  Fonte: [docs.n8n.io/build/keyboard-shortcuts](https://docs.n8n.io/build/keyboard-shortcuts),
  [canvas-groups](https://docs.n8n.io/build/understand-workflows/workflow-components/canvas-groups),
  [pin-and-mock-data](https://docs.n8n.io/build/work-with-data/pin-and-mock-data) — 02/07/2026. `confirmado 3-0`
- **Focus Panel** (a partir de v1.113.0, anunciado 08/10/2025): parâmetros do nó num painel
  lateral em vez de modal — edita o nó sem perder de vista o diagrama do fluxo. *(fonte
  primária, extraído mas não passou pelo voto 3x — tratar como sinal, não fato duro)*
- Canvas evoluiu de Alpha→Beta (v1.70.0, 29/10/2024) com minimapa e ganho de performance
  (~20s→~3s de carregamento). *(idem, não votado)*

**Sentimento de comunidade (sourced):**
- Elogio de performance: usuário "Kool_Baudrillard" (28/10/2024, fórum n8n) — "the new canvas
  rocks, really, really performant!"
- Fricção real: dragging/pan do canvas exige tecla modificadora (Ctrl ou espaço+arraste),
  piora quando dá zoom ou quando notas/sticky notes ficam por baixo de nós (thread de sugestão
  de feature, 17/11/2024, community.n8n.io).
- Regressão relatada: sticky note passou a renderizar como painel de nó normal (com
  header/ações) em vez da UI simples — clicar pra editar fechava o painel na hora em vez de
  permitir digitar (thread de comunidade, fonte extraída na pesquisa).
- Reclamação de contraste: update p/ v2.20.9 trouxe UI de alto contraste que piorou
  legibilidade (perdeu pontilhado de fundo, ícones/texto menos visíveis, setas entre nós mais
  fracas) — thread "canvas contrast UI feedback after update to 2.20.9".

**Ideia extraída:** (1) cada Team/grupo materializado ganha um "handler de falha" designável —
nó de notificação ou o próprio líder — e o backend (sandbox/orquestrador) emite um evento de
falha estruturado (qual agente, último comando, texto de erro/exit code, id do grupo), pra
reagir automaticamente em vez de precisar notar visualmente um terminal morto. (2) atalho de
teclado pra agrupar/desagrupar nós **arbitrários** selecionados (não só via Team Templates);
estado de "pin" pro scrollback de um terminal (referência congelada enquanto os outros
continuam); estado de "desativar" distinto de dispensar/remover — silencia o cabo de entrada
de um nó sem desconectar, útil pra excluir temporariamente um membro do broadcast do grupo.

---

## 2. Movimento spec-driven development (Spec Kit, Kiro, OpenSpec)

**O que faz de diferente:**
- **GitHub Spec Kit**: pipeline de 5 slash-commands — `/speckit.constitution` (princípios) →
  `/speckit.specify` (requisitos, sem stack técnica) → `/speckit.plan` (arquitetura) →
  `/speckit.tasks` (lista ordenada por dependência) → `/speckit.implement`, mais opcionais
  `/speckit.clarify`/`/speckit.analyze`/`/speckit.checklist`. Repousa em 4 princípios:
  intent-first, specs estruturadas/guardrailed, refinamento iterativo multi-etapa, forte
  dependência da capacidade do modelo. Fonte: [github.com/github/spec-kit](https://github.com/github/spec-kit),
  [concepts/sdd.html](https://github.github.com/spec-kit/concepts/sdd.html) — 02/07/2026. `confirmado 3-0`
  *(claim refutada 0-3: que a spec seria "diretamente executável" num sentido literal — a
  moldura correta é aspiracional/arquitetural, não geração literal de código a partir só da spec)*
- **AWS Kiro**: converte prompt em specs estruturadas (`requirements.md`/`design.md`/
  `tasks.md`) que formam um grafo de dependência e executam em "ondas" (tarefas concorrentes
  dentro da mesma onda); testes baseados em propriedade (via Hypothesis, Automated Reasoning
  Group da AWS) que verificam propriedades do código no espaço de entradas — mais perto de
  fuzz testing que unit test. Fonte: [kiro.dev](https://kiro.dev/), [kiro.dev/docs/specs](https://kiro.dev/docs/specs/),
  [kiro.dev/blog/property-based-testing](https://kiro.dev/blog/property-based-testing/) — 02/07/2026. `confirmado 3-0`
  **Cautela de comunidade**: issue [kirodotdev/Kiro#8402](https://github.com/kirodotdev/Kiro) (2026) confirma que a
  execução paralela por onda existe mas relata problemas reais (conflito de recurso, bug de
  rastreamento de status, perda de contexto).
- **OpenSpec**: 4 slash-commands — `/opsx:explore` (parceiro de raciocínio lendo código, SEM
  compromisso, antes de criar qualquer artefato) → `/opsx:propose` (cria pasta de mudança com
  proposta/specs/design/tasks) → `/opsx:apply` (implementa) → `/opsx:archive` (preserva +
  atualiza specs), mais dashboard de progresso; suporta 25+ ferramentas de IA. Fonte:
  [github.com/Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec) — 02/07/2026. `confirmado 3-0`

**Ideia extraída:** o estágio "explore" do OpenSpec (uma passada de leitura/discussão SEM
compromisso, antes de criar qualquer artefato) é diferente do fluxo mais cerimonioso do BMAD
(já em uso) — pode virar um modo "scout" leve pra um agente recrutado solo, que lê/discute
antes do líder de grupo formalmente materializar um Team Template completo, evitando gastar
nós/terminais com ideias que não vingam. O conceito de "onda" do Kiro (tarefas agrupadas por
dependência, agentes da mesma onda rodam concorrentes, a próxima onda só libera quando a
anterior fecha) cabe bem no líder de grupo — ele já teria como sequenciar sub-tarefas dos
membros em ondas de dependência em vez de só atribuição estática de papel — mas a cautela do
Kiro (conflitos de recurso em paralelo) é um aviso pra construir lock explícito de claim de
tarefa (ver §4) em vez de assumir que "simplesmente funciona".

---

## 3. GSD ("Get Sh*t Done") e BMAD Method v6.9.0

**GSD**: descrito pelo próprio criador (TÂCHES) como sistema leve de meta-prompting/context
engineering/spec-driven pra Claude Code, ~64.600 estrelas no GitHub. **Repositório arquivado
(read-only) desde 31/05/2026**, migrado pro sucessor "Open GSD". Fonte:
[github.com/gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done) — 02/07/2026.
`confirmado 3-0 (fatos); refutado 1-2 (a moldura "alternativa mais enxuta ao BMAD" não é
sourced ao próprio projeto, só auto-descrição)`. **Cautela**: se for buscar ideias do GSD,
pesquisar o sucessor "Open GSD"/org `open-gsd`, não o repo arquivado.

**BMAD Method v6.9.0** (lançado 21/06/2026) — "Party-mode revamp": parties customizáveis e
salváveis, com **memória de sessão persistente append-only por party** (retoma contexto entre
sessões), 4 modos de execução (`auto`/`session`/`subagent`/`agent-team`), e um "Code Review
Crew" pré-carregado de 5 lentes adversariais. Fonte:
[CHANGELOG.md do BMAD-METHOD](https://raw.githubusercontent.com/bmad-code-org/BMAD-METHOD/main/CHANGELOG.md) — 02/07/2026. `confirmado 3-0`

**Ideia extraída:** (1) memória persistente por party é a peça que falta na regra de
persistência de UI do próprio projeto — ela cobre `ui_state` (janela/config), mas não **estado
de agente**; uma instância de Team Template materializada poderia manter um arquivo de memória
append-only por grupo, sobrevivendo fechar/reabrir o canvas, espelhando como `ui_state` já
persiste. (2) os 4 modos de execução são uma taxonomia útil pra expor explicitamente na UI do
Maestro mode — o usuário escolhe o modo por time recrutado em vez de um comportamento
implícito único. (3) um "Code Review Crew" pré-carregado de 5 lentes adversariais é um Team
Template pronto pra distribuir como padrão junto dos templates que já existem.

---

## 4. Claude Code Agent Teams + caso real da Anthropic (compilador C)

**Agent Teams** (feature oficial, experimental, opt-in — `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`):
coordenação via artefatos de arquivo puro — lista de tarefas compartilhada em
`~/.claude/tasks/{team-name}/` com estados pending/in-progress/completed e bloqueio por
dependência; config do time em `~/.claude/teams/{team-name}/config.json`; um sistema
"**Mailbox**" de entrega automática de mensagem entre agentes (sem polling); **lock de
arquivo** pra evitar corrida quando dois membros tentam reivindicar a mesma tarefa. Fonte:
[code.claude.com/docs/en/agent-teams](https://code.claude.com/docs/en/agent-teams) — 02/07/2026.
`confirmado 3-0 (mecânica)`; `refutado 1-2` (a moldura mais forte de "cada teammate roda em
context window totalmente independente, comunica direto, sem gestão central" não é sourced tão
fortemente quanto a mecânica de coordenação em si).

**Caso real da Anthropic** (16 agentes Claude Opus 4.6 em paralelo construindo um compilador
Rust→C, ~2.000 sessões, ~$20K de custo de API, compilador de 100K linhas p/ x86/ARM/RISC-V):
**sem orquestrador central** — cada agente escolhia sozinho a "próxima tarefa mais óbvia";
coordenação via **um container Docker por agente** (cada um clonando um bare-git compartilhado
pro seu próprio `/workspace` local) e **locks simples baseados em arquivo** (um arquivo-texto
por tarefa numa pasta compartilhada), sincronizando via ciclos `git pull`/merge/`push`/unlock.
Fonte: [anthropic.com/engineering/building-c-compiler](https://www.anthropic.com/engineering/building-c-compiler) — 02/07/2026.
`confirmado 3-0`, corroborado por repo GitHub companheiro e cobertura de imprensa (The
Register, InfoQ, fev/2026).

**Ideia extraída — a de maior relevância arquitetural desta pesquisa inteira**: isso é
arquiteturalmente muito próximo dos primitivos já corrigidos hoje no Maestro mode
(`recruit`/`wire`/`dismiss`/`reassign`, autoridade por linhagem controlada pelo host, nunca
pelo cabo). Adotar o padrão de **lock de arquivo por claim de tarefa** pra delegação do líder
de grupo evita dois membros disputando a mesma sub-tarefa. E vale considerar uma abstração
literal de "**Mailbox**" como a próxima camada acima do cabo/wire síncrono atual — uma fila de
mensagem assíncrona por nó que sobrevive desconexão/reconexão, em vez do modelo atual
totalmente síncrono via cabo. O caso do compilador também **valida** a escolha já feita de
isolamento por bwrap (um workspace isolado por agente) como o formato certo em escala — não só
uma economia forçada pelo hardware ARM/dev-solo, é o mesmo padrão que a própria Anthropic usou
em produção com 16 agentes.

---

## 5. Beast Mode (Burke Holland / GitHub Copilot)

Implementado inteiramente como artefato de system-prompt — um arquivo `.chatmode.md` (YAML
frontmatter declarando quais ferramentas de plataforma já existentes ele pode chamar + corpo
de instrução em linguagem natural), **sem código próprio por trás**: "it's just a prompt".
Fonte: [burkeholland.github.io/posts/beast-mode-3-1](https://burkeholland.github.io/posts/beast-mode-3-1/) — 02/07/2026.
`confirmado 3-0`. *(claim refutada 0-3: que o fluxo plano→todo-list→execução teria sido
"diretamente inspirado" pelo comportamento de todo-list em PR do Copilot coding agent — é uma
alegação causal não sourced)*

**Ideia extraída:** a lição central é que um loop persistente plano→todo-list→memória dá pra
alcançar com **zero infraestrutura nova**, só com um system-prompt bem desenhado + acesso a
ferramentas já existentes. Relevante pro comportamento do líder de grupo (já implementado na
Fase D): antes de partir pra código de orquestração novo, vale testar se o comportamento
desejado do líder é ajustável só via prompt.

---

## 6. gstack (Garry Tan / YC)

**O que faz de diferente:** 23+ slash-commands nativos do Claude Code, cada um uma persona de
escopo fechado (CEO, Eng Manager, Designer, QA, Release Engineer, CSO, SRE, Doc Writer...),
encadeáveis num pipeline Think→Plan→Build→Review→Test→Ship→Reflect. Problema declarado: agente
genérico sem guardrail produz "vibe coding" descontrolado; a persona por fase **constrange** o
foco em vez de dar autoridade ampla a um único agente. MIT, self-hosted, runtime-agnóstico
("works with any python agent, not Rails-focused" — o próprio Tan). Fontes:
[github.com/garrytan/gstack](https://github.com/garrytan/gstack),
[x.com/garrytan/status/2033020984093978930](https://x.com/garrytan/status/2033020984093978930) — 02/07/2026.
*(pesquisa focada de complemento, sem voto 3x, mas fonte primária direta)*

**Sentimento de comunidade** (thread HN [item 47355173](https://news.ycombinator.com/item?id=47355173)):
- Elogio: "josh2600" relata ganho real de qualidade/velocidade nas decisões (as personas geram
  respostas de múltipla escolha CEO/eng que aceleram decisão); "dmppch" reconhece a
  "role decomposition" (personas distintas por planning/review/QA/shipping) como ideia válida.
- Crítica de escala: "dmppch" — o modelo git-clone-and-copy funciona solo, mas não escala
  quando repos diferentes precisam de gates de review/QA divergentes.
- **Crítica de segurança relevante pro nosso contexto**: "zippolyon" relata um loop autônomo
  de 70min que injetou URLs de staging em config de produção **sem trava alguma**, propondo
  auditoria externa.
- Crítica de mérito: Mo Bitar chamou de "um punhado de prompts num arquivo texto"; Sherveen
  Mashayekhi atribuiu a visibilidade ao cargo de Tan na YC, não ao artefato em si.

**Ideia extraída:** não copiar slash-commands — adaptar o *gate de persona por fase* como
checkpoint obrigatório no líder de grupo: antes de uma ação irreversível (ex.: `git push`,
dismiss em massa), o líder passa por um nó "reviewer" do próprio template (um cabo de
aprovação), fechando exatamente a falha que "zippolyon" relatou no gstack (agente autônomo sem
trava agindo em produção).

---

## 7. CrewAI

**O que faz de diferente:** arquitetura em duas camadas — **Flows** (controle determinístico,
event-driven, state management — o "gerente"/definição de processo) e **Crews** (times
autônomos de agentes com papel, delegados por um Flow pra resolver uma sub-tarefa complexa).
Agente definido por `role`/`goal`/`backstory`; `allow_delegation` (default `False`) habilita
delegação entre colegas; `process=sequential` (ordem fixa) vs `hierarchical`
(`manager_agent`/`manager_llm` coordena). Fontes:
[docs.crewai.com/en/introduction](https://docs.crewai.com/en/introduction),
[docs.crewai.com/en/concepts/agents](https://docs.crewai.com/en/concepts/agents) — 02/07/2026.

**Sentimento de comunidade — achado mais relevante desta pesquisa:** issue
[crewAIInc/crewAI#4783](https://github.com/crewAIInc/crewAI/issues/4783) (02/07/2026):
"Manager agents only execute tasks using their own tools and never delegate... effectively
making hierarchical behave like sequential", **mesmo com `allow_delegation=True`** e sem
`manager_agent` pré-definido (manager criado dinamicamente via `manager_llm`). **Status:
fechada como "not planned"**, com fix proposto em PR #4782 pelo próprio reporter. Corroborado
no fórum oficial ([community.crewai.com/t/.../7010](https://community.crewai.com/t/issue-only-manager-agent-appears-in-self-agents-when-using-process-hierarchical/7010)):
o manager não enxerga os colegas pra delegar e acaba fazendo tudo sozinho. Crítica de
arquitetura adicional (Towards Data Science, ["Why CrewAI's Manager-Worker Architecture Fails"](https://towardsdatascience.com/why-crewais-manager-worker-architecture-fails-and-how-to-fix-it/)):
crews hierárquicos consomem tokens excessivos, geram loops de delegação circular (dois agentes
delegando a mesma query 12 ciclos seguidos), alta latência.

**Ideia extraída (a mais validante desta pesquisa toda):** o problema-raiz do CrewAI é que a
**legalidade da delegação depende do julgamento do próprio agente-gerente**, não de um estado
externo confiável — **exatamente a classe de bug (confused deputy) corrigida hoje** em
`wire`/`dismiss`/`reassign` do maestro console (PR #52, líder de grupo não ganha mais
autoridade de comando de graça). Isso não é uma ideia nova a implementar — é uma **confirmação
externa e sourced** de que a regra já aplicada (autoridade nunca deriva de fiação/decisão do
agente, sempre de estado controlado pelo canvas/host) é o diferencial certo, e vale
**generalizar como princípio explícito de arquitetura** (ver síntese, item 3) em vez de tratar
como um fix pontual — o Flows-vs-Crews do CrewAI tenta essa separação control-plane vs
execução-autônoma, mas falha em aplicá-la de forma coerente no modo hierárquico.

---

## Síntese — diferenciais de maior potencial (ranqueados, valor × esforço p/ contexto ARM/dev-solo)

1. 🥇 **Generalizar a regra "autoridade nunca deriva de fiação/decisão do agente" como
   princípio de arquitetura explícito (ADR)**, não só como o fix pontual do líder de grupo.
   *Por quê no topo:* esforço quase-zero e fecha uma classe de bug que já mordeu o projeto
   duas vezes (confused-deputy no `wire`/`dismiss` + PR #52). **Status pós-Fable (2026-07-02):
   JÁ FEITO — virou o ADR-21;** é higiene concluída, não "o que construir a seguir". O paralelo
   com o CrewAI #4783 vale como **reforço direcional** (ferramentas maduras erram no mesmo eixo
   control-plane vs execução), **não** como "mesma classe validada em produção" — a regra se
   sustenta pelo nosso próprio bug (ver correção no Resumo executivo e o ADR-21).

2. 🥈 **Lock de arquivo por claim de tarefa + "Mailbox" assíncrono** (Claude Code Agent Teams +
   caso do compilador da Anthropic). Extensão natural do Maestro mode já existente; evita
   corrida quando o líder de grupo delega sub-tarefas a mais de um membro. Esforço: médio.

3. 🥉 **Handler de falha estruturado por grupo** (Error Trigger do n8n). Fecha a dor de
   "observabilidade fraca" já identificada em `docs/08` com um mecanismo concreto e testado em
   produção por uma ferramenta madura. Esforço: médio (evento estruturado no orquestrador +
   UI de designar handler).

4. **Checkpoint de aprovação obrigatório antes de ação irreversível do líder** (gate de
   persona do gstack + o incidente relatado por "zippolyon"). Fecha um risco real e já
   documentado publicamente (loop autônomo sem trava). Esforço: baixo-médio (um nó
   "reviewer"/cabo de aprovação no próprio Team Template).

5. **Memória persistente por grupo materializado** (BMAD v6.9.0 party memory), estendendo a
   regra de persistência de UI (`ui_state`) pra **estado de agente**. Esforço: médio (arquivo
   append-only por grupo + carregamento no `__init__`).

*Bônus de baixo esforço, alto valor de polimento:* atalhos de teclado do n8n — agrupar/
desagrupar nós arbitrários, "pin" de scrollback de um terminal, "desativar" um nó sem
desconectar — generalizam o modelo de grupo/líder já entregue sem exigir arquitetura nova.

## Caveats desta pesquisa
- gstack e CrewAI não passaram pelo voto adversarial 3x da rodada principal (orçamento de
  verificação priorizou os outros 6 alvos); foram cobertos numa pesquisa focada de complemento
  com fonte primária + comunidade real, mas sem o mesmo nível de contraverificação dos outros 6.
- Vários achados de sentimento de comunidade do n8n (Focus Panel, minimapa, fricção de
  dragging, regressão de sticky note, queixa de contraste) foram extraídos mas não entraram no
  corte de 25 claims votados — tratar como sinal direcional, não fato duro.
- GSD está com o repo arquivado (31/05/2026) — se for aprofundar, pesquisar o sucessor
  "Open GSD", não este snapshot.
