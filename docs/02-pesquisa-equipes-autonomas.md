# Pesquisa Profunda — Equipes Autônomas de Agentes com Orquestrador

> Relatório de deep research (verificação adversarial) — 2026-06-21
> 111 subagentes · 28 fontes · 139 afirmações extraídas · 25 verificadas · 20 confirmadas · 5 refutadas
> Objetivo: como devs profissionais montam equipes autônomas (orquestrador + subagentes) que fluem sozinhas, escalando ao humano só quando necessário — para (a) conduzir o desenvolvimento do **maestri-console** e (b) servir de referência de design do próprio produto.

---

## Resumo executivo

Devs profissionais usam o padrão **orchestrator-worker**: um **agente líder** analisa a tarefa, define estratégia, **decompõe em subtarefas**, gera **subagentes em paralelo** (3-5), e depois **agrega/sintetiza**, decidindo se precisa de mais trabalho. A Anthropic mediu esse padrão **superar um único agente em 90,2%** na sua avaliação interna de pesquisa.

Para **autonomia de longa duração com mínima intervenção**, a receita validada da Anthropic é um **harness de duas fases**: um agente **inicializador** (monta ambiente) + um agente de codificação **reinvocado a cada sessão**, que trabalha **UMA feature por vez**, mantém **estado externo persistente** (log de progresso, git, feature-status JSON — porque cada sessão começa sem memória) e é **obrigado a se autoverificar end-to-end** antes de marcar algo como "pronto".

Confiabilidade vem de **revisão adversarial** (o revisor é OBRIGADO a achar problemas; zero findings → HALT) combinada com **agentes realmente independentes** (evitar convergência de personas). Mas a revisão adversarial gera **falsos positivos** que exigem **filtragem humana** — e *esse filtro é o ponto natural de retorno ao humano*.

Para **custo/hardware limitado** (ARM, pouca RAM), a literatura recomenda arquitetura **heterogênea**: modelos pequenos (SLM) por padrão + LLM grande invocado **seletiva e raramente**. O **BMad** (já instalado, v6.8.0) oferece um template prático completo: **6 papéis nomeados**, **Party Mode** (modos que trocam velocidade por independência) e **revisão adversarial embutida** — sendo **human-in-the-loop por design**.

---

## 1. Padrão Orchestrator-Worker `confiança: alta`

- Agente líder: **analisa → estratégia → decompõe → gera subagentes em paralelo (3-5) → sintetiza → decide** se precisa de mais.
- Cada subagente tem **janela de contexto e ferramentas próprias**.
- Ganho medido: **+90,2%** vs agente único (Opus 4 líder + Sonnet 4 workers).

> ⚠️ **Caveats que mudam tudo:** o ganho é de avaliação **interna** da Anthropic; concentra-se em tarefas **breadth-first/paralelizáveis** (pesquisa) e **NÃO** em tarefas **fortemente acopladas como codificação interdependente** — que é justamente o trabalho dominante de construir o maestri-console. E **~80% da variância de performance é explicada pelo uso de tokens** (parte do "ganho" é simplesmente gastar mais).

Fontes: anthropic.com/engineering/multi-agent-research-system, bytebytego

## 2. Harness autônomo de longa duração (a receita da Anthropic) `confiança: alta`

A peça mais importante para o objetivo "fluir sozinho":

1. **Duas fases**: agente **inicializador** (`init.sh`, `claude-progress.txt`, commit git inicial) + agente de codificação **reinvocado a cada sessão**.
   - Nuance: é UM harness com **dois prompts** distintos, não dois agentes estruturalmente diferentes.
2. **Estado externo persistente** (porque *cada sessão começa sem memória*):
   - 📄 arquivo de log de progresso (`claude-progress.txt`)
   - 🔀 histórico **git** com mensagens descritivas
   - 📊 **feature-status JSON** (lista de features end-to-end → escolhe a de maior prioridade não feita)
3. **UMA feature por vez** — crítico. O agente tende a "one-shot" o app inteiro; restringir a uma feature por sessão foi *"critical"*.
4. **Autoverificação obrigatória** — agentes marcam como "pronto" sem testar. Só marcar "passing" após **teste end-to-end real** (automação de browser, "como um usuário humano faria").

