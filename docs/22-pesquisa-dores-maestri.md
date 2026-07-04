---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'market'
research_topic: 'Dores e feedback negativo de usuários do theMaestri'
research_goals: 'Catalogar dores reais, reclamações, limitações e pedidos não atendidos de usuários do theMaestri (fontes vivas: comunidades, fóruns, Twitter/X, GitHub, reviews), para reaproveitar como oportunidades no maestro-console'
user_name: 'Hydekel'
date: '2026-07-03'
web_research_enabled: true
source_verification: true
---

# Research Report: market

**Date:** 2026-07-03
**Author:** Hydekel
**Research Type:** market

---

## Research Overview

# Pesquisa de Mercado: Dores e feedback negativo de usuários do theMaestri

## Inicialização da Pesquisa

### Entendimento Confirmado

**Tópico**: Dores, reclamações, limitações e pedidos não atendidos de usuários do theMaestri (app original que o maestro-console clona para o uConsole)
**Objetivos**: Catalogar as dores REAIS dos usuários — somente feedback negativo — para que o agente possa reaproveitá-las como oportunidades de produto no maestro-console
**Tipo**: Pesquisa de mercado (voz do cliente / análise de dores)
**Data**: 2026-07-03
**Escopo confirmado pelo usuário na delegação em 2026-07-03** (delegação explícita via /bmad-help com escopo pré-definido)

### Escopo da Pesquisa

**Foco (adaptado — NÃO é análise de tamanho de mercado):**

- Dores e reclamações recorrentes de usuários reais do theMaestri
- Limitações técnicas e de UX apontadas pela comunidade
- Pedidos de recurso não atendidos (feature requests abertos/ignorados)
- Fricções de preço/licenciamento/plataforma, se reclamadas
- EXCLUÍDO: elogios, feedback positivo, marketing do próprio produto

**Fontes (pesquisa AO VIVO, sempre com fonte + data):**

- Comunidades e fóruns: Reddit, Hacker News, Discord públicos
- Twitter/X e redes sociais
- GitHub: issues e discussions (do produto e de projetos relacionados)
- Reviews (lojas de app, diretórios de ferramentas) e blogs/comparativos

**Metodologia:**

- Dados atuais da web com verificação de fonte (fonte + data em cada achado)
- Múltiplas fontes independentes para afirmações críticas
- Nível de confiança declarado para dados incertos
- Cada dor catalogada com: descrição, evidência/citação, fonte, data, frequência aparente

### Próximos Passos

1. ✅ Inicialização e escopo (este passo)
2. Insights de clientes — varredura de dores por fonte
3. Panorama competitivo (como as dores se relacionam a alternativas)
4. Síntese estratégica — dores → oportunidades para o maestro-console

**Status**: Escopo confirmado, pronto para a análise detalhada

---

## Índice