Fonte: anthropic.com/engineering/effective-harnesses-for-long-running-agents

## 3. Confiabilidade & verificação `confiança: alta`

- **Revisão adversarial**: o revisor **é obrigado a achar problemas** — "looks good" proibido; **zero findings dispara HALT**. O BMad embute isso ("encontre ao menos 10 issues"; HALT se zero) — **skill já instalada** (`bmad-review-adversarial-general`).
- **Custo da revisão adversarial**: gera **falsos positivos** (nitpicks, mal-entendidos, alucinações). Estudos relatam **~1/3 das sugestões exigindo verificação humana**. ➡️ **Esse filtro de falsos positivos É o checkpoint humano racional** (conecta verificação ↔ human-in-the-loop).
- **Convergência de personas**: um único modelo simulando várias personas *"share a mind"* — perde independência. ➡️ **O crítico/revisor precisa ser um agente SEPARADO de verdade**, não a mesma instância fazendo papel.

> ❌ **Refutado (0-3):** a ideia de que **debate/votação entre agentes elimina a necessidade do humano**. Não há evidência forte disso — **a filtragem humana de falsos positivos permanece mandatória**.

Fontes: docs.bmad-method.org/explanation/adversarial-review, /party-mode, asdlc.io

## 4. O que o BMad já te dá (instalado, v6.8.0) `confiança: alta`

| Papel | Agente | Responsabilidade |
|---|---|---|
| Analyst | **Mary** (`bmad-agent-analyst`) | Pesquisa / discovery |
| Product Manager | **John** (`bmad-agent-pm`) | PRD / epics / stories |
| Architect | **Winston** (`bmad-agent-architect`) | Arquitetura |
| Developer | **Amelia** (`bmad-agent-dev`) | Dev de stories + code review + QA + sprint planning |
| UX Designer | **Sally** (`bmad-agent-ux-designer`) | UX/UI |
| Tech Writer | **Paige** (`bmad-agent-tech-writer`) | Documentação |

- **Party Mode** (`bmad-party-mode`): orquestra discussão entre agentes, cada um um **subagente real com pensamento independente**, com **você como orquestrador**. (Doc online cita 4 modos — Session/Auto/Subagent/Agent-team — que trocam velocidade por independência; ⚠️ o skill local v6.8.0 pode descrever um modelo mais simples: **verificar o comportamento real antes de depender dos 4 modos**.)
- **Revisão adversarial** embutida.

> ⚠️ **Tensão de design central:** o BMad é **human-in-the-loop por design** (gates/checkpoints, menos autônomo), enquanto o harness da Anthropic é projetado para **fluxo autônomo prolongado**. São **paradigmas opostos** — combiná-los exige **decidir conscientemente onde ficam os gates humanos**.

Fontes: docs.bmad-method.org/reference/agents, github.com/bmad-code-org/BMAD-METHOD, skills locais

## 5. Custo & hardware (ARM, 3.7 GB sem swap) `confiança: média`

- Arquitetura **heterogênea**: **SLMs por padrão**, **LLM invocado seletiva e raramente** (só quando raciocínio geral é essencial). Um SLM de **7B é 10-30x mais barato** que um de 70-175B.
- ➡️ Implicação direta para o uConsole: **orquestrador/raciocínio via LLM remoto (API)** + **workers locais pequenos** para tarefas estreitas. **NÃO carregar LLM grande localmente.**

> ⚠️ Vem de **position paper de vendor** (NVIDIA, interesse em inferência edge); "10-30x" é faixa ampla. A versão forte ("SLM basta para a maioria das invocações agênticas") foi **refutada (0-3)** — **adotar SLM com ceticismo e validar empiricamente** no uConsole.

Fontes: arxiv 2506.02153 (NVIDIA), arxiv 2510.03847

---

## ⚠️ Caveats globais

1. Métricas da Anthropic (90,2%) = avaliação **interna**, breadth-first; **não transfere** para codificação acoplada. ~80% da variância = uso de tokens.
2. Multi-agente **custa caro** (sinal de ~15x tokens vs chat consistente na literatura, embora a claim específica não tenha sido verificada nesta rodada).
3. SLM: position paper de vendor; validar localmente.
4. Verificação **sem humano** via debate/votação → **refutada**. Humano no filtro de falsos positivos é mandatório.
5. **Drift de versão no BMad** entre skill local e doc online (modos do party-mode) — checar o real.
6. **Cobertura incompleta de frameworks**: CrewAI, LangGraph, AutoGen/AG2, OpenAI Agents SDK, Google ADK foram pedidos mas **nenhuma claim sobreviveu à verificação** — comparativo fica para uma rodada dedicada (ver pergunta aberta #1).

## ❓ Perguntas em aberto

1. **Comparativo de frameworks em ARM/3.7GB**: qual de CrewAI / LangGraph / AutoGen / OpenAI Agents SDK / Google ADK roda viável no uConsole? (precisa rodada dedicada)
2. **Quais SLMs específicos** (modelo + quantização) rodam em ~3.7 GB com latência aceitável, e qual a divisão ótima orquestrador-remoto vs workers-locais (sem swap)?
3. **Taxonomia operacional de quando-escalar** ao humano (níveis de autonomia, gates p/ ações irreversíveis, detecção de loop) — a literatura não deu critérios quantificáveis; precisa definição própria.
4. **Topologia híbrida concreta**: como casar o harness autônomo da Anthropic (1 feature + estado externo + autoverificação) com papéis + revisão adversarial do BMad **sem que os gates do BMad quebrem o fluxo autônomo** — e onde exatamente posicionar os checkpoints humanos.

---

## 🎯 Recomendações concretas

### Para (a) conduzir o desenvolvimento do maestri-console

1. **Topologia híbrida**: usar os **papéis BMad** (Mary/John/Winston/Amelia + revisor adversarial) como estrutura de equipe, mas operar no **modo harness da Anthropic** durante a implementação: **1 story/feature por sessão + estado externo + autoverificação obrigatória**.
2. **Estado externo desde o dia 1**: `claude-progress.txt` (ou equivalente BMad sprint-status) + git descritivo + **feature-status JSON**. É o que permite "fluir sozinho" entre sessões sem memória.
3. **Gate humano no lugar certo** (alinha com sua regra "fundação = sua decisão"):
   - 🔴 **Humano decide**: spec, PRD, arquitetura, escolhas irreversíveis, **triagem dos falsos positivos** da revisão adversarial.
   - 🟢 **Autônomo**: implementação story-a-story, testes, refactor, dentro da fundação aprovada.
4. **Revisor adversarial sempre como agente SEPARADO** (independência real), obrigado a achar ≥N issues; **zero findings = HALT**.
5. **Custo**: orquestrador no modelo forte; workers em modelo mais barato; preferir paralelizar só tarefas **independentes** (codificação acoplada NÃO ganha com multi-agente).

### Para (b) referência de design do próprio produto

6. O maestri-console **é, por natureza, um orchestrator-worker** — os achados aqui são o blueprint: nó **orquestrador** que decompõe e delega a **terminais-worker**, com **estado externo compartilhado** (arquivos), **detecção de idle** para handoff (cf. pesquisa Maestri) e **gates human-in-the-loop** explícitos (o `tmux attach` do CAO é exatamente isso).
7. Embutir **revisão adversarial** e **papéis** (Lead/Coder/Reviewer/Tester) como primitivos do produto — exatamente o que o Maestri faz com subdiretórios + role.json.

---

### Fontes primárias
- anthropic.com/engineering/multi-agent-research-system
- anthropic.com/engineering/effective-harnesses-for-long-running-agents
- docs.bmad-method.org — /explanation/party-mode, /explanation/adversarial-review, /reference/agents
- github.com/bmad-code-org/BMAD-METHOD
- arxiv.org/pdf/2506.02153 (NVIDIA, SLM) · arxiv.org/abs/2510.03847
- blog.bytebytego.com/p/how-anthropic-built-a-multi-agent · asdlc.io