1. [Sumário Executivo](#sumário-executivo)
2. [Escopo e inicialização da pesquisa](#research-overview)
3. [Perfil dos Usuários e Contexto de Uso](#perfil-dos-usuários-e-contexto-de-uso-quem-sente-as-dores)
4. [Catálogo de Dores](#catálogo-de-dores-somente-feedback-negativo) — A. Estabilidade · B. Recursos · C. Orquestração · D. Plataforma/lock-in · E. Custo · F. UX/proposta de valor
5. [Sinais de Mercado](#sinais-de-mercado-contexto-competitivo-das-dores)
6. [Síntese Estratégica: Dores → Oportunidades para o maestro-console](#síntese-estratégica-dores--oportunidades-para-o-maestro-console)
7. [Metodologia e Limitações](#metodologia-e-limitações)
8. [Anexo A — Varredura bruta por canal](#anexo-a--varredura-bruta-por-canal)
9. [Anexo B — Lista consolidada de fontes](#anexo-b--lista-consolidada-de-fontes)
10. [Anexo C — Softwares similares ao Maestri (panorama competitivo)](#anexo-c--softwares-similares-ao-maestri-panorama-competitivo)

---

## Sumário Executivo

O **Maestri** (themaestri.app, dev: Evert Junior/@evertjr, lançado ~mar-abr/2026) é um app macOS nativo de canvas infinito para orquestrar agentes de código. A varredura de 4 canais em paralelo (Reddit/HN · GitHub/Product Hunt · X/redes sociais · reviews/blogs) em 2026-07-03 catalogou **29 dores** distribuídas em 6 categorias. As mais graves e recorrentes:

1. **Instabilidade séria** — perda de trabalho, teclado que morre no meio da sessão, canvas que congela em uso prolongado (múltiplos relatos independentes, Setapp + Product Hunt).
2. **Consumo de RAM extremo** — até 20 GB com várias instâncias de Claude Code (relato de usuário + confirmação do dev: 500–700 MB por instância).
3. **Orquestração não confiável** — o recurso central (delegação agente→agente) falha com frequência (~70% de sucesso segundo review editorial; relatos de agentes criando subagentes em vez de delegar; cabo agente→shell que não executa).
4. **Lock-in duro de plataforma** — só macOS 26.2+ / Apple Silicon, closed source, sem tracker público de bugs; já motivou clones open-source (open-maestri, canvas-ade).
5. **Custo empilhado** — app pago + assinaturas dos agentes por fora (US$20–200/mês por pessoa).

Sinal de mercado relevante: o app tem **quase zero discussão em comunidade aberta** (Reddit: nada indexado; HN: 2 submissões com 0 comentários) — o feedback vive no Setapp (37 reviews, 95% positivas; as dores acima são a minoria negativa) e num Discord fechado. Cada dor abaixo tem citação, fonte, data e nível de confiança, pronta para reuso como oportunidade no maestro-console (seção final).

---

## Perfil dos Usuários e Contexto de Uso (quem sente as dores)

- **Perfil dominante:** dev macOS/Apple Silicon *early adopter*, solo ou time pequeno, rodando **2–4+ agentes CLI em paralelo** (Claude Code, Codex, OpenCode, Gemini) em sessões longas — é nesse uso intenso que o freeze, a RAM e a delegação falha aparecem. Vários são "early adopters seriais" de ferramentas de agente (um relatou ter testado ~9 orquestradores antes).
- **Subgrupo Setapp:** assinantes de catálogo que esperam maturidade de app publicado — mais duros com bugs ("a side project that Setapp shouldn't have ever published").
- **Subgrupo influencer dev CN/JP:** power users que publicam reviews (X/Threads/YouTube/note/zenn) — criticam polimento e observabilidade, mas continuam usando.
- **Quem REJEITA o produto (não-clientes com dor):** devs Linux/Windows e donos de Mac Intel (excluídos por requisito), defensores de open-source (motivaram clones), e power users de terminal rápido (tmux/Warp/cmux) para quem o canvas é um passo a mais.
- Nenhum sinal de uso corporativo/equipe grande nas reclamações — reviews editoriais apontam justamente que "só macOS tranca fora a maioria das equipes profissionais".

_Fontes: Setapp customer reviews (mai/2026), Product Hunt (abr/2026), X @yrzhe_top (mar/2026), note.com (abr/2026), zenn.dev (abr/2026), agent-finder.co (mai/2026)._

---

## Catálogo de Dores (somente feedback negativo)

Legenda de confiança: **Alta** = citação lida na fonte primária e/ou corroborada por 2+ fontes independentes · **Média** = citação via snippet de busca ou fonte única não corroborada · **Baixa** = número/afirmação sem corroboração independente.

### A. Estabilidade e bugs (categoria mais grave)

| # | Dor | Evidência (citação) | Fonte · data · autor | Confiança |
|---|-----|--------------------|---------------------|-----------|
| A1 | **Perda de trabalho; teclado morre no meio da sessão** | "DO NOT TRUST THIS APP WITH ANYTHING IMPORTANT… keyboard randomly stops working mid session… I just lost SO MUCH WORK" ("não confie neste app com nada importante… o teclado para de responder no meio da sessão… perdi MUITO trabalho") — dev reconheceu: bug de *focus-management* "difícil de reproduzir pela complexidade do canvas" | [Setapp reviews](https://setapp.com/apps/maestri/customer-reviews) · 2026-05-15 · Brandan (v0.25.4) | **Alta** (2 agentes confirmaram) |
| A2 | **Canvas/workspace congela em uso prolongado** — UI trava, terminais continuam rodando por baixo | "after sometime the workspace gets stuck, terminals are doing their work, but I cant drag them and buttons become unresponsive" ("depois de um tempo o workspace trava… não consigo arrastá-los e os botões param de responder") — **sem resposta do maker** na thread | [Product Hunt](https://www.producthunt.com/products/maestri) · ~abr/2026 · @abu_nowshad_md_jawad | **Alta** |
| A3 | **Botões que não funcionam / UI com lag; link no terminal abre janela de erro** | "At first glance, it's already pretty buggy. Buttons don't work, or when they do, they're laggy" ("de cara já é bem bugado; botões não funcionam, ou funcionam com lag"); clicar em link dentro do terminal gera erro em vez de abrir (diferente de Terminal/iTerm) | [Setapp reviews](https://setapp.com/apps/maestri/customer-reviews) · 2026-05-31 · John B (v0.28.0) | **Alta** |
| A4 | **Performance "clunky" (travada)** | "Needs a tweak to fix the clunky performance" | [Setapp reviews](https://setapp.com/apps/maestri/customer-reviews) · 2026-05-06 · InquisitiveBadger (v0.24.1) | **Alta** |
| A5 | **Canvas engasga + observabilidade fraca em cadeias longas de agentes** | "Still early. Canvas lags sometimes, and long agent chains could use better observability" ("o canvas engasga às vezes, e cadeias longas de agentes precisariam de melhor observabilidade") | [X @yrzhe_top](https://x.com/yrzhe_top/status/2037581353458212914) · ~2026-03-27 | **Alta** |
| A6 | **Scroll lateral quebrado com mouse Logitech** | "I cant sidescroll using my Logitech mouse" | [Setapp reviews](https://setapp.com/apps/maestri/customer-reviews) · 2026-05-04 · Abdul Habeeb (v0.23.4) | **Média-alta** |
| A7 | **Bug de terminal TUI: botões ativavam no hover** (SGR mouse reporting) — afetava Claude Code/OpenCode dentro do Maestri; o próprio dev corrigiu upstream | "TUI apps that use SGR mouse reporting… interpret the lowercase 'm' as a button release, which causes interactive elements like buttons to activate on hover instead of requiring a click" | [SwiftTerm PR #520](https://github.com/migueldeicaza/SwiftTerm/pull/520) · 2026-04-02 · evertjr (dev) | **Alta** (evidência direta) |

### B. Consumo de recursos

| # | Dor | Evidência | Fonte · data · autor | Confiança |
|---|-----|-----------|---------------------|-----------|
| B1 | **Consumo de RAM extremo: ~20 GB com várias instâncias de Claude Code** | "My biggest complaint is how much memory it takes up… using 20 gigs of RAM" — resposta do dev: cada instância de Claude Code usa **500–700 MB** e "soma rápido" | [Setapp reviews](https://setapp.com/apps/maestri/customer-reviews) · 2026-05-18 · Paul Chambers (v0.26.1) | **Alta** (2 agentes confirmaram; dev corroborou a mecânica) |

### C. Orquestração não confiável (o coração do produto falha)

| # | Dor | Evidência | Fonte · data · autor | Confiança |
|---|-----|-----------|---------------------|-----------|
| C1 | **Delegação agente→agente inconsistente** — às vezes o agente cria os próprios subagentes em vez de delegar | "Delegating tasks to agent sometimes work, and sometimes the agent which should delegate the work creates his own sub agents" — sem resposta do maker | [Product Hunt](https://www.producthunt.com/products/maestri) · ~abr/2026 · @abu_nowshad_md_jawad | **Alta** |
| C2 | **Cabo agente→shell não executa comandos** | "If I connect an agent with a terminal (shell), if I tell the agent to run commands on the connected shell it does not do it" | [Product Hunt](https://www.producthunt.com/products/maestri) · ~abr/2026 · mesmo autor | **Alta** |
| C3 | **Handoff automático ~70% confiável; exige intervenção regular** — e o agente receptor precisa ficar com a janela **desfocada** para ser monitorado | "70% success rate on automatic agent handoffs means you still intervene regularly"; "receiving agent must stay unfocused to be monitored" | [agent-finder.co](https://agent-finder.co/reviews/maestri) · 2026-05-21 (editorial) + citado no teardown [canvas-ade PR #29](https://github.com/ch923dev/canvas-ade/pull/29) · 2026-06-02 | **Média** (número sem corroboração independente; direção consistente com C1/C2) |
| C4 | **Compartilhamento de estado/contexto entre agentes é manual** — a "memória compartilhada" é o usuário conectar sticky notes; nada automático para limites de contexto com vários agentes simultâneos | Pergunta sem solução de produto: "how you handle state sharing and context window limits when several agents are interacting at the same time" → resposta do maker: sticky notes | [Product Hunt](https://www.producthunt.com/products/maestri) · ~abr/2026 · @y_taka | **Alta** (lacuna admitida na resposta) |
| C5 | **Merge conflict de git não resolvível na UI ("Floors")** — precisa sair pro IDE/terminal | Autor testou paralelizar agentes e reporta que a resolução de conflito não é suportada na UI | [zenn.dev](https://zenn.dev/youjinfox/articles/bb3facc650adb1) · 2026-04-19 (blog pessoal) | **Média-alta** |

### D. Plataforma, lock-in e canal fechado

| # | Dor | Evidência | Fonte · data | Confiança |
|---|-----|-----------|--------------|-----------|
| D1 | **Só macOS, e agressivo: exige macOS 26.2+ e Apple Silicon** (sem Intel, sem macOS antigo) | Admitido pelo vendor ("Maestri currently runs on macOS only"; "macOS 26.2+ · Apple Silicon"); note.com: "a base de usuários alvo é limitada… não roda em Macs Intel" | [themaestri.app/docs](https://www.themaestri.app/en/docs/intro) · 2026-07-03 + [note.com](https://note.com/masa_wunder/n/n0f6c7214a6db) · 2026-04-13 | **Alta** (vendor + 3 fontes) |
| D2 | **Exclui equipes profissionais / fricção em time com SO misto** | "macOS-only locks out most professional development teams"; "creates friction in mixed-OS teams" | [agent-finder.co](https://agent-finder.co/reviews/maestri) · 2026-05-21 (editorial) | **Média** (editorial, review possivelmente sintética) |
| D3 | **Closed source e SEM tracker público de bugs** — feedback só via Discord fechado/e-mail; bugs reportados em público (Product Hunt) ficam sem resposta | Verificado: nenhum repo/issue tracker público existe (busca exaustiva GitHub); site só aponta Discord/X/e-mail | Varredura GitHub · 2026-07-03 | **Alta** (dor estrutural) |
| D4 | **Ecossistema de skills fechado** — clone open-source cita isso como motivação | Tabela do README: "Skill ecosystem: Open, extensible \| Maestri: Closed"; "License: GPL v3 \| Maestri: Proprietary" | [open-maestri](https://github.com/zlh-428/open-maestri) · repo criado 2026-05-15 | **Alta** (como evidência da motivação do clone) |
| D5 | **Sem suporte a agentes remotos** (ex.: agente rodando num Raspberry Pi na LAN via wss/REST) | "could not find how to use agents that do not run locally" | Setapp reviews (via snippet de busca) · mai/2026 | **Média** (não conferido página a página) |
| D6 | **Privacidade "local-first" não cobre o tráfego dos agentes** — cada agente continua mandando dados pro seu provedor | Admitido pelo vendor: "Coding agents… may send data to their respective providers. Maestri does not control or intercept that traffic" | [themaestri.app](https://www.themaestri.app/en) · 2026-07-03 + note.com · 2026-04-13 | **Alta** (admitida) |

### E. Custo e licenciamento

| # | Dor | Evidência | Fonte · data | Confiança |
|---|-----|-----------|--------------|-----------|
| E1 | **Custo real empilha: app pago + assinatura de cada agente por fora** | "your real cost is $19/month for Maestri Pro plus $20-40/month for the agents"; usuário PH: "won't it get expensive? Claude Code alone costs $100–200 per license per person if used actively" — maker não negou o custo | [agent-finder.co](https://agent-finder.co/reviews/maestri) · 2026-05-21 + [Product Hunt](https://www.producthunt.com/products/maestri) · ~abr/2026 · @natalia_iankovych | **Alta** (2 fontes) |
| E2 | **Free limitado a 1 workspace**; multi-workspace, atalhos de navegação e 2º Mac são pagos (Pro) | Homepage/pricing do vendor; zenn confirma a limitação na prática | [themaestri.app](https://www.themaestri.app/en) · 2026-07-03 + zenn · 2026-04-19 | **Alta** (admitida) |
| E3 | **Modelo de preço inconsistente entre fontes** — US$19/mês (mai/2026) vs US$18 compra única (site em jul/2026; tweet JP abr/2026); /en/pricing retorna 404 | Discrepância registrada por 3 agentes independentes | agent-finder (mai/2026) vs [themaestri.app](https://www.themaestri.app/en) (2026-07-03) vs [X @AI_masaou](https://x.com/AI_masaou/status/2043635016295682089) (2026-04-13) | **Alta** (a inconsistência em si) |

### F. UX e proposta de valor questionada

| # | Dor | Evidência | Fonte · data | Confiança |
|---|-----|-----------|--------------|-----------|
| F1 | **Curva de aprendizado íngreme** para quem nunca usou fluxo multi-agente | "Learning curve is steep if you have never worked with multi-agent workflows" | [agent-finder.co](https://agent-finder.co/reviews/maestri) · 2026-05-21 | **Média** (editorial) |
| F2 | **Canvas = passo extra** para power users de multi-janela/terminal (tmux/Warp/cmux); atrito de atalhos para quem vem do tmux | note.com: "a operação de canvas parece adicionar uma etapa a mais" (explicitamente não recomendado pra quem é rápido em CMUX/Warp); zenn: atrito adaptando atalhos do tmux; comparativos: Warp ganha em terminal UX, cmux em "fast, focused execution" | [note.com](https://note.com/masa_wunder/n/n0f6c7214a6db) · 2026-04-13 + [zenn.dev](https://zenn.dev/youjinfox/articles/bb3facc650adb1) · 2026-04-19 | **Alta** (3 fontes) |
| F3 | **Sem valor para trabalho single-agent** — Cursor/Copilot fazem melhor o fluxo de 1 agente | "You primarily need inline code completion… Cursor and GitHub Copilot handle that workflow better"; zenn: "pouca utilidade pra quem completa tarefas com um único agente" | agent-finder · 2026-05-21 + zenn · 2026-04-19 | **Alta** (2 fontes) |
| F4 | **Posicionamento questionado vs. IDE-native** (Cursor/Windsurf): em que cenário é "strictly better"? | Objeção de venda nº 1 na thread de launch | [Product Hunt](https://www.producthunt.com/products/maestri) · ~abr/2026 · @curiouskitty | **Alta** |
| F5 | **Assistente "Ombro" preso ao Apple Intelligence on-device — sem BYO API key** (usuário quer Claude/GPT na camada de monitoramento) | "I'd love the option to plug in my own API key for OpenAI or Anthropic models instead. Apple's on-device models are fine for light summaries…" | [X @yrzhe_top](https://x.com/yrzhe_top/status/2037581353458212914) · ~2026-03-27 | **Alta** |
| F6 | **Sem suporte a nerdfonts** | "only wish it handled nerdfonts" | Setapp reviews (via snippet) · mai/2026 | **Média** |
| F7 | **Timer/cron de lembrete pros agentes mal integrado** ("enterrado nas rotinas") | "buried in the routines" | Setapp reviews (via snippet) · mai/2026 | **Média** |

---

## Sinais de Mercado (contexto competitivo das dores)

- **Quase zero presença em comunidade aberta:** Reddit — nada indexável até 2026-07-03 (WebSearch, DuckDuckGo, API PullPush, subreddits r/ClaudeAI, r/ClaudeCode, r/macapps, r/LocalLLaMA); Hacker News — 2 submissões (2026-03-30 pelo próprio dev e 2026-04-11), **2 pontos e 0 comentários cada** ([1](https://news.ycombinator.com/item?id=47573259), [2](https://news.ycombinator.com/item?id=47729574)); Bluesky/Mastodon — nada. O boca-a-boca real está no X (cena dev CN/JP/BR), Setapp e Discord fechado.
- **A nota geral no Setapp é ALTA (95%, 37 reviews)** — as dores deste catálogo são a minoria negativa, não a média. Quem reclama de estabilidade continua usando (exceto o caso de perda de trabalho, A1).
- **As dores já estão gerando concorrentes diretos:** [open-maestri](https://github.com/zlh-428/open-maestri) (GPL v3, macOS 14+, skills abertas — clone motivado explicitamente por proprietário/requisito alto/ecossistema fechado, criado 2026-05-15) e [canvas-ade "Expanse"](https://github.com/ch923dev/canvas-ade/pull/29) (teardown competitivo de 2026-06-02 apontando cross-platform como o *moat* que o Maestri não cobre: "Maestri's APFS CoW is Mac-only, not portable"). O próprio **maestro-console** se encaixa nessa onda.
- **Concorrentes citados nas comparações:** Warp (terminal UX), cmux (execução rápida focada), Cursor/Windsurf (IDE-native), Conductor. O Maestri perde nas comparações justamente onde as dores apontam: velocidade de execução pura e plataforma.

---

## Síntese Estratégica: Dores → Oportunidades para o maestro-console

Cada oportunidade referencia as dores que a justificam. Estado atual do maestro-console anotado quando já há resposta implementada.

1. **Cross-platform/Linux-ARM como razão de ser** (D1, D2, D4 + teardown canvas-ade): a maior dor estrutural do Maestri — só macOS 26.2+/Apple Silicon, fechado — é exatamente o espaço do maestro-console (Linux/ARM/uConsole, código próprio). O teardown competitivo independente confirma: cross-platform é o *moat* que o Maestri não cobre.
2. **Frugalidade de RAM como feature de primeira classe** (B1, A4): 20 GB de RAM no Mac vs. o maestro-console rodando num CM4. A feature **em desenvolvimento agora (unload de nó / kill-and-resume)** ataca diretamente a dor mais citada com número concreto — vale posicioná-la como resposta direta ("cada instância de agente = 500–700 MB; descarregue as ociosas").
3. **Estabilidade e gestão de foco como diferencial testável** (A1, A2, A3, A7): as dores mais graves do Maestri são de *focus-management* e freeze de UI — o dev dele mesmo admite que é difícil no canvas. Regra do projeto já cobre (testar runtime antes de declarar pronto); vale criar testes específicos de stress (sessões longas, muitos nós) e de foco de teclado.
4. **Delegação confiável e auditável** (C1, C2, C3, C4): o coração do Maestri falha ~30% das vezes e o estado compartilhado é manual. O maestro-console já tem envelope/ledger/budget-cap host-side (ADR-17, ADR-21/22) — caminho: garantir que delegação seja *verificável* (o host sabe se o comando chegou e rodou), não fire-and-forget via PTY.
5. **Observabilidade de cadeias de agentes** (A5, C3): pedido explícito de usuário power ("long agent chains could use better observability") — o monitor de atividade (v0.53.0) e o medidor de custo (v0.54.0) já são passos nessa direção; expor histórico/estado da cadeia de delegação é a lacuna.
6. **Canal público de feedback** (D3): o Maestri não tem tracker público e bugs ficam sem resposta; o maestro-console em repo GitHub público com issues já entrega isso de graça.
7. **Custo transparente** (E1): a objeção "não fica caro?" não tem resposta no Maestri; o medidor de custo/tokens por nó + budget cap (v0.54.0/v0.55.0) é resposta direta — mostrar o gasto em vez de escondê-lo.
8. **Cuidado com as MESMAS armadilhas** (F1, F2, F3): as dores de proposta de valor valem para qualquer canvas de agentes, incluindo este projeto — canvas pode ser passo extra pra power user de terminal, e não agrega em fluxo single-agent. Mitigações: atalhos de teclado de primeira classe e valor claro no fluxo multi-agente (que no uConsole é viável só com a frugalidade do item 2).

**Riscos de leitura:** (a) volume total de feedback ainda é pequeno (app com ~3 meses de vida, 37 reviews) — dores podem mudar de perfil conforme o produto amadurece (versões v0.23→v0.28 já num ritmo rápido de correção); (b) o número "70% de handoff" tem fonte única editorial possivelmente sintética; (c) replies do X e Discord fechado ficaram fora — o volume real de reclamação é provavelmente MAIOR que o capturado.

---

## Metodologia e Limitações

**Método:** 4 agentes de pesquisa em paralelo (2026-07-03), um por canal — (1) Reddit+HN, (2) GitHub+Product Hunt, (3) X/Bluesky/Mastodon/Threads/YouTube/Discord, (4) reviews/diretórios/blogs — com regra rígida de só reportar o que foi realmente lido, cada dor com citação + URL + data + autor. Consolidação com deduplicação entre canais e nível de confiança por item (achados corroborados por 2+ canais independentes marcados).

**Limitações declaradas:**
- **X/Twitter:** replies e quote-tweets (onde mora a maioria das críticas) invisíveis sem login — subestimação provável.
- **Discord oficial** ("Maestri Users", convite V9SRtFDcKy): fechado a indexação — o canal primário de feedback do produto ficou 100% fora.
- **Reddit:** www/old.reddit bloqueados pelo fetcher; cobertura via buscadores + PullPush (historicamente incompleto pra 2026).
- **Setapp:** página paginada/dinâmica — pode haver mais reviews negativas não capturadas; itens D5, F6, F7 vieram de snippets de busca (não conferidos na página, marcados como confiança Média).
- **agent-finder.co** aparenta ser review sintética/SEO — seus números (ex.: 70%) receberam peso menor que relatos de usuários.
- **YouTube:** comentários não renderizam via fetch; único vídeo achado (JP) ficou sem leitura de comentários.

---

## Anexo A — Varredura bruta por canal

Registro do que cada agente buscou e encontrou (ou não), para auditoria e para repetir a varredura no futuro.

### A.1 Reddit — NADA ENCONTRADO

Estratégias executadas, todas sem resultado relevante: WebSearch `site:reddit.com maestri app canvas claude code agents` · `"themaestri.app" OR "themaestri" reddit` · `site:reddit.com "maestri" claude OR codex OR "coding agents"` · buscas dirigidas a r/ClaudeAI, r/ClaudeCode, r/macapps, r/LocalLLaMA, r/ChatGPTCoding · DuckDuckGo HTML · API PullPush (submissions + comments, com filtro por subreddit) · Redlib (403) · reddit.com/search.json e old.reddit (bloqueados pelo fetcher). Só homônimos irrelevantes (café "Maestri House", pincéis "3 Maestri", música italiana). **Conclusão:** não há discussão indexável sobre o Maestri no Reddit até 2026-07-03 — nem positiva nem negativa.

### A.2 Hacker News / Lobsters — ZERO DISCUSSÃO

Via API hn.algolia.com: 2 submissões, ambas com **2 pontos e 0 comentários** — "Maestri – Infinite canvas where coding agents work side by side (macOS)", autor evertjr (o próprio dev), 2026-03-30 ([item 47573259](https://news.ycombinator.com/item?id=47573259)); e "Maestri – Infinite Canvas for coding agents", autor surrTurr, 2026-04-11 ([item 47729574](https://news.ycombinator.com/item?id=47729574)). Lobsters: 0 resultados. **Dado de mercado em si: 2 tentativas de launch no HN sem nenhuma tração.**

### A.3 GitHub — SEM TRACKER PÚBLICO; dores aparecem indiretamente

Queries: `gh search repos maestri` · `gh api search/issues` com `themaestri`, `"themaestri.app"`, `"maestri" canvas agents`, `maestri "claude code"` · busca por repo de feedback (`maestri in:name feedback` → 0) · listagem dos repos do dev (evertjr) · WebSearch `site:github.com`. O Maestri é **closed source, sem repo público nem repo de issues** — site só aponta Discord, X e e-mail. Achados indiretos:
- **[open-maestri](https://github.com/zlh-428/open-maestri)** (zlh-428, criado 2026-05-15, 10 stars): clone GPL v3 que documenta as dores que o justificam — proprietário, macOS 26.2+ vs 14.0+, código fechado, ecossistema de skills fechado.
- **[canvas-ade PR #29](https://github.com/ch923dev/canvas-ade/pull/29)** (ch923dev, 2026-06-02): teardown competitivo citando handoff ~70% confiável, "receiving agent must stay unfocused to be monitored" e "Maestri's APFS CoW is Mac-only, not portable".
- **[SwiftTerm PR #520](https://github.com/migueldeicaza/SwiftTerm/pull/520)** (evertjr, 2026-04-02): fix upstream do próprio dev pra bug que fazia botões de TUI (Claude Code/OpenCode) ativarem no hover.

### A.4 Product Hunt — bugs sem resposta + objeções de venda

[producthunt.com/products/maestri](https://www.producthunt.com/products/maestri), launch ~abr/2026 (datas exibidas como "3mo ago"). Thread visível com 6 comentadores; reviews formais: apenas 1 (5 estrelas, positiva). Negativo extraído: workspace congela (A2), delegação inconsistente (C1), cabo agente→shell não executa (C2) — os três do mesmo usuário @abu_nowshad_md_jawad, **sem resposta do maker**; custo empilhado (@natalia_iankovych, E1); estado compartilhado manual (@y_taka, C4); posicionamento vs IDE-native (@curiouskitty, F4). Limite: comentários paginados/aninhados podem não ter carregado.

### A.5 Twitter/X — acesso parcial (sem replies)

Contas confirmadas: dev **@evertjr** (Evert Junior, brasileiro), oficial **@maestriapp** (criada abr/2026). Método: Google `site:x.com` + API fxtwitter (só tweet-raiz; replies/quotes invisíveis sem login). Achados: thread crítica de @yrzhe_top ~2026-03-27 (lag no canvas, observabilidade fraca em cadeias longas, Ombro sem BYO API key — A5/F5) e tweet informativo @AI_masaou 2026-04-13 (requisitos duros + preço US$18 buy-once). Posts JP/CN/BR restantes eram elogiosos; nenhuma reclamação indexada de crash/preço/Windows-Linux.

### A.6 Bluesky / Mastodon / Threads — quase nada

Bluesky: API pública bloqueada (403 no proxy); via Google, zero menções. Mastodon: nada indexado. Threads: 1 post relevante — @yrzheee (mesma pessoa do @yrzhe_top), 2026-03-27, review "não é porque ele seja perfeito…" com continuação cortada sem login; as críticas desse autor estão cobertas pela versão X do fio.

### A.7 YouTube — sem review em inglês; comentários inacessíveis

Nenhum vídeo-review em inglês (só homônimos: Claude Canvas, RunMaestro, UiPath Maestro — descartados). 1 vídeo JP (canal do まさお/@AI_masaou, ~2026-04-13, [watch?v=8c7k_BIs_3o](https://www.youtube.com/watch?v=8c7k_BIs_3o)) com enquadramento positivo; comentários não renderizam via fetch.

### A.8 Discord — canal primário de feedback, FECHADO

Servidor oficial "Maestri Users" ([convite](https://discord.com/invite/V9SRtFDcKy), linkado no rodapé do site). Não indexado (não está no AnswerOverflow); impossível ler sem login. **O canal onde o feedback do produto realmente acontece ficou 100% fora da varredura.**

### A.9 Setapp (reviews de usuários) — a fonte negativa mais rica

[setapp.com/apps/maestri/customer-reviews](https://setapp.com/apps/maestri/customer-reviews) — 37 reviews, nota 95% (negativos são minoria, mas concretos e versionados): Brandan 2026-05-15 v0.25.4 (perda de trabalho, A1) · Paul Chambers 2026-05-18 v0.26.1 (20 GB RAM, B1) · John B 2026-05-31 v0.28.0 (botões/lag/links, A3) · InquisitiveBadger 2026-05-06 v0.24.1 (performance, A4) · Abdul Habeeb 2026-05-04 v0.23.4 (scroll Logitech, A6). Via snippets (não conferidos na página): agentes remotos (D5), nerdfonts (F6), cron/routines (F7), "a side project that Setapp shouldn't have ever published". Achado por 3 agentes independentes — corroboração cruzada forte. Página paginada: pode haver mais.

### A.10 Reviews editoriais / diretórios / blogs

- [agent-finder.co/reviews/maestri](https://agent-finder.co/reviews/maestri) (2026-05-21): fonte dos itens D2, C3 (70%), E1, F1, F3 — **aparenta review sintética/SEO, peso reduzido**.
- [note.com (guia JP)](https://note.com/masa_wunder/n/n0f6c7214a6db) (2026-04-13): canvas = passo extra (F2), base limitada por hardware (D1), privacidade não cobre agentes (D6), custos à parte (E1).
- [zenn.dev](https://zenn.dev/youjinfox/articles/bb3facc650adb1) (2026-04-19): free = 1 workspace (E2), merge conflict fora da UI (C5), atrito tmux (F2), inútil single-agent/Linux (F3).
- Sem contras: [alternativeto.net](https://alternativeto.net/software/maestri/about/) (zero comentários), [macaiapps.com](https://www.macaiapps.com/apps/maestri/), [topaihubs.com](https://www.topaihubs.com/item/maestri) (2026-03-29), [productcool.com](https://www.productcool.com/product/maestri) (2026-03-24), [clauday.com](https://clauday.com/article/1267c13c-8e58-4259-b7f3-cc316570f3a6) (2026-03-25).

### A.11 Vendor (docs/homepage) — limitações admitidas

[themaestri.app](https://www.themaestri.app/en) + [docs/intro](https://www.themaestri.app/en/docs/intro) (consultados 2026-07-03): "Maestri currently runs on macOS only" · macOS 26.2+ / Apple Silicon · "Maestri is not an AI agent itself" (exige agentes instalados) · privacidade não cobre tráfego dos agentes · Free = 1 workspace; Pro US$18 one-time, 2 Macs, 7 dias de trial · `/en/pricing` retorna 404.

---

## Anexo B — Lista consolidada de fontes

| Fonte | Tipo | Data | Usada em |
|-------|------|------|----------|
| [setapp.com/apps/maestri/customer-reviews](https://setapp.com/apps/maestri/customer-reviews) | Reviews de usuários | mai/2026 (v0.23–v0.28) | A1, A3, A4, A6, B1, D5, F6, F7 |
| [producthunt.com/products/maestri](https://www.producthunt.com/products/maestri) | Comentários de launch | ~abr/2026 | A2, C1, C2, C4, E1, F4 |
| [x.com/yrzhe_top/status/2037581353458212914](https://x.com/yrzhe_top/status/2037581353458212914) | Thread de usuário (X) | ~2026-03-27 | A5, F5 |
| [x.com/AI_masaou/status/2043635016295682089](https://x.com/AI_masaou/status/2043635016295682089) | Tweet informativo (JP) | 2026-04-13 | D1, E3 |
| [github.com/zlh-428/open-maestri](https://github.com/zlh-428/open-maestri) | Clone concorrente (README) | criado 2026-05-15 | D1, D4 |
| [github.com/ch923dev/canvas-ade/pull/29](https://github.com/ch923dev/canvas-ade/pull/29) | Teardown competitivo | 2026-06-02 | C3, D1 |
| [github.com/migueldeicaza/SwiftTerm/pull/520](https://github.com/migueldeicaza/SwiftTerm/pull/520) | Fix upstream do dev | 2026-04-02 | A7 |
| [agent-finder.co/reviews/maestri](https://agent-finder.co/reviews/maestri) | Review editorial (peso reduzido) | 2026-05-21 | C3, D2, E1, F1, F3 |
| [note.com/masa_wunder/n0f6c7214a6db](https://note.com/masa_wunder/n/n0f6c7214a6db) | Guia editorial (JP) | 2026-04-13 | D1, D6, E1, F2 |
| [zenn.dev/youjinfox/…/bb3facc650adb1](https://zenn.dev/youjinfox/articles/bb3facc650adb1) | Blog pessoal (JP) | 2026-04-19 | C5, E2, F2, F3 |
| [themaestri.app](https://www.themaestri.app/en) + [docs](https://www.themaestri.app/en/docs/intro) | Vendor | consultado 2026-07-03 | D1, D3, D6, E2, E3 |
| [news.ycombinator.com/item?id=47573259](https://news.ycombinator.com/item?id=47573259) · [id=47729574](https://news.ycombinator.com/item?id=47729574) | Submissões HN (0 comentários) | 2026-03-30 · 2026-04-11 | Sinais de mercado |
| [threads.com/@yrzheee/post/DWZVe6MEaQz](https://www.threads.com/@yrzheee/post/DWZVe6MEaQz) | Post Threads (cortado) | 2026-03-27 | A5 (corroboração) |
| [youtube.com/watch?v=8c7k_BIs_3o](https://www.youtube.com/watch?v=8c7k_BIs_3o) | Vídeo JP (sem comentários legíveis) | ~2026-04-13 | — |
| [discord.com/invite/V9SRtFDcKy](https://discord.com/invite/V9SRtFDcKy) | Discord oficial (inacessível) | — | Limitação declarada |

---

## Anexo C — Softwares similares ao Maestri (panorama competitivo)

Levantado em 2026-07-03 a partir de: [AlternativeTo](https://alternativeto.net/software/maestri/) (alternativas listadas ao Maestri), [agent-finder](https://agent-finder.co/reviews/maestri) (comparativos), lista curada [awesome-agent-orchestrators](https://github.com/andyrewlee/awesome-agent-orchestrators) (100+ ferramentas) e o comparativo [Agentic Coding Mac Apps](https://rywalker.com/research/mac-coding-agent-apps) (atualizado 2026-06-11). O nicho explodiu em 2026 — abaixo só a curadoria dos relevantes, por grau de semelhança com o Maestri.

### C.1 Mesma ideia: canvas/superfície VISUAL para orquestrar agentes (concorrência direta)

| Software | O que é | Plataforma | Licença/preço |
|----------|---------|-----------|----------------|
| **[open-maestri](https://github.com/zlh-428/open-maestri)** | Clone open-source declarado do Maestri (nascido das dores D1/D3/D4) | macOS 14+ | GPL v3 |
| **canvas-ade "Expanse"** ([teardown](https://github.com/ch923dev/canvas-ade/pull/29)) | Canvas de agentes em desenvolvimento; aposta em cross-platform como *moat* | multi (alvo) | em dev |
| **[Nimbalyst](https://rywalker.com/research/mac-coding-agent-apps)** | Sucessor do Crystal; workspace visual (kanban) p/ Codex/Claude Code | cross-platform | core grátis |
| **[AgentsRoom](https://agentsroom.dev/)** | "Terminal & IDE reimaginado": todos os projetos/agentes com status ao vivo numa janela, agentes com papéis (DevOps/Frontend/QA) | desktop | — |
| **[JAT](https://rywalker.com/research/mac-coding-agent-apps)** | IDE visual pra supervisionar 20+ agentes | cross-platform | MIT |
| **vibecraft** ([lista](https://github.com/andyrewlee/awesome-agent-orchestrators)) | Workspace estilo RTS (jogo de estratégia) pra gerenciar agentes — metáfora espacial como a do canvas | — | — |
| **maestro-console** (este projeto) | Canvas GTK4 nativo p/ agentes em Linux/ARM (uConsole) | Linux/ARM | open |

### C.2 Mesma função, outra metáfora: orquestradores desktop de agentes paralelos (worktree/dashboard)

| Software | O que é | Plataforma | Licença/preço |
|----------|---------|-----------|----------------|
| **[Conductor](https://madewithlove.com/blog/conductor-running-multiple-ai-coding-agents-in-parallel/)** (Melty Labs) | O mais citado: Claude Code/Codex em paralelo, 1 worktree por agente, dashboard visual + review diff-first | macOS | grátis (por ora) |
| **cmux** | Terminal nativo Swift p/ sessões paralelas; ganha do Maestri em "execução rápida e focada" (comparativo) | macOS | GPL + comercial |
| **[Emdash](https://alternativeto.net/software/maestri/)** | Dashboard agnóstico de provedor, 20+ agentes | Mac/Win/Linux | open |
| **mux** | "Coding agent multiplexer" — desenvolvimento paralelo isolado | Mac/Linux | — |
| **Sculptor** (Imbue) | Isolamento por container + Pairing Mode | macOS | comercial |
| **Verdent** | Suíte com múltiplos agentes paralelos (planejar/codar/verificar) | Mac/IDEs/Win | comercial |
| **Ami** | App nativo p/ rodar agentes localmente e conversar com o codebase | Win/Mac/Linux | — |
| **Clave** | App macOS nativo p/ sessões Claude Code paralelas | macOS | MIT |
| **Constellagent · Aizen · supacode · parallel-code · Jean · Polyscope · dorothy** | Onda de apps Mac nativos de worktree/sessões paralelas (vários open-source) | macOS | maioria grátis/open |
| **Crystal** | Pioneiro (A/B de agentes em worktrees) — **descontinuado fev/2026**, sucedido pelo Nimbalyst | macOS | deprecated |
| **Maestro (OSS) / RunMaestro** | ⚠️ Produtos DIFERENTES do Maestri apesar do nome — 1-6 sessões paralelas em worktrees / playbooks | multi / macOS | MIT / comercial |

### C.3 Terminal-first (CLI/tmux) — os "anti-canvas"

| Software | O que é | Plataforma |
|----------|---------|-----------|
| **dmux** | Multiplexador CLI/TUI p/ 11+ agentes via tmux + worktrees | Mac/Linux/WSL, open |
| **claude-squad · agent-of-empires · herdr · amux · superset** | Gerenciadores de sessão de agentes no terminal | CLI |
| **[HiveTerm](https://agent-finder.co/reviews/maestri)** | Abordagem declarativa: `hive.yml` define o setup multi-agente reproduzível (vs. composição livre do canvas) | CLI |
| **multi-agent-shogun · tmux-ide** | Orquestração tmux com hierarquia/layouts | CLI |

### C.4 Gigantes adjacentes (IDE/plataforma — a objeção F4 "por que não usar isso?")

| Software | O que é | Preço |
|----------|---------|-------|
| **Warp Oz** | Plataforma cloud-first com integração Slack/Linear | US$18–180/mês |
| **JetBrains Air** | IDE multi-agente com isolamento Docker/worktree | — |
| **Claude for Mac** (Cowork) · **Codex App** | Apps oficiais Anthropic/OpenAI virando "command centers" de agentes | plano pago |
| **Cursor · Cline · Windsurf** | Fluxo agente dentro do IDE (o "melhor pra single-agent" citado nas dores F3/F4) | ~US$20/mês |

### C.5 Leitura estratégica pro maestro-console

1. **O nicho é uma corrida de 2026** — 100+ orquestradores na lista curada, dezenas nativos de Mac; churn alto (Crystal deprecated, OpenSquirrel arquivado 9 dias pós-launch, Orca dormente). Validar antes de copiar qualquer padrão.
2. **O sub-nicho CANVAS é pequeno**: só Maestri, open-maestri, canvas-ade e nichos visuais (Nimbalyst/JAT/AgentsRoom usam kanban/dashboard, não canvas espacial). O maestro-console compete num espaço com pouca gente — e é o único em Linux/ARM/handheld.
3. **Quase tudo é macOS** — a dor D1 (lock-in Mac) se repete no panorama inteiro; cross-platform/Linux continua sendo o diferencial mais defensável.
4. **O padrão dominante da concorrência é git worktree + dashboard** (Conductor, cmux, Emdash, dmux…) — resolve isolamento e paralelismo SEM canvas; é a resposta deles à dor C1–C4 (orquestração PTY não confiável do Maestri). Vale estudar worktrees como mecanismo de isolamento por nó.
5. **Nomes colidem**: "Maestro OSS"/"RunMaestro"/"ai-maestro" NÃO são o Maestri — cuidado ao pesquisar feedback (fontes desta pesquisa filtraram homônimos).

**Status da pesquisa: CONCLUÍDA em 2026-07-03.** Workflow BMad Market Research (passos 1–6) executado de forma adaptada ao escopo "só dores": passo 2 = perfil de quem reclama; passos 3–4 = catálogo de dores; passo 5 = sinais de mercado/comparativos; passo 6 = síntese dores→oportunidades. Escopo confirmado pelo usuário na delegação (2026-07-03).

