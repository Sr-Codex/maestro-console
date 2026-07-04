---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: ['market-dores-usuarios-themaestri-research-2026-07-03.md']
workflowType: 'research'
lastStep: 1
research_type: 'market'
research_topic: 'Dores de usuários dos softwares similares ao Maestri (concorrência do nicho, Anexo C)'
research_goals: 'Repetir a pesquisa de dores (só feedback negativo, fontes vivas, citação+URL+data+autor+confiança) para cada software similar ao Maestri, em relatório único com capítulo por software, para reaproveitar como oportunidades no maestro-console'
user_name: 'Hydekel'
date: '2026-07-03'
web_research_enabled: true
source_verification: true
---

# Research Report: dores da concorrência do nicho (softwares similares ao Maestri)

**Date:** 2026-07-03
**Author:** Hydekel
**Research Type:** market (voz do cliente / dores, escopo avançado: todos os softwares do Anexo C)

**Metodologia:** prompt-template desenhado e criticado adversarialmente pelo Fable (verificação de identidade obrigatória por software contra homônimos; tetos de esforço P/M/G; recorte multi-agente para os gigantes; regras anti-fabricação idênticas à pesquisa do Maestri). Execução em 13 lotes / 3 ondas de agentes paralelos.

---

## Sumário Executivo

**41 capítulos, 29 produtos varridos** (+12 homônimos descartados e registrados). O nicho inteiro — dos clones de 10 stars aos apps oficiais de Anthropic e OpenAI — converge em **13 padrões de dor** (seção transversal no fim). Os três mais universais são exatamente onde o maestro-console já está posicionado: **sessão que não persiste** (nem o Cowork da Anthropic garante — "limitação atual" admitida), **custo de N agentes sem guardrail** (sessão de US$600 no Cursor; quota drenada em 2 min no mux) e **delegação não-verificável** (Maestri ~70%, Windsurf ~40%, Cline desligou os subagents por segurança). A maior demanda reprimida medida da categoria é **Linux** (issue com 194 reações no cmux, o produto mais estrelado da categoria terminal). Achados de segurança graves em 3 produtos: `--dangerously-skip-permissions` hardcoded (superset, dmux) e vazamento entre sessões no Warp Oz (confused deputy). ~1/3 dos produtos está morto, estagnado ou esfriando — churn brutal. **Nenhum concorrente combina canvas espacial + Linux + open source + custo transparente + delegação verificável.**

## Índice

- **Parte 1 — Canvas/superfície visual (concorrência direta):** 1. open-maestri · 2. canvas-ade "Expanse" · 3. AgentsRoom · 4. vibecraft
- **Parte 2 — Orquestradores desktop:** 5. Conductor · 6. cmux · 7. Emdash · 8. mux (Coder) · 9. Sculptor · 10. Verdent · 11. Maestro OSS · 12. RunMaestro · 13. ai-maestro · 14. Nimbalyst · 15. Crystal (autópsia) · 16. JAT · 17. parallel-code · 18. Jean · 19. Polyscope · 20. Dorothy · 21. Ami · 22. Clave · 23. Constellagent · 24. Aizen · 25. supacode
- **Parte 3 — Terminal-first (CLI/tmux):** 26. herdr · 27. amux · 28. superset · 29. tmux-ide · 30. HiveTerm · 31. multi-agent-shogun · 32. dmux · 33. claude-squad · 34. agent-of-empires
- **Parte 4 — Gigantes adjacentes (recorte multi-agente):** 35. Claude for Mac/Cowork · 36. Codex App · 37. Cursor · 38. Windsurf · 39. Cline · 40. Warp Oz · 41. JetBrains Air
- **Dores recorrentes do nicho (transversal)** — os 13 padrões P1-P13 + leitura executiva
- **Metodologia e Limitações (consolidado)**

---

# Parte 1 — Canvas/superfície visual (concorrência direta)

> **Tese confirmada pela varredura:** o sub-nicho canvas é praticamente deserto — dos 4 concorrentes diretos, nenhum tem base de usuários mensurável. O único com feedback público é o AgentsRoom (1 review, negativa). Ausência de feedback ≠ produto bom: reflete zero adoção.

### 1. open-maestri

**Identidade:** clone GPL v3 declarado do Maestri (Swift, macOS 14+; CLI `omaestri` compatível) · grátis · status: raso — criado 2026-05-15, último push 2026-06-01 (~1 mês parado), 10 stars · varrido em 2026-07-03.

**SEM FEEDBACK ENCONTRADO** — 0 issues (abertas ou fechadas), 0 discussions, 0 hits no HN/Reddit; ausente até das listas de "Maestri alternatives" (AlternativeTo lista Emdash/mux/dmux/Ami/maki — não o clone). Queries: `gh issue list -R zlh-428/open-maestri --state all`, hn.algolia "open-maestri", WebSearch.

**Sinal de mercado:** base de usuários ~zero. E o diferencial é só licença/preço — mantém o mesmo lock-in macOS do original.

**Lição pro maestro-console:** clonar com diferencial só de licença não gera adoção; o diferencial de PLATAFORMA (Linux/ARM) é o que nenhum clone do Maestri cobre.

### 2. canvas-ade ("Expanse")

**Identidade:** canvas de agentes Electron/TypeScript · **pré-lançamento** — sem licença publicada, sem release, sem site, 0 stars; dev diário ativo (push 2026-07-03), roadmap na "Phase 5 = packaging" · varrido em 2026-07-03.

**SEM FEEDBACK ENCONTRADO** — as 2 únicas issues são do próprio mantenedor (tracker interno, 0 comentários de terceiros — não contam pela regra). Zero usuários externos identificáveis.

**Sinal de mercado:** impossível haver dor de usuário sem distribuição. Riscos observados: sem licença no repo (atrito de adoção) e nome que colide com "ADE" — termo que virou genérico da categoria (Letta ADE, ade-app.dev, Orca…) → discoverability quase nula ao lançar.

### 3. AgentsRoom

**Identidade:** app desktop nativo (macOS/Linux/Windows) multi-agente com papéis (DevOps/Frontend/QA) + companion iOS · closed-source, freemium (grátis até 3 projetos; Pro US$9,99/mês, BYOK) · status: GA v1.100.1, ritmo de release altíssimo (solo dev/time mínimo) · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **App mobile despareava sozinho — inutilizável fora de casa** (dev admitiu: bug de "security improvement", corrigido na v1.23.0) | "every time I open the app it's unpaired, which of course is impossible to repair without being home" ("toda vez que abro está despareado — impossível reparear sem estar em casa") | [App Store](https://apps.apple.com/us/app/agentsroom-ai-remote-dev-agent/id6761265182) · 2026-04-08 · alixorus (usuário, 3★) | Alta |
| 2 | **UX de texto do mobile "um desastre"** — respostas ilegíveis/não-parseadas, impossível responder perguntas do agente ou adicionar agentes pelo mobile | "text display and entry a disaster… unreadable and unparsed responses… inability to respond to user input questions" | mesma review · paráfrase de snippet (2 leituras) | Média |
| 3 | **Nota 3.0/5 na App Store US — com 1 única avaliação** (a negativa acima é 100% do feedback público) | página lida | App Store · 2026-07-03 | Alta |

**Sinal de mercado:** zero presença em HN/Reddit/Product Hunt/AlternativeTo apesar de GA com plano pago — tração pública ~nula; changelog admite histórico de bugs de estabilidade.

**Lição pro maestro-console:** controle remoto/mobile de agentes é diferenciador atraente, mas pareamento frágil transforma a feature num passivo — se um dia fizer companion remoto, resiliência de re-pareamento é requisito nº 1.

### 4. vibecraft (vibecraft.build)

**Identidade:** "RTS interface" 3D nativa macOS p/ múltiplos Claude Code/Codex · trial 7 dias → **US$20/mês ou US$200/ano** · só Apple Silicon; 2 agentes suportados; download atrás de invite code (snippet) · status: incerto (repo público sem atividade desde 2026-04-22) · varrido em 2026-07-03. NÃO confundir: Nearcyan/vibecraft é OUTRO produto homônimo do mesmo nicho; Minecraft/Vivecraft descartados.

**SEM FEEDBACK DE USUÁRIO ENCONTRADO** — launch no HN (2025-10-14) fechou com 2 pontos e 1 comentário (do próprio autor); Reddit 0 resultados; nenhuma review em lugar nenhum.

**Sinal de mercado:** US$20/mês sem nenhuma prova social; nome é desastre de SEO (5+ produtos "VibeCraft/Vivecraft" ativos dominam a busca). A metáfora RTS (a mais próxima do canvas espacial do Maestri fora os clones) não validou.

**Lição pro maestro-console:** metáfora espacial sozinha não vende — o Maestri validou canvas+PTY com execução impecável de marketing/nativo, não pela metáfora; e preço premium sem prova social afasta até curiosos.

# Parte 2 — Orquestradores desktop de agentes paralelos

### 5. Conductor (Melty Labs)

**Identidade:** orquestrador de Claude Code/Codex/Cursor em git worktrees paralelos com dashboard visual · macOS Apple Silicon apenas · proprietário, grátis (Enterprise/Cloud em beta) · status: ATIVO, o mais bem financiado do nicho (Series A US$22M em 2026-03-31; v0.72.0, releases quase semanais) · varrido em 2026-07-03

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **OAuth GitHub pede "as chaves do reino"** — read-write total em TODOS os repos, settings e deploy keys | "Full read-write access required to all your Github account's repos. Not just code. Settings, deploy keys." ("acesso total de leitura-escrita a todos os repos… não só código") | [HN Show HN](https://news.ycombinator.com/item?id=44594584) · 2025-07-20 · @itsalotoffun (usuário) | Alta |
| 2 | **Desconfiança por closed source** — sem como auditar o que vai pros servidores; onde ficam os tokens OAuth? | "no way to find out if there's any data sent to your servers"; "I don't want to… get heavily reliant on closed source" | HN · 2025-07-19 a 2026-02-08 · @janpieterz, @joshualyon, @throwaw12, @kernelbugs (usuários) | Alta |
| 3 | **Mac-only + Apple Silicon-only** — exclui Windows, Linux e Mac Intel; ainda dói em 2026 | "conductor.build is Mac only .." | HN · 2025-07-17 a 2026-06-29 · @WalterSear, @countfeng, @Quarrel (usuários) + editorial | Alta |
| 4 | **Só repos clonados do GitHub** — sem git local, GitLab, Bitbucket, self-hosted; GitHub Enterprise falha | "I can't connect this to my work GitHub enterprise repos"; "If Conductor would work with local branches I would switch from Crystal" | HN · 2025-07-20/22 · @BewareTheYiga, @lachances, @cahaya (usuários) | Alta |
| 5 | **Bootstrap manual de cada worktree** — .env/node_modules não vêm; todo workspace novo exige setup | "Git worktrees don't include untracked files like your .env or node_modules, so every new workspace needs to be bootstrapped" | HN 2025-07-20 @pjm331 + [madewithlove](https://madewithlove.com/blog/conductor-running-multiple-ai-coding-agents-in-parallel/) 2026-03-24 (editorial hands-on) | Alta |
| 6 | **Custo de tokens multiplicado** — 4 agentes = 4x consumo, fácil de abrir workspace sem pensar | "Running four agents simultaneously means four times the token consumption" | madewithlove · 2026-03-24 · editorial | Média |
| 7 | **Humano vira gargalo de review** — 4x mais coisas pra revisar, 4x mais bugs pra pegar | "You're still the quality gate. Now you're just reviewing more things" | madewithlove · 2026-03-24 · editorial | Média |
| 8 | **Sem memória entre sessões/workspaces** — agente não lembra convenções nem decisões passadas | "Context doesn't persist between sessions… no memory of previous work" | madewithlove · 2026-03-24 · editorial | Média |
| 9 | **"Sandbox de mentira"** — agente ALEGA restrição de sandbox mas escreve fora quando instruído; wrapper quebra as proteções reais | "Tell HN: AI lies about having sandbox guardrails" (confirmado por terceiro na thread) | [HN](https://news.ycombinator.com/item?id=47256614) · 2026-03-05 · @benjosaur (usuário) | Alta |
| 10 | **Perde o "feel" do Claude Code nativo** | "There's a 'feel' to the way Claude Code outputs the text… this is lost with conductor" | HN · 2025-07-21 · @aantix (usuário) | Alta |
| 11 | **Worktrees = camada desnecessária pra alguns; branch só pode estar em 1 worktree** (admitido) | "adds an unnecessary layer on top" + docs de troubleshooting | HN 2025-07-22 @redhale + vendor | Alta |
| 12 | **Incompatível com VMs — sem intenção de suportar** | "their docs say they have no intention of implementing vm's" | HN · 2026-01-24 · @MarcelOlsz (usuário) | Alta |
| 13 | **Bugs admitidos pelo vendor**: undo quebrado no composer, output do terminal corrompe ao trocar janela, agentes empacotados falham com shell customizado, workspace movido some | [docs/troubleshooting](https://conductor.build/docs) (lida 2026-07-03) + changelog (startup lento, uso excessivo em background, freeze Chromium) | vendor | Alta |
| 14 | **Risco de plataforma** — Anthropic quase restringiu uso de assinatura Claude em ferramentas terceiras (2026-05-13; adiado indefinidamente em 2026-06-15) | conductor.build/blog/claude-subscription-update | vendor | Alta (fato) |
| 15 | **Concorrente open-source cobre o gap** | "Crystal can do all of this and more, and unlike Conductor is open source" | HN · 2025-07-20 · @jbentley1 (usuário, possível viés) | Média |

**Sinal de mercado:** tração forte e saúde excelente (Show HN 228 pts/115 comentários, US$22M, releases semanais). O negativo concentra-se em lock-in estrutural (Mac/GitHub/closed) e nos custos inerentes ao paralelismo — não em falta de qualidade. Canais vazios: AlternativeTo (0 reviews), Reddit (nada indexado/bloqueado), X (só a conta oficial).

**Lição pro maestro-console:** os flancos do líder do nicho são exatamente Linux/git-local/open-source; e as dores de paralelismo (tokens 4x, review 4x, sandbox falso, sem memória entre sessões) são dores DE NICHO que o maestro-console também vai enfrentar — medidor de custo/budget cap já responde a primeira; autoridade host-side (ADR-21/22) responde a do sandbox.

### 6. cmux (Manaflow)

**Identidade:** terminal nativo Swift (base Ghostty/libghostty) p/ sessões paralelas de agentes · macOS Apple Silicon apenas · GPL-3.0 + licença comercial · status: MUITO ativo (~23.5k stars, push 2026-07-03; 1.307 issues abertas) · varrido em 2026-07-03. Homônimos descartados: soheilhy/cmux (Go), craigsc/cmux, kakao/cmux.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Vazamento de memória severo → OOM / máquina "tijolada"** — dezenas de GB, sistema congela | "cmux reaches 70+ GB memory, bricks macOS (16 GB machine)"; "RSS grows from 400MB to 8GB within minutes" | [#4529](https://github.com/manaflow-ai/cmux/issues/4529) (25 comentários, 22 reações) + [#4520](https://github.com/manaflow-ai/cmux/issues/4520) + [#2871](https://github.com/manaflow-ai/cmux/issues/2871) · abr-mai/2026 · usuários | Alta |
| 2 | **"Nativo" que não performa como o Ghostty puro** — lag de digitação, 3-6% CPU por processo ocioso (~35% total), main thread a 100%, Settings demora segundos | "ghostty + ssh + tmux has essentially no typing lag, but cmux + ssh + tmux has serious lag"; "It improved when I stopped using cmux" | [#4681](https://github.com/manaflow-ai/cmux/issues/4681) (10 reações) + [#2408](https://github.com/manaflow-ai/cmux/issues/2408) (13) + [#2586](https://github.com/manaflow-ai/cmux/issues/2586) + [#4101](https://github.com/manaflow-ai/cmux/issues/4101) · mar-mai/2026 · contributor c/ eco de terceiros | Alta |
| 3 | **Só macOS Apple Silicon** — a issue mais quente do repo é "Linux support?" (**194 reações**, aberta desde fev); Windows 46 reações; Intel 12. Ports não-oficiais surgiram (wmux, cmux-windows, PrettyMux) | "I would like to be able to use this on a Linux desktop... Ghostty is also Linux native :)" | [#330](https://github.com/manaflow-ai/cmux/issues/330) + [#1012](https://github.com/manaflow-ai/cmux/issues/1012) + [#293](https://github.com/manaflow-ai/cmux/issues/293) · fev-mar/2026 · usuários | Alta |
| 4 | **Quebra de confiança: update forçou "bypass permissions" do Claude silenciosamente**, ignorando `--permission-mode`, sem changelog | "It feels like the latest update was compromised, and I don't feel safe executing Claude code in this terminal" | [#3547](https://github.com/manaflow-ai/cmux/issues/3547) (27 reações, 20 comentários) · 2026-05-05 · usuários | Alta |
| 5 | **Sessões vivas não persistem entre restarts** — restaura layout, mas não o processo (Claude/tmux/vim) | Vendor admite: "It does NOT restore live process state inside terminal apps yet" | [#2823](https://github.com/manaflow-ai/cmux/issues/2823) + [docs troubleshooting](https://manaflow-ai-cmux.mintlify.app/resources/troubleshooting) · abr/2026 · usuário + vendor | Alta |
| 6 | **Regressões frequentes** — drag-and-drop de imagem quebrou (4 issues em mai/2026), workspace novo crashava; "buggy mess" no HN | "Looks like this could be really cool, but it's a buggy mess… Once I lose focus in a tab, I can't ever type again" | [#3435](https://github.com/manaflow-ai/cmux/issues/3435) etc. + [HN](https://news.ycombinator.com/item?id=47082157) · fev-mai/2026 · usuários | Alta |
| 7 | **Atalhos quebram teclados não-US** — option+q capturado impede digitar @ | "this is a blocker for anyone using a non-us keyboard layout" | [#1653](https://github.com/manaflow-ai/cmux/issues/1653) + #135 · fev-mar/2026 · usuários | Média-alta |
| 8 | **Polling em background estoura rate limit do GitHub** (5000/5000), mesmo com o recurso desligado | "cmux is exhausting the GitHub GraphQL API rate limit… even when sidebar.showPullRequests is set to false" | [#2746](https://github.com/manaflow-ai/cmux/issues/2746) · 2026-04-09 · usuário | Média |

**Sinal de mercado:** projeto quente com backlog de qualidade — a promessa "nativo = leve" contradita pelos usuários (RAM/CPU/lag), confiança arranhada pelo episódio bypass-permissions, e a dor nº 1 é plataforma (Linux/Windows/Intel descobertos).

**Lição pro maestro-console:** (1) a maior demanda reprimida do concorrente mais estrelado do nicho é LINUX — exatamente onde o maestro-console vive; (2) persistência de sessão viva pós-restart é lacuna admitida — o unload/kill-and-resume com captura de sessão ataca isso; (3) nunca mexer em permissões de agente silenciosamente (autoridade host-side + changelog).

### 7. Emdash (generalaction, YC W26)

**Identidade:** dashboard desktop Electron cross-platform (Mac/Win/Linux) p/ agentes CLI em worktrees git · Apache-2.0, grátis · status: ativo (~5.1k stars, push 2026-07-03; triagem rápida: 58 abertas de 637) · varrido em 2026-07-03. Homônimos descartados: emdash-cms (Cloudflare), dmotz/emdash, caractere "—".

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Releases quebradas / crash na instalação (Win e Linux)** — JS error na abertura; .deb com NODE_MODULE_VERSION errado; "Claude Code is not installed" (estava); segfaults | "On launching Emdash Beta (v1.0.5) the app immediately throws a JavaScript error… and becomes unusable"; ".deb package is broken" | [#1738](https://github.com/generalaction/emdash/issues/1738) (mais comentada) + [HN](https://news.ycombinator.com/item?id=47143382) + [HN](https://news.ycombinator.com/item?id=47144145) · fev-mai/2026 · usuários | Alta |
| 2 | **Terminal embutido com defeitos básicos de TTY** — Ctrl+V não cola (Win), sem quebra de linha no Claude, menu embaralhado "como máquina de escrever no mesmo papel", input vazando entre workspaces | "Claude CLI multi-selection menu garbled… Once a session is in a bad state, I need to restart [Emdash]" | [#1901](https://github.com/generalaction/emdash/issues/1901) + #636 + [#2538](https://github.com/generalaction/emdash/issues/2538) + #2401 + #156 + #597 · out/2025-jun/2026 · usuários | Alta |
| 3 | **Arquitetura "só embute terminal" fecha portas** — sem SDK/JSON = mobile/headless inviável (crítica estrutural de usuário técnico) | "you don't use any agent SDK or --json outputs. You just embed a terminal window. That makes mobile interfaces a non-starter" | [HN](https://news.ycombinator.com/item?id=47148054) · 2026-02-25 · @kzahel | Alta |
| 4 | **Performance Electron degrada com escala** — 78 tarefas = UI no chão; fork "Emdash2 but faster" (Tauri/Rust) nasceu disso; teto de paralelismo é dúvida aberta sem resposta | "I've loaded 78 tasks and the UI is crawling to a halt" | [HN](https://news.ycombinator.com/item?id=47151688) + [fork Emdash2](https://github.com/mweinbach/Emdash2) · fev/2026 · usuários | Média-alta |
| 5 | **Fricções do modelo worktree** — exige remote `origin` até em projeto local (bloqueia uso puramente local); vendor admite catálogo de falhas (worktree "already exists", .env não copiado, sqlite corrompido, PTY morre, zumbis) | "Emdash incorrectly requires a Git remote (origin)… blocks core functionality for purely local development" | [#451](https://github.com/generalaction/emdash/issues/451) + [docs troubleshooting](https://generalaction-emdash-14.mintlify.app/guides/troubleshooting) · dez/2025 · usuário + vendor | Alta |
| 6 | **SSH/remoto imaturo** — shell não abre, ignora SSH_AUTH_SOCK (1Password), path remoto global | "remote ssh, not starting shell after connection... stall in empty screen" | [#835](https://github.com/generalaction/emdash/issues/835) + #1235 + #2731 · fev-jun/2026 · usuários | Média-alta |
| 7 | **Escreve configs de hook nos projetos do usuário sem opt-out** (.claude/settings.local.json, .codex/config.toml) | "writes notification hook configs into the project/worktree cwd" — pede opção de desligar | [#1944](https://github.com/generalaction/emdash/issues/1944) · 2026-05-09 · contributor | Média |
| 8 | **Ceticismo "camada descartável"** — por que investir numa ADE se o próprio CLI evolui?; modelo de negócio admitidamente indefinido; coordenação/merge entre agentes fica no colo do usuário | "Why should we invest long time into your 'ADE', really?… Maybe you're betting on being purchased?" | [HN](https://news.ycombinator.com/item?id=47143449) · fev/2026 · usuários + vendor | Média |

**Sinal de mercado:** o custo do cross-platform via Electron+node-pty é um catálogo de modos de falha (o troubleshooting oficial é extenso); perguntas estratégicas (merge entre agentes, teto de paralelismo) seguem sem resposta. Ponto forte: triagem de issues rápida.

**Lição pro maestro-console:** (1) cross-platform "de verdade" exige QA de runtime por SO — teste de runtime é o diferencial, não o port; (2) a crítica "só embute terminal, sem camada estruturada" valida a arquitetura de envelope/ledger do maestro-console; (3) não exigir remote/GitHub: fluxo git puramente local é dor recorrente do nicho (também no Conductor).

### 8. mux (Coder)

**Identidade:** "Coding Agent Multiplexer" — desktop + browser, workspaces isolados (worktree/SSH/Docker), da Coder · macOS/Linux (Windows em issue) · AGPL-3.0, grátis · status: ativo (1.888 stars, push 2026-07-03), vendor admite "Preview state — you will encounter bugs" · varrido em 2026-07-03. Homônimos descartados: mux.com (vídeo), gorilla/mux, tmux, e o Show HN "Cmux" (produto do lote 2).

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Estouro de billing — Copilot Pro drenado em ~2 minutos** numa única sessão | "it blew through my entire premium requests budget within a single session in ~2 minutes, then stopped due to lack of credits" | [#2489](https://github.com/coder/mux/issues/2489) · 2026-02-18 · @staticfloat (usuário) | Alta |
| 2 | **Trabalho do sub-agente se perde** — commit reportado como sucesso, patch gerado, mas a mudança não chega ao workspace pai | "An exec sub-agent reports a successful commit… but the change does not appear in the parent workspace" | [#2112](https://github.com/coder/mux/issues/2112) · 2026-02-02 · usuário | Alta |
| 3 | **Ambiente do agente ≠ ambiente do dev** — PATH sem as pastas do usuário no macOS; fish/direnv/nix ignorados; nenhuma CLI funciona | "the PATH seen by the model is missing all user folders and nothing works" | [#797](https://github.com/coder/mux/issues/797) · 2025-11-29 · usuário | Alta |
| 4 | **Fluxo git confuso** — com Docker, mudanças commitadas no workspace não aparecem na pasta original, "sem forma aparente" de levá-las | "even if the changes are committed in the workspace they're not visible in the original project folder" | [#1713](https://github.com/coder/mux/issues/1713) · 2026-01-16 · usuário | Alta |
| 5 | **Sem controle de tier/custo** (OpenAI Service Tier) + no lançamento só API key (sem plano Claude Max) | "Please add option to turn off OpenAI Service Tier!" | [#3196](https://github.com/coder/mux/issues/3196) + [#306](https://github.com/coder/mux/issues/306) · usuários | Média |
| 6 | **Distribuição falha** — release 0.19.0 sumiu do npm | título da issue | [#2765](https://github.com/coder/mux/issues/2765) · 2026-03-03 · usuário | Média |
| 7 | **Sem modelos locais/OpenAI-compatíveis** (llama.cpp) — issue externa mais comentada | pedido aberto | [#1435](https://github.com/coder/mux/issues/1435) · 2026-01-03 · usuário | Média |

**Sinal de mercado:** launch HN 100 pts/49 comentários; temas dominantes das issues = custo imprevisível, sincronizar trabalho do agente de volta, replicar o ambiente real dentro do isolamento. Na thread de launch, a dor era do NICHO: "If two agents try to run tests at the same time… I need to manually do air traffic control". Reddit: nada.

**Lição pro maestro-console:** isolamento que diverge do ambiente real do dev gera a pior classe de bug ("nada funciona"); e trabalho de agente que "se perde" no caminho de volta é quebra de confiança fatal — o ledger/captura de sessão do maestro-console precisa garantir o caminho de volta verificável.

### 9. Sculptor (Imbue)

**Identidade:** agentes Claude Code/Codex em paralelo, cada um em container Docker; "Pairing Mode" sincroniza com o IDE local · macOS Apple Silicon + Linux (Intel/Windows "a caminho") · MIT (hoje), grátis no beta, exige acesso Anthropic · status: ativo (194 stars, push 2026-07-03) · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Marketing dizia "open source" com LICENSE proprietária** — mantenedor admitiu "linguagem desonesta" (depois corrigiu pra MIT) | "not sure if this is an oversight or just some fundamental misunderstanding of what OSS actually means" → maker: "will remove the disingenuous language" | [#12](https://github.com/imbue-ai/sculptor/issues/12) · 2026-05-13 · usuários + mantenedor | Alta |
| 2 | **Updater/instalação do Claude congela** — 15+ min a 25%, restart não resolvia | "the Claude installation step is taking a very long time (15 minutes so far, 25% progress)" | [#14](https://github.com/imbue-ai/sculptor/issues/14) · 2026-05-23 · usuário (corrigido na 0.35) | Alta |
| 3 | **Terminal morre após sleep do macOS** — usuário mandou o próprio diff do fix | "after a system sleep terminals open in Sculptor become unresponsive" | [#182](https://github.com/imbue-ai/sculptor/issues/182) · 2026-06-25 · usuário | Alta |
| 4 | **Pós-beta opaco** — "e quando o grátis acabar?"; "não é grátis: você paga com seu e-mail" | "Ok, and then what? Honest question."; "You pay for it by supplying your email address." | [HN launch](https://news.ycombinator.com/item?id=45427697) (176 pts/85 comentários) · 2025-09-30 · usuários | Alta |
| 5 | **Sem base URL configurável da Anthropic** — bloqueia proxies/gateways corporativos; lock-in de fato no ecossistema Claude | "Lacks an option to configure anthropic base url" | HN launch · 2025-09-30 · usuário | Média |
| 6 | **Plataformas faltando** (Intel, Windows) + features centrais "coming soon" admitidas (fork de agente, MCP custom, Dockerfile custom, GPT) | página oficial | vendor · lida 2026-07-03 | Alta |

**Sinal de mercado:** tração real no HN; objeções dominantes = confiança/monetização e abertura, não a proposta. Só 3 issues públicas (feedback vai por Discord/e-mail — invisível). Reddit: nada.

**Lição pro maestro-console:** transparência de licença importa (o episódio "open source de mentira" custou confiança); e beta grátis sem plano claro de pós-beta gera desconfiança — o maestro-console open-source de verdade não tem esse flanco.

### 10. Verdent / Verdent Deck

**Identidade:** extensão IDE + app desktop Mac multi-agente (planejar/codar/verificar), da Verdent AI (Singapura, fundador ex-TikTok) · comercial fechado, créditos mensais (Starter US$19/480 créditos → Max US$179) · status: ativo · varrido em 2026-07-03.

| # | Dor | Evidência | Fonte · data · autor | Confiança |
|---|-----|-----------|---------------------|-----------|
| 1 | **Trustpilot devastador: nota 2.3, 100% das 7 reviews com 1 estrela** — alegação de golpe (cliente gastou >€3.000, empresa trocou conta de pagamento e parou de responder), cartão obrigatório no trial com cobrança automática sem aviso claro, suporte que ignora | reviews relatam "scam", "$20 → ~10-12 requests com Opus", créditos mensais que "somem rápido demais" | [Trustpilot](https://www.trustpilot.com/review/verdent.ai) · 2025-2026 · usuários | Média-alta (fetch 403; corroborado por 2 resumos de busca convergentes) |
| 2 | **Sem reembolso, admitido nos Terms** | "final and non-refundable, unless otherwise agreed" | [verdent.ai/terms](https://www.verdent.ai/terms) · vendor | Média |
| 3 | **Lento em repos grandes; confirmação demais; JetBrains atrás do VS Code** | "it asks for confirmation a lot. Safer, but slows flow" | [Skywork review](https://skywork.ai/blog/vibecoding/verdent-ai-review-2025/) · editorial/SEO (rebaixado) | Média |
| 4 | **Onboarding/definição de produto confusos** — review convidada pela própria empresa | "I couldn't for the life of me figure out what this thing was supposed to do beyond the answer I was given: it's an agent" | [dev.to](https://dev.to/anchildress1/codeck-presents-verdent-ai-they-wanted-opinions-i-have-plenty-5ccl) · 2025-09-24 · @anchildress1 | Alta |

**Sinal de mercado:** contraste gritante entre Product Hunt 5,0/5 e Trustpilot 100% 1-estrela — padrão launch-hype vs atrito real de cobrança. A dor validada nº 1 é **billing/créditos**, não tecnologia. Reddit: nada específico.

**Lição pro maestro-console:** modelo de créditos opacos + trial com cartão é o anti-padrão de confiança do nicho; transparência de custo (medidor por nó + budget cap) é diferencial defensável.

### 11. Maestro (OSS) — "its Maestro Baby"

**Identidade:** "Bloomberg Terminal for CLI Agents" — 1-6 sessões Claude Code/Gemini/Codex em worktrees · Tauri/Rust, Mac/Win/Linux · MIT, grátis · status: ⚠️ **possivelmente abandonado** — 1.158 stars, criado 2026-01-07, **último push 2026-04-19 (~2,5 meses parado)**, issues centrais abertas sem resposta · varrido em 2026-07-03. NÃO confundir com mobile-dev-inc/maestro (teste mobile) nem camoneart/maestro (CLI).

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Windows quebrado no lançamento** — terminais spawnando em loop infinito; janela trava sem resposta | "multiple terminals spawn up and keep spawning up" | [#76](https://github.com/its-maestro-baby/maestro/issues/76) (11 comentários) + #104 + #93 · fev/2026 · usuários | Alta |
| 2 | **Requisito de macOS subiu pra 15** — não roda em Sonoma/Sequoia; o "fix" foi exigir OS mais novo | issues #25 + #34 → PR #35 | jan/2026 · usuários | Alta |
| 3 | **Status do agente não confiável — a proposta central falha** — "working" quando o agente tem pergunta; agentes "idle" trabalhando pesado (ABERTA, sem fix) | "it never was able to catch 'Needs input'… status is still never updated"; "All my claude agents are showing up as 'idle' despite them actually working hard" | [#204](https://github.com/its-maestro-baby/maestro/issues/204) + [#176](https://github.com/its-maestro-baby/maestro/issues/176) · fev/2026 · usuários | Alta |
| 4 | **Copiar/colar e seleção quebrados** (chat + terminal); first responder agressivo quebrava até hotkey de outros apps | "Cmd+V does nothing… Unable to select/copy text from the terminal output area" | [#33](https://github.com/its-maestro-baby/maestro/issues/33) + #53 + #52 · jan/2026 · usuários | Alta |
| 5 | **Sem modo headless/servidor** — GUI exige webkit2gtk+DISPLAY no Linux; SSH/VS Code Server fica de fora (ABERTA) | pedido sem resposta | [#77](https://github.com/its-maestro-baby/maestro/issues/77) · 2026-02-02 · usuário | Alta |
| 6 | **Render do terminal ruim + race de MCP entre sessões + deadlock com output grande** | "MCP Status Pollution: Race condition when multiple sessions share .mcp.json"; PR "Fix pipe buffer deadlock" | #94 + #98 + [#80](https://github.com/its-maestro-baby/maestro/issues/80) + PR #36 · jan-fev/2026 | Alta |

**Sinal de mercado:** hype de launch (1,1k stars em semanas) → rajada de bugs básicos em todas as plataformas → estagnação total desde abril. O fundador do RunMaestro abriu issue "We should collaborate!" — consolidação do nicho em curso; usuários tendem a migrar pro player ativo.

**Lição pro maestro-console:** (1) monitor de status de agente TEM que ser confiável — é a promessa central desse tipo de app e foi onde este morreu; (2) cadência sustentável > hype: nicho pune abandono em semanas.

### 12. RunMaestro

**Identidade:** "Agent Orchestration Command Center" — Claude Code/Codex/OpenCode/Droid/Copilot, Auto Run Playbooks · cross-platform (premissa "comercial macOS-only" estava DESATUALIZADA: é **AGPL-3.0, grátis**, site runmaestro.ai) · status: MUITO ativo (3.084 stars em ~7 meses, push 2026-07-03, mantenedor hiperativo) · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Auto Run trava silenciosamente** — playbooks rodando horas sem indicação, porcentagem parada | "Some of the playbooks would run for hours with no indication, the percentage never seemed to change" | [#338](https://github.com/RunMaestro/Maestro/issues/338) · 2026-02-11 · mantenedor consolidando reports de usuários | Alta |
| 2 | **Exaustão de tokens em run de 24h = parada silenciosa de ~4h** — sem notificação, sem pausa graciosa, sem retomada; descoberto olhando o git log | "no notification, no graceful pause, and no way to resume cleanly… Manual discovery required (noticed gap in git log)" | [#235](https://github.com/RunMaestro/Maestro/issues/235) · 2026-01-24 · @mellanon (experience report) | Alta |
| 3 | **Auto Run atropela revisão humana** — specs criadas → implementação imediata, sem chance de "espera, não é isso" (sem HITL gates) | "The agents completed full cycles without human input… No opportunity for 'wait, that's not quite right'" | [#232](https://github.com/RunMaestro/Maestro/issues/232) · 2026-01-24 · @mellanon | Alta |
| 4 | **Commita sem aprovação** mesmo com instrução explícita de não commitar antes do teste | "even when i… explicit said to no commit before i can test, after every task Maestro commit" | [#76](https://github.com/RunMaestro/Maestro/issues/76) · 2025-12-23 · usuário | Alta |
| 5 | **Windows de segunda classe** — Claude não detectado, shells não spawnam, pty.node ARM em release não-ARM | 3 issues de usuários distintos | [#60](https://github.com/RunMaestro/Maestro/issues/60) (15 comentários) + #150 + #116 · dez/2025-jan/2026 | Alta |
| 6 | **Remoto/SSH frágil** — agentes não encontrados no remote (issue mais comentada, 20), detecção ignora config SSH, lentidão, exit 127 | 4 issues de usuários distintos | [#181](https://github.com/RunMaestro/Maestro/issues/181) + #176 + #554 + #1016 · jan-mai/2026 | Alta |
| 7 | **"Compact & Continue" não funcionava**; histórico não reabre sessões (aba vazia/erro de leitura); upgrade brickou o app ("Indexing the score…" eterno); prompt grande crasha com erro logado como Info | "clicking it doesn't do anything"; "I tried restarting but it doesn't help" | [#172](https://github.com/RunMaestro/Maestro/issues/172) + [#251](https://github.com/RunMaestro/Maestro/issues/251) + [#587](https://github.com/RunMaestro/Maestro/issues/587) + [#296](https://github.com/RunMaestro/Maestro/issues/296) · dez/2025-mar/2026 · usuários | Alta |
| 8 | **Limitações admitidas** — loop de Auto Run "does not survive a restart"; halt marker velho bloqueia re-runs; trocar de documento descarta edições; progresso goal-driven é auto-avaliação do agente (não medido) | [docs](https://docs.runmaestro.ai) lidas 2026-07-03 | vendor | Alta |

**Sinal de mercado:** crescimento rápido GitHub-first (HN irrelevante: 7 pts), mantenedor que fecha issue rápido e usuários engajados escrevendo "experience reports". Clusters de dor: (a) observabilidade/robustez de runs autônomos longos, (b) SSH/remoto, (c) Windows. Nota: maioria das issues citadas já fechada — retrato de dez/2025-mar/2026.

**Lição pro maestro-console:** runs autônomos longos exigem: notificação de parada, pausa graciosa ao esgotar orçamento (o budget cap do maestro-console já bloqueia com envelope — falta UX de retomada), gates de revisão humana opcionais e NUNCA commitar sem aprovação; orquestração deveria sobreviver a restart (casa com o kill-and-resume atual).

### 13. ai-maestro (23blocks)

**Identidade:** dashboard web self-hosted (Next.js + node-pty + xterm.js) p/ Claude/Codex/Gemini com "skills" e mensagens agente-a-agente · MIT, grátis · status: ativo mas nicho (721 stars, push 2026-06-13; issues concentradas em 2 power users) · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Vazamento de PTYs derruba o terminal do macOS inteiro** — ~500 handles de /dev/ptmx presos; iTerm2 sem conseguir abrir abas; persistiu entre versões | "version 0.17.18 still leaks PTYs… a single node process was holding ~500 /dev/ptmx handles open" | [#47](https://github.com/23blocks-OS/ai-maestro/issues/47) · 2026-01-11 · @Emasoft | Alta |
| 2 | **Picos de memória → dashboard inutilizável** — reiniciado até 35 vezes a cada 2 minutos | "becomes unusable because it disconnects continuously (restarted up to 35 times every 2 minutes!)" | [#74](https://github.com/23blocks-OS/ai-maestro/issues/74) · 2026-01-22 · @Emasoft | Alta |
| 3 | **Mensageria entre agentes SEM isolamento por projeto** — broadcast contaminou agentes de OUTROS projetos, que interpretaram como se fosse deles ("efeitos desastrosos"); ABERTA | "I'm troubled by the complete lack of restrictions on the message exchange… agents working on different project received the messages" | [#241](https://github.com/23blocks-OS/ai-maestro/issues/241) (10 comentários) · 2026-02-20 · @Emasoft | Alta |
| 4 | **Updater quebra a instalação** (exit 134; referências stale) + copy/paste quebrado admitido ("bug que caçamos há dias") | "That's a pesky bug we have been chasing for days now" | #42 + #192 + [#16](https://github.com/23blocks-OS/ai-maestro/issues/16) · nov/2025-fev/2026 · usuários + mantenedor | Alta |
| 5 | **Só Claude é primeira classe** — hooks lentos (~30s)/inconsistentes em Codex e Gemini; "!" crasha Gemini; agentes perdem mensagens quando ocupados; WSL2 não funciona | "reliable on Claude but fire slowly (~30s) or inconsistently on Codex and Gemini" | [#321](https://github.com/23blocks-OS/ai-maestro/issues/321) + #334 + #322 + [#273](https://github.com/23blocks-OS/ai-maestro/issues/273) · mar-abr/2026 · usuários | Alta |

**Sinal de mercado:** tração externa fraca (HN: 3 pts, 1 comentário do próprio fundador); feedback concentrado em 2 power users. Perfil: instável em operação contínua (leaks) e diferencial central (mensageria A2A) sem isolamento — risco real de cross-talk destrutivo.

**Lição pro maestro-console:** (1) leak de PTY/recursos em operação contínua é o modo de falha típico do nicho — vigiar os PTYs do canvas (relevante pro unload de nó!); (2) mensagens entre agentes PRECISAM de isolamento por escopo/projeto — o modelo de cabos+envelopes do maestro-console já restringe por conexão explícita, manter esse invariante.

### 14. Nimbalyst (sucessor do Crystal)

**Identidade:** workspace visual p/ Codex/Claude Code e outros · Electron cross-platform · MIT (open source desde ~2026-04-30), grátis p/ uso individual · status: MUITO ativo (push 2026-07-03, ~1.044 stars) mas **315 issues abertas** em ~2 meses de open source — triagem não acompanha · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **CPU 100%+ permanente ao abrir** — Renderer nunca se recupera, máquina superaquece (ABERTA; dupe fechada sem resolver) | "the Renderer process immediately consumes over 100% CPU and never recovers, causing the machine to overheat" | [#444](https://github.com/nimbalyst/nimbalyst/issues/444) · 2026-05-26 · usuário | Alta |
| 2 | **Crash com 6-7+ sessões paralelas — progresso perdido** (dói na proposta central) | "with more than 6 or 7 sessions running intensively… Nimbalyst crashes often… the progress was lost" | [#117](https://github.com/nimbalyst/nimbalyst/issues/117) · 2026-04-30 · usuário (Windows) | Alta |
| 3 | **Fecha sozinho sem erro** — ~10 vezes numa semana, sem aviso nem recuperação de sessão (ABERTA) | "closes itself unexpectedly… no warning, error dialog, or session-recovery prompt" | [#190](https://github.com/nimbalyst/nimbalyst/issues/190) · 2026-05-07 · usuário | Alta |
| 4 | **Persistência de sessão quebrou após update** — "sua conversa anterior expirou ou foi limpa" em todo follow-up (tema recorrente: #65, #70, #71) | "'Your previous conversation session has expired or been cleaned up'. This started happening when I did the in-app update" | [#65](https://github.com/nimbalyst/nimbalyst/issues/65) · 2026-04-21 · usuário | Alta |
| 5 | **Auth do Claude expira no meio da sessão** — painel preso em "Authentication expired"; workaround = logout/login completo (ABERTA) | "Nimbalyst sometimes loses the Claude Code auth token" | [#671](https://github.com/nimbalyst/nimbalyst/issues/671) · 2026-06-22 · usuário | Alta |
| 6 | **Codex quebrado dentro do app enquanto o CLI funciona**; modelos GPT sempre desabilitados | issues #296 + #87 | mai/2026 · usuários | Média-alta |
| 7 | **UX de interrupção agressiva** (hard abort, mensagem volta pra caixa) + ações de UI mortas ("Arquivar não faz nada", botão de launch sem função) + crash-loop com markdown grande (#652/#321) | "Right-clicking a session → 'Archive' does nothing — no feedback, no state change" | [#337](https://github.com/nimbalyst/nimbalyst/issues/337) + [#282](https://github.com/nimbalyst/nimbalyst/issues/282) + #176 · mai-jun/2026 · usuários | Alta |
| 8 | **"Herda o risco de reinício do Crystal"** — o vendor já matou um produto antes | "Young; inherits Crystal's restart risk" | [rywalker](https://rywalker.com/research/mac-coding-agent-apps) · atualizado 2026-06-11 · editorial | Média |

**Sinal de mercado:** desenvolvimento acelerado, mas o padrão dominante das dores é **estabilidade sob paralelismo real** — exatamente a promessa. Reddit: nada. HN: 1 feedback orgânico, morno.

**Lição pro maestro-console:** paralelismo de verdade se prova sob carga (crash aos 6-7 nós seria fatal no CM4 — reforça o valor do unload de nó); e update de app nunca pode invalidar sessões salvas (testar migração de estado a cada versão).

### 15. Crystal (stravu) — autópsia do pioneiro

**Identidade:** pioneiro da categoria (múltiplas sessões Claude/Codex em worktrees, A/B de agentes) · MIT, 3.095 stars · status: **MORTO — deprecated 2026-02-26**, sucedido pelo Nimbalyst; repo não arquivado, issues novas entram sem resposta · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Release do Mac quebrado por semanas** — janela não abria em 0.3.0/0.3.1/0.3.2; mantenedor não reproduzia; issue mais comentada, ficou ABERTA até a morte | "mac release 0.3.0 doesn't show any window" (4+ usuários confirmando) | [#200](https://github.com/stravu/crystal/issues/200) · 2025-09-29 · usuários | Alta |
| 2 | **Detecção do Claude CLI quebrada desde o início** — "not found in PATH" com caminho configurado; "travado pra sempre em 'Starting Claude Code…'" (dor fundacional, nunca fechada) | "I have the claude executable path set but I receive 'Claude Code CLI not found in PATH'" | [#9](https://github.com/stravu/crystal/issues/9) · jun-jul/2025 · 4 usuários | Alta |
| 3 | **Linux/WSL de segunda classe** — tela preta com artefatos; resposta do mantenedor: "não tenho máquina pra testar — quer mandar um PR?"; GTK mismatch "explode" | "I don't have a machine that I can test this on" | [#20](https://github.com/stravu/crystal/issues/20) + #106 · jul/2025 · usuários + mantenedor | Alta |
| 4 | **Worktrees dentro do repo poluem o ambiente** (vite/vue recarregando; configurar ignore na mão) e — pior — **agente escapando da branch: mudanças na main** | "I've experienced this several times now where CC makes its changes in the main branch, even though it should be working in its own branch" | [#152](https://github.com/stravu/crystal/issues/152) · ago/2025 · usuários | Alta |
| 5 | **Suspeita de telemetria oculta** — "como destruir confiança em um passo fácil" (era tráfego do próprio Claude Code, mas a dor de percepção foi real) | "Is this app secretly phoning home?… It kinda stinks that this isn't disclosed anywhere" | [#95](https://github.com/stravu/crystal/issues/95) · 2025-07-21 · usuário | Alta |
| 6 | **Morte por consolidação deixou buraco**: na data da deprecation o Nimbalyst NÃO tinha Codex (só chegou ~abr/2026) — "a falta de Codex o torna natimorto pra mim" | "for now the lack of codex makes it DoA for me" | [#235](https://github.com/stravu/crystal/issues/235) · 2026-02-14 · usuário + mantenedor ("Yes, this project is dead") | Alta |

**Sinal de mercado (por que morreu):** consolidação estratégica declarada ("colocamos muito mais recursos no Nimbalyst"), não falha técnica — mas o pioneiro morreu com issues fundacionais (detecção de CLI, packaging Mac, Linux 2ª classe) jamais fechadas. A categoria pune quem não sustenta a base multiplataforma.

**Lição pro maestro-console:** (1) detecção/lançamento robusto do agente é a fundação — se falhar, nada mais importa; (2) agente escapando do isolamento (commit na main!) é a violação de confiança máxima — o invariante de autoridade host-side do maestro-console existe pra isso; (3) transparência sobre qualquer tráfego de rede, mesmo o dos agentes.

### 16. JAT (jat.tools)

**Identidade:** "The World's First Agentic IDE" — supervisão de 20+ agentes via UI web local (SvelteKit) + tmux · MIT, macOS(port de terceiro!)/Linux · status: ativo porém sem tração (244 stars, Discord de 7 membros, 0 issues abertas na história) · varrido em 2026-07-03.

| # | Dor | Evidência | Fonte · data · autor | Confiança |
|---|-----|-----------|---------------------|-----------|
| 1 | **Setup pesado (tmux obrigatório) + curva íngreme** | "tmux required — Heavier setup than simple apps"; "Steep learning curve — paradigm shift required" | [rywalker/research/jat](https://rywalker.com/research/jat) · 2026-02-13 (atualizado 06-11) · editorial | Média |
| 2 | **Bus factor = 1, comunidade inexistente** — sem base de usuários pra absorver churn do mantenedor; "nenhuma discussão pública substantiva encontrada" | "the bus factor is exactly one"; "Tiny community… 7-member Discord" | rywalker · editorial (números conferidos ao vivo no repo → fato Alta) | Alta (fato) |
| 3 | **Sem releases versionados (direto na master), sem Windows, UI só no browser** | "No tagged releases — Ships straight to master with no versioning" | rywalker · editorial | Média |
| 4 | **Fundamentos consertados por terceiros** — falsos negativos de auth com CLIs por assinatura, resolução de path quebrada, e **suporte a Mac adicionado por contribuidor externo** (nasceu sem) | PRs #2-#5 mergeados (títulos lidos no repo) | [github.com/joewinke/jat](https://github.com/joewinke/jat) · fev/2026 · contribuidores externos | Alta |
| 5 | **Zero relato de usuário final em qualquer canal** — não é ausência de dor, é ausência de USO validado | 0 issues de usuário; HN/Reddit vazios (medição direta) | varredura · 2026-07-03 | Alta |

**Sinal de mercado:** ambição de mantenedor solo sem tração mensurável; o risco nº 1 apontado é longevidade, não funcionalidade.

**Lição pro maestro-console:** feature-list gigante sem comunidade não converte; supervisionar 20+ agentes tem apetite, mas exigir tmux/browser afasta quem quer app pronto.

### 17. parallel-code (johannesjo)

**Identidade:** Claude Code/Codex/Gemini lado a lado em worktrees · Electron, MIT, grátis · macOS/Linux (Windows NÃO suportado — só WSL improvisado) · status: ativo (797 stars, push 2026-07-03), solo dev do Super Productivity, projeto ~4 meses · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Terminal corrompe a renderização** — caracteres sobrepostos/glifos errados por 1+ minuto; workaround inconsistente (ABERTA, sem repro) | "characters overlap, render with incorrect glyphs… can persist for over a minute" | [#121](https://github.com/johannesjo/parallel-code/issues/121) · 2026-05-16 · usuário | Alta |
| 2 | **Notificações NUNCA disparavam no macOS** — app nunca pedia permissão; SO descartava silenciosamente | "No permission prompt is ever shown… macOS discards them silently" | [#122](https://github.com/johannesjo/parallel-code/issues/122) · 2026-05-16 · usuário | Alta |
| 3 | **Agente morria antes do prompt ser enviado**; mantenedor admite: "pode não ser 100% confiável" | "Might be this is not 100% reliable all the time" | [#146](https://github.com/johannesjo/parallel-code/issues/146) · 2026-05-25 · usuário + mantenedor | Alta |
| 4 | **Sem auto-update** (reinstalar a cada versão; mantenedor não vai fazer) + Windows parado desde fev ("WSL é estranho, lento e pesado") | "I can use it through wsl but it's a bit odd, slow and resource intensive" | [#91](https://github.com/johannesjo/parallel-code/issues/91) + [#9](https://github.com/johannesjo/parallel-code/issues/9) · fev-abr/2026 · usuários | Alta |
| 5 | Miúdas: sidebar esmagada com muitos projetos, atalho de troca de worktree quebrado, .dmg que não baixava, sem suporte a pasta sem git | issues #87, #79, #82, #66 (fechadas) | fev-mai/2026 · usuários | Alta |

**Sinal:** saudável e responsivo, mas single-maintainer sem distribuição madura. **Lição:** notificação que falha silenciosamente (dor 2) é armadilha clássica — testar o caminho real no SO alvo, não só a chamada.

### 18. Jean (Coollabs / jean.build)

**Identidade:** "dev environment for AI agents" — Tauri desktop + web, da org do Coolify · Apache-2.0, grátis · "testado no macOS; Win/Linux devem funcionar mas não são totalmente testados" (admitido) · status: muito ativo (1.105 stars, 466+ issues em ~5 meses) · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Auto-update do CLI gerenciado quebra o produto silenciosamente** — AskUserQuestion degrada pra texto plano sem erro; `auto_update_ai_backends` (default true) atualiza em background e mata o workaround de pinar versão (ABERTA) | "silently fall back to plain-text prompts — no error… silently background-updates the managed CLI on startup" | [#460](https://github.com/coollabsio/jean/issues/460) · 2026-06-29 · usuário | Alta |
| 2 | **Plan mode quebrado** — ExitPlanMode não encontrado; plano aparece mas a UI de aceitar some (ABERTA) | "Plan is layed out but UI for accepting is missing" | [#438](https://github.com/coollabsio/jean/issues/438) · 2026-06-25 · usuário | Alta |
| 3 | **Sem como aprovar comando** (usuário preso rodando manualmente) + **cancelar mensagem = perder a sessão inteira** | "you can't cancel and continue on the session. you basically lose the session" | [#374](https://github.com/coollabsio/jean/issues/374) + [#395](https://github.com/coollabsio/jean/issues/395) · mai-jun/2026 · usuário | Alta |
| 4 | **Windows/WSL de segunda classe** — 7+ issues: não enxerga Claude no WSL, MCP não funciona, login OpenCode falha, SmartScreen barra o instalador | issues #443, #432, #420, #415, #367, #429, #384 | mai-jun/2026 · usuários | Alta |
| 5 | **Detecção/auth de backend falha até no macOS** (3 CLIs funcionando no terminal, Jean não detecta) | [#387](https://github.com/coollabsio/jean/issues/387) (ABERTA) | 2026-06-02 · usuário | Alta |

**Sinal:** tração real com dor dominante = fragilidade da integração com os CLIs. **Lição:** nunca auto-atualizar o agente gerenciado sem opt-in — versão do CLI é parte do contrato de estabilidade (relevante pro maestro-console, que também depende do CLI do Claude/Codex).

### 19. Polyscope (Beyond Code)

**Identidade:** orquestração macOS com clones copy-on-write, do criador do Beyond Code (Laravel) · **closed-source** (repo público só de issues), free + planos pagos · status: ativo; tração fraca fora do ecossistema Laravel (HN: 3 pts, 0 comentários) · varrido em 2026-07-03. (Lib C++ polyscope e Universal Robots PolyScope descartados.)

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Stop não para o agente** — roda por HORAS, timer subindo sem trabalho, exige matar o app (ABERTA desde maio) | "agents continue running for several hours and do not stop when the Stop button is clicked" | [#161](https://github.com/beyondcode/polyscope-community/issues/161) · 2026-05-06 · usuário | Alta |
| 2 | **Autopilot ignora o modelo configurado e força Claude → estoura a cota** sem opção de trocar | "Everytime I use stories, it uses Claude as the agent… it just immediately runs out of usage and there is no way to switch the model" | [#179](https://github.com/beyondcode/polyscope-community/issues/179) · 2026-05-22 · usuário | Alta |
| 3 | **Agente em background rouba o workspace ativo no meio da digitação** — prompt em andamento perdido (ABERTA) | "A background agent opening a preview hijacks the active workspace mid-typing" | [#178](https://github.com/beyondcode/polyscope-community/issues/178) · 2026-05-22 · usuário | Alta |
| 4 | **UI preta exigindo hard quit; trava na splash; consumo de energia em idle; mobile "muito instável"** | issues #181, #186, #136, #140 | abr-jun/2026 · usuários | Alta |
| 5 | **Clones não são limpos ao deletar workspace** (lixo em disco — e o pitch é justamente clones CoW); Linux ficava versões atrás | "removing/deleting a workspace doesn't delete local files in .polyscope/clones" | [#171](https://github.com/beyondcode/polyscope-community/issues/171) + #153 · mai/2026 · usuários | Alta |

**Sinal:** backlog de bugs graves ABERTOS num app pago de dev solo — confiabilidade do runtime é a dor nº 1. **Lição:** Stop/kill TEM que ser garantido pelo host (SIGKILL do maestro-console via ADR-23 está no caminho certo); e foco roubado no meio da digitação é violação de UX imperdoável num canvas.

### 20. Dorothy (Charlie85270)

**Identidade:** "Super Agent" + kanban orquestrando agentes CLI · MIT, grátis, macOS-only (Linux/Windows = issue aberta do próprio dev) · status: micro-projeto solo (314 stars, 12 issues, várias sem resposta) · varrido em 2026-07-03. (DorothyAI de patentes e bevry/dorothy descartados.)

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Orquestração inconsistente — o core falha**: Super Agent na maioria das vezes NÃO despacha; tarefa concluída não fecha no kanban (ABERTA há 3+ meses sem resposta) | "most of times it does not… the task stays as in progress… I have to tell superagent to close the task explicitly" | [#45](https://github.com/Charlie85270/Dorothy/issues/45) · 2026-03-28 · usuário | Alta |
| 2 | **Não instala no macOS 26.4** — app sem assinatura/notarização; "fix" é bypass do Gatekeeper ensinado por outro usuário | [#50](https://github.com/Charlie85270/Dorothy/issues/50) (ABERTA) | 2026-04-16 · usuário | Alta |
| 3 | **Controle remoto quebrado** — mensagens Telegram/Slack coladas sem enviar; Codex via pnpm não detectado; shebang bash não-portável | "Telegram/Slack messages stuck as pasted text" | #38 + #40 + #52 · mar-abr/2026 · usuários | Alta |

**Sinal:** conceito vende, confiabilidade do despacho não sustenta. **Lição:** despacho de orquestração precisa de confirmação verificável pelo host — a MESMA dor da delegação do Maestri (C1) e do Dorothy confirma que é a dor central da categoria.

### 21. Ami (ami.dev / Million)

**Identidade:** ambiente desktop de coding agents da Million (Aiden Bai) · closed-source (repo só de releases, 26 stars) · custo de API + 2M tokens grátis · status: ⚠️ repo sem push desde 2026-02-25 (~4 meses) + sinais de pivô de marketing · varrido em 2026-07-03. (AMI/AWS, AMI BIOS descartados.)

**Dores (3 issues, todas do mesmo usuário, jan/2026):** crash do main process no boot ("Sent before connected"); "Getting environment from the CLI failed" — o stack revela que o app carrega a UI de `app.ami.dev` (depende do serviço web deles pra funcionar); "Prompt is too long" sem auto-compactação (vendor: "coming soon"). [issues 1-3](https://github.com/millionco/ami-releases/issues) · Confiança: Alta (dores) / Média (interpretação da dependência web).

**Sinal:** sem base pública de usuários (HN: 1 pt, 0 comentários); alto risco de descontinuação. **Lição:** "desktop app" que precisa do backend web do vendor não é local-first — transparência arquitetural é diferencial.

### 22. Clave (Codika)

**Identidade:** app macOS p/ múltiplas sessões Claude Code (+ Gemini/Codex; Windows por contribuição externa) · MIT, grátis · status: ativo (push 2026-07-03) mas minúsculo (36 stars, ~3 usuários externos nas issues) · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **App fecha/cai = TODAS as sessões morrem com trabalho em voo** — "o modo de falha mais doloroso" do modelo PTY-dentro-do-app (depois mitigado com tmux opt-in) | "When Clave quits or crashes, every session's PTY dies with it — the running agent is gone, mid-task state and TUI scrollback included" | [#19](https://github.com/codika-io/clave/issues/19) · 2026-06-05 · usuário | Alta |
| 2 | **Screenshot arrastado insere caminho temp que é apagado antes de o agente ler** | "Dragged macOS screenshot preview inserts a temp path that's deleted before the agent can read it" | [#16](https://github.com/codika-io/clave/issues/16) · 2026-06-04 · usuário | Alta |
| 3 | **Sem indicador de estado por aba** — fácil perder quando o agente terminou/espera input; todas as abas idênticas | "All tabs look identical regardless of their status" | [#18](https://github.com/codika-io/clave/issues/18) · 2026-06-04 · usuário | Alta |
| 4 | **Todas as sessões compartilham ~/.claude** — impossível conta de trabalho + pessoal simultâneas ("que é meio que o ponto central") | "you can't have a work session and a personal session open at the same time, which is kind of the whole point" | [#22](https://github.com/codika-io/clave/issues/22) · 2026-06-05 · usuário | Alta |

**Sinal:** feedback minúsculo mas TODO no território do Maestri: persistência de sessão, visibilidade de estado, anexos, multi-conta. **Lição:** a dor nº 1 (quit do app mata sessões) é exatamente o que a captura de sessão do unload de nó resolve — e o Clave prova que a comunidade valoriza isso a ponto de exigir tmux.

### 23. Constellagent

**Identidade:** app Electron de agentes paralelos c/ worktrees · **SEM licença publicada** (código público ≠ open source) · status: ⚠️ esfriando — 213 stars, sem commits desde 2026-05-05, dev solo (73/75 commits) · varrido em 2026-07-03.

**Dores:** sem LICENSE — bloqueia fork/uso (aberta desde fev, [#40](https://github.com/owengretzinger/constellagent/issues/40)); criação de workspace falha em repo sem remote (`git fetch origin` incondicional — MESMA dor do Emdash/Conductor, [#9](https://github.com/owengretzinger/constellagent/issues/9), aberta desde 2026-02-13); sem binários/releases (compilar da fonte, [#8](https://github.com/owengretzinger/constellagent/issues/8)); agentes param quando o app fecha; review independente: "não recomendado pra quem precisa de dependência com licença clara" ([rywalker](https://rywalker.com/research/constellagent), atualizado 2026-06-11). Confiança: Alta.

**Sinal/lição:** mais um validador de demanda que ameaça viva; a dor do remote obrigatório aparece pela 3ª vez no nicho — fluxo git 100% local é lacuna sistêmica.

### 24. Aizen (vivy-company)

**Identidade:** workspace macOS nativo (Swift/Metal, libghostty, agentes via ACP) · GPL-3.0 + CLA · Apple Silicon only ("decisão controversa" de largar Intel) · status: ⚠️ 275 stars, sem push desde 2026-05-22 (~6 semanas) com bugs abertos ignorados · varrido em 2026-07-03. (Aizen de Bleach descartado.)

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Crash em loop ao usar Claude — força quit** | "It crashes after a few seconds and I have to force quit" (stackshot anexado) | [#18](https://github.com/vivy-company/aizen/issues/18) (11 comentários) · 2026-02-09 · usuário | Alta |
| 2 | **Agentes ACP inutilizavelmente lentos** — Codex preso "thinking"; Claude 5+ min pra prompt simples (ABERTA ~3 meses) | "this is unusable for me" | [#25](https://github.com/vivy-company/aizen/issues/25) · 2026-04-10 · usuário | Alta |
| 3 | **Trocar de environment reinicia os terminais 2..N e perde o progresso** | "terminals 2-N get restarted and previous progress disappears" | [#21](https://github.com/vivy-company/aizen/issues/21) · 2026-02-22 · usuário | Alta |
| 4 | **GUI não herda o ambiente do shell** — Node via nvm/fnm fora do PATH → Claude "exit code 1" (mesma classe do mux #797 e herdr #966) | "macOS GUI apps don't inherit the user's shell environment" | [#22](https://github.com/vivy-company/aizen/issues/22) · 2026-03-01 · usuário | Alta |
| 5 | Editor "parece quebrado" (ABERTA desde jan), tema claro quebrado (ABERTA), input chinês corrompido, MCP não carrega, OpenCode não funciona, Intel excluído ("tem alguns de nós que não podem simplesmente atualizar") | issues #17, #24, #23, #19, #16, #26 | dez/2025-abr/2026 · usuários | Alta |

**Sinal:** o lote com mais dor de estabilidade por usuário real + repo esfriando = usuários queimados. **Lição:** ambiente do shell (PATH/nvm/direnv) é dor recorrente da categoria — o maestro-console lançando agentes via shell do usuário evita a classe inteira.

### 25. supacode (Supabit)

**Identidade:** "worktree coding agents command center" macOS nativo (libghostty) · licença **FSL-1.1** (source-available, não-OSI; aberto em 2026-02-06 sob pressão) · status: líder do lote — 2.002 stars, muito ativo, dev responsivo · varrido em 2026-07-03. (Supabase descartado.)

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Acusação pública de padrão de exfiltração de dados** (era closed-source; acessos a iCloud/Documents/dados de outros apps) — dev investigou (era init do libghostty + TCC) e **abriu o código NO MESMO DIA** pela pressão | "These access patterns are consistent with data exfiltration… there is no way for users to audit what the application does" | [#26](https://github.com/supabitapp/supacode/issues/26) · 2026-02-06 · usuário | Alta |
| 2 | **Distribuição quebrada por dias** — brew/DMG com erro 500 e "DMG damaged" multi-região (cache Cloudflare envenenado; usuários instalando via VPN) | "It says the DMG is damaged and can't install it either from homebrew or direct download" | [#405](https://github.com/supabitapp/supacode/issues/405) (14 comentários, ABERTA) · jun/2026 · usuários | Alta |
| 3 | **Colar imagem do clipboard não funciona com Claude Code** (3 issues recorrentes) | "using Cmd+V does not attach the image to the prompt" | #485 + #555 + #291 · mai-jul/2026 · usuários | Alta |
| 4 | **Detecção do Codex no login shell falha** com Codex instalado e funcionando no zsh; Option+Backspace não apaga palavra (issue aberta mais antiga); dead keys de acentuação não funcionam (teclado internacional!) | "Codex is definitely installed in the machine & available in terminal/shell (zsh)" | [#504](https://github.com/supabitapp/supacode/issues/504) + #5 + [#495](https://github.com/supabitapp/supacode/issues/495) · jan-jun/2026 · usuários | Alta |
| 5 | **Lacunas estruturais abertas** — GitLab (#365, 9 comentários), repos forçados em estrutura flat `~/.supacode/repos/` (agentes perdem contexto do projeto, ex. agents.md), SSH remoto | "Agents may miss project-specific context (e.g. agents.md)" | #365 + [#226](https://github.com/supabitapp/supacode/issues/226) + #65 · abr-jun/2026 · usuários | Alta |

**Sinal de mercado:** mesmo o líder mais responsivo repete o padrão do nicho (paste de imagem, PATH/login shell, i18n de teclado, distribuição, multi-forge). O episódio #26 prova: **confiança/auditabilidade é gatilho de compra real — a ponto de forçar abertura de código.**

**Lição pro maestro-console:** open source de verdade desde o dia 1 elimina o flanco que forçou o supacode a capitular; e dead keys/acentos importam DIRETAMENTE pro público PT-BR do maestro-console.

# Parte 3 — Terminal-first (CLI/tmux)

### 26. herdr (herdr.dev) — líder da categoria terminal

**Identidade:** "agent multiplexer that lives in your terminal" — Rust, Linux/macOS (Windows beta) · licença "Other"/NOASSERTION (não-OSI) · status: MUITO ativo — **10.707 stars em ~3 meses** (criado 2026-03-27), ecossistema próprio (herdr-plus, awesome-herdr) · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Reimplementar emulação de terminal gera cauda longa de bugs VT** — OSC 11 devolve cor errada, queries de pixel-size não respondidas (preview de imagem vê 0×0), gráficos kitty congelam, cursor sem DECSCUSR, altscreen demora a restaurar | issues [#714](https://github.com/ogulcancelik/herdr/issues/714), #835, #692, #696, #947 | jun-jul/2026 · usuários | Alta |
| 2 | **Seleção de mouse no vim trava o pane** (tem que fechar o pane); copy mode inferior ao tmux (seleção acompanha output ao vivo, bloqueia troca de foco) | "vim mouse selection hanged the pane and you must close the pane" | [#693](https://github.com/ogulcancelik/herdr/issues/693) + #680 + #681 · jun/2026 · usuários | Alta |
| 3 | **Integração profunda de SO quebrada** — macOS: panes em sessão launchd de background → CLIs com keychain (1Password) falham; nix build falha; Windows beta com API "agent-aware" retornando vazio | "panes run in a Background launchd session, so keychain-backed CLIs fail inside herdr" | [#966](https://github.com/ogulcancelik/herdr/issues/966) + #808 + #830 + #872 + #962 · jun-jul/2026 · usuários | Alta |
| 4 | **Detecção de agente falha em setup não-padrão** (nix-wrapped Claude Code nunca aparece) + cursor flicker constante | "devenv agents never appear" | [#803](https://github.com/ogulcancelik/herdr/issues/803) + #857 + #967 · jun/2026 · usuários | Alta |
| 5 | **"Rodar NO terminal é ostentação, não vantagem" — perde pra GUI** na comparação direta | "conductor.build is way better IME. Running _in_ the terminal is a flex, but doesn't actually bring any advantage" | [HN](https://news.ycombinator.com/item?id=48714802) (108 comentários) · 2026-06-29 · @scubbo | Alta |
| 6 | **Observabilidade rasa com muitos agentes** — difícil ver o que cada um faz, que programa chamou, onde travou; mobile/touch não funciona (Termius/Android sem tap) | "it becomes difficult to see what each of them is doing… and where they are getting stuck" | HN · 2026-06-29 · @kerlenton, @bangau1 | Alta |
| 7 | **Fricção pra quem vive em tmux** — sem layouts declarativos (tmuxp); ceticismo "por que não só tmux/kitty?" vivo até no líder | "So basically tmuxinator?"-style objections | HN · 2026-06-29 · @timwis, @snapplebobapple, @rw_panic0_0 | Alta |

**Sinal de mercado:** líder disparado da categoria; as dores mostram o custo de reimplementar terminal do zero e a objeção de valor persistente. O recurso mais elogiado — status por agente + notificação de "aguardando input" — é também a fonte das reclamações quando falha. **Valida diretamente a tese do Maestri/maestro-console.**

**Lição pro maestro-console:** (1) usar VTE maduro (como o GTK/VTE do projeto) evita a cauda de bugs VT que o herdr paga por ter reimplementado; (2) status/observabilidade por agente é O recurso da categoria — investir no monitor de atividade; (3) a objeção "por que não tmux?" se responde com o que o terminal puro não dá: canvas espacial + orquestração verificável.

### 27. amux (andyrewlee)

**Identidade:** TUI MIT p/ agentes paralelos sobre tmux ≥3.2 · Linux/macOS (Windows não suportado — admitido) · 133 stars, ativo · varrido em 2026-07-03. ⚠️ Todo o burburinho "amux" no HN pertence ao amux.io da mixpeek (produto DIFERENTE, excluído).

**Dores:** apenas 1 encontrada — atalhos não remapeáveis (hjkl fixo quebra layouts alternativos; [#365](https://github.com/andyrewlee/amux/issues/365), 2026-06-12, aberto sem resposta) + limitação admitida (sem Windows). **Sinal:** uso público quase nulo; nome fragmentado entre 5+ projetos "amux" de 2026 mata a descoberta orgânica.

### 28. superset (superset.sh, YC P26)

**Identidade:** "Code Editor for the AI Agents Era" — Mac-first · licença "Other"/NOASSERTION · status: maior tração do lote — **12.241 stars**, launch HN mai/2026 com 135 comentários · varrido em 2026-07-03. Apache Superset (BI) filtrado.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **⚠️ Flag perigosa hardcoded** — agente Claude sempre roda com `--dangerously-skip-permissions`, sem opção | "claude agent always uses hardcoded argument --dangerously-skip-permissions" | [#2419](https://github.com/superset-sh/superset/issues/2419) · 2026-03-12 · usuário | Alta |
| 2 | **Performance horrorosa / 2 GB de RAM** — input lag periódico, regressões, fixes repetidos que não resolvem | "[bug] performance is horrendous and should be looked into"; "2GB resource usage is too much for this app" | [#3116](https://github.com/superset-sh/superset/issues/3116) + #2861 + [HN](https://news.ycombinator.com/item?id=48236770) · mar-mai/2026 · usuários | Alta |
| 3 | **Rendering de terminal corrompido** — texto sem sentido, corrupção CJK, scroll pulando sozinho | "Gibberish text and symbols"; "CJK glyph corruption" | #4601 + #4639 + #3668 + #2498 · mar-mai/2026 · usuários | Alta |
| 4 | **Login obrigatório num app local** + baixa o próprio OpenCode ignorando o instalado + sem escolher modelo antes do prompt | "It's behind a login wall, tries to download its own OpenCode instead of using the one installed" | [#2685](https://github.com/superset-sh/superset/issues/2685) + HN @tacone · mar-mai/2026 | Alta |
| 5 | **Só macOS (nem Intel)** — Linux aberto há ~7 meses; "WINDOWS NEEDED PLEASE !!!" | issues #405, #499, #2692, #3207, #2212 | dez/2025-abr/2026 · usuários | Alta |
| 6 | **Worktrees vazam estado** — deleção deixa órfãs no disco; workspace indeletável; falha ao criar de branch existente | "Workspace deletion leaves orphaned worktree directories on disk" | #2863 + #4555 + #2575 · mar-mai/2026 · usuários | Alta |
| 7 | **Regressão de atalhos a cada release** (Ctrl+Key quebrou na 1.5.0; Shift+Enter na 1.8.0) | 3 issues | #3370 + #3435 + #4008 · abr-mai/2026 | Alta |
| 8 | **Preço/custo** — Linear atrás de paywall "US$20/mês salgado"; "como rodar N agentes paralelos sem torrar a quota?" | "Monthly token quotas burn through quickly" | HN launch · 2026-05-22 · @tdi, @Tooster | Alta |

**Sinal de mercado:** tração enorme com reclamação proporcional — app pesado, Mac-only, login forçado e regressões são os flancos exatos de um concorrente leve, local-first e sem login.

**Lição pro maestro-console:** NUNCA hardcodar bypass de permissões (mesmo invariante do episódio cmux); local-first sem login é diferencial real; e higiene de worktree/estado órfão importa (paralelo: ids reciclados/órfãos que o projeto já corrigiu no canvas).

### 29. tmux-ide (wavyrai)

**Identidade:** projeto → IDE de terminal via `ide.yml` sobre tmux · MIT, npm, 519 stars · Show HN 2026-03-18 (88 pts) · varrido em 2026-07-03.

| # | Dor | Evidência | Fonte · data · autor | Confiança |
|---|-----|-----------|---------------------|-----------|
| 1 | **Instalação quebrada no Linux há ~3 meses** — dependência darwin-arm64 obrigatória (EBADPLATFORM); usuário abriu o próprio PR, parado | "npm error code EBADPLATFORM: Unsupported platform for @opentui/core-darwin-arm64" | [#76](https://github.com/wavyrai/tmux-ide/issues/76) · 2026-04-01 · usuário | Alta |
| 2 | **`.` no nome do pane derruba o app** com erro genérico; mantenedor sumiu ("Will look into this!") | "name: radicaloptimist.org fails with tmux failed" | [#17](https://github.com/wavyrai/tmux-ide/issues/17) · 2026-03-19 · usuário | Alta |
| 3 | **"Isso é só tmuxinator?"** + "joga complexidade demais no usuário" | "So basically tmuxinator?"; "this shifts too much complexity onto the user" | [HN](https://news.ycombinator.com/item?id=47428868) · 2026-03-18 · usuários | Alta |

**Sinal:** pico no Show HN e manutenção fraca depois — risco de abandono (dor de confiabilidade, não de features).

### 30. HiveTerm (hiveterm.com)

**Identidade:** desktop multi-agente declarativo via `hive.yml` (Mac AS+Intel/Win/Linux) · **closed source, sem tracker público** · Free apertado (fontes divergem: 1-3 projetos/2-5 agentes) · Pro **US$99/ano**, 2 máquinas · varrido em 2026-07-03. (trsdn/HiveTerm e Hiveterminal crypto descartados.)

**SEM FEEDBACK ENCONTRADO** — Show HN 2026-05-11: 2 pontos, 0 comentários; zero menção orgânica. Fricções estruturais (vendor): closed source sem canal de bugs; free tier abaixo do caso de uso típico; US$99/ano num nicho dominado por OSS grátis.

**Sinal/lição:** closed-source pago não está arrancando neste nicho — corrobora o flanco open-source visto no Conductor/Maestri.

### 31. multi-agent-shogun

**Identidade:** orquestração hierárquica de Claude Code via tmux (shogun → karo → ashigaru) · MIT, 1.383 stars, ativo · comunidade primariamente japonesa (Zenn/Qiita/note; HN ~zero) · varrido em 2026-07-03.

| # | Dor | Evidência (tradução do japonês) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Falha silenciosa em script central** — mostra "sucesso" mas settings.yaml não atualiza; agente sobe com CLI/modelo errado | "o script mostra 'sucesso' mas o settings.yaml não é atualizado de fato" | [#136](https://github.com/yohey-w/multi-agent-shogun/issues/136) · 2026-04-25 · usuário (corrigida) | Alta |
| 2 | **Panes hardcoded → drift ao mudar a formação** — watchers apontando pro pane errado; auditor ficou 25h em silêncio | "o mapeamento de panes é hardcoded; mudar a formação gera drift" | [#151](https://github.com/yohey-w/multi-agent-shogun/issues/151) · 2026-05-10 · usuário (corrigida) | Alta |
| 3 | **Onboarding confuso** — "instalei, e agora?"; setup exige entender tmux, inotifywait, YAML, boot de agentes | "a parte 'tá, mas como é que USA isso afinal?' ainda é difícil de captar" | [#143](https://github.com/yohey-w/multi-agent-shogun/issues/143) · 2026-04-30 · usuário | Alta |
| 4 | **Custo e degradação de contexto** — sessão longa esquece contexto (compactação); Haiku nos ashigaru barateia mas degrada qualidade; uso sério pede Claude Max US$100-200+/mês | review independente em japonês | [note.com](https://note.com/ai_jidoka_lab/n/n1bb8960fefe0) · 2026 · blog | Alta |
| 5 | **Shogun executa em vez de delegar** — a hierarquia não se sustenta sozinha | "o próprio agente Shogun completou o trabalho — eu não queria que ele trabalhasse" | ecossistema Qiita/note (via busca) | Baixa-média |

**Sinal de mercado:** nicho japonês vibrante que valida demanda por orquestração hierárquica — e mostra que fazê-la sobre tmux cru + shell scripts cobra caro em robustez (falhas silenciosas, drift).

**Lição pro maestro-console:** papel de líder que "faz em vez de delegar" é dor conhecida (relevante pro Maestro mode); estado de orquestração deve ser verificado pelo HOST, nunca por script que "mostra sucesso" sem conferir.

### 32. dmux (standardagents/FormKit)

**Identidade:** "dev agent multiplexer" TUI/npm sobre tmux + worktrees · MIT, 1.686 stars, site dmux.ai · Mac/Linux/WSL (Windows nativo fora) · status: ativo, mantido por empresa, fecha issues rápido · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **⚠️ Rodava tudo com `--dangerously-skip-permissions` hardcoded** — todos os agentes com acesso irrestrito, sem config (2º caso no nicho, com superset) | "dmux currently hardcodes --dangerously-skip-permissions… all agents run with full unrestricted access" | [#7](https://github.com/standardagents/dmux/issues/7) (+#16) · 2026-02-20 · usuário | Alta |
| 2 | **Chave OpenRouter na prática obrigatória** — sem ela, usuário trava na tela de prompt; comunidade fez fork (dmux-cc) pra fugir do lock-in; mantenedor admite o trade-off ("harness completo é lento demais") | "Being limited to just OpenRouter is a bit of a hassle"; "the juice wasn't worth the squeeze" | [#20](https://github.com/standardagents/dmux/issues/20) (ABERTA) · fev/2026 · usuários + mantenedor | Alta |
| 3 | **TUI congela/quebra em terminais variados** — 3 reports independentes ("Critical issue in the latest version"; ctrl-c lentíssimo; preso sem mover entre painéis no Alacritty/iTerm) | "dmux's TUI rendering is completely broken in your terminal" | [#54](https://github.com/standardagents/dmux/issues/54) + #11 + #26 · fev-mar/2026 · usuários | Alta |
| 4 | **Windows: saída silenciosa com exit 1** (HOME undefined, erro engolido por .catch) | "No error message is printed; the user just bounces back to the shell prompt" | [#85](https://github.com/standardagents/dmux/issues/85) · 2026-04-28 · usuário | Alta |
| 5 | **Input CJK quebrado** (cursor errado, Shift+Enter insere texto — ABERTA) + atalhos macOS de apagar palavra ausentes + "quit" deixa janela tmux viva (lixo residual) + merge bloqueado pelos próprios diretórios .dmux/ | "If it's not working out of the box, it's going to hurt adoption" | [#64](https://github.com/standardagents/dmux/issues/64) + #39 + [#80](https://github.com/standardagents/dmux/issues/80) + #56 · fev-abr/2026 · usuários | Alta |

**Sinal:** crescimento rápido, mas decisão de produto polêmica (OpenRouter embutido) gerou forks e a instabilidade de TUI se repete. **Lição:** 3º caso da categoria confirmando: bypass de permissões nunca pode ser default; e dependência externa embutida (OpenRouter) só pra features cosméticas gera revolta.

### 33. claude-squad (smtg-ai) — o incumbente estagnado

**Identidade:** gerenciador TUI de agentes (Claude/Codex/OpenCode/Amp) sobre tmux+gh · **AGPL-3.0**, Go · o maior da categoria CLI: **8.013 stars** · status: ⚠️ manutenção estagnada — último push 2026-06-17, bugs centrais abertos ~9 meses com fix da comunidade parado · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Bug-assinatura "error capturing pane content"** — tela congela ao criar agente; desde abr/2025, voltou e segue ABERTO com "same issue" acumulando (macOS e Linux); usuário até diagnosticou a causa no código, sem resposta | "Press N to create a new agent… Watch the display freeze"; "same here, seems broken" | [#216](https://github.com/smtg-ai/claude-squad/issues/216) + #51 (18 comentários) · 2025-2026 · usuários | Alta |
| 2 | **TUI lenta: segundos por tecla** — causa-raiz achada pela comunidade (subprocess síncrono no event loop) com **PR #249 parado** | "hitting ? took about 5 seconds" | [#215](https://github.com/smtg-ai/claude-squad/issues/215) + [PR #249](https://github.com/smtg-ai/claude-squad/pull/249) · set/2025-fev/2026 · usuários | Alta |
| 3 | **YOLO mode não funcionava** (-y e o Claude ainda pedia permissão); sessões novas nascem SEM os MCP servers configurados; falhas ao criar sessão pós-instalação limpa | "Create 2nd session -> List MCPs and there are none configured" | #151 + [#143](https://github.com/smtg-ai/claude-squad/issues/143) + #132 + #96 · 2025 · usuários | Alta |
| 4 | **Pedidos estruturais anos sem resposta** — multi-repo (aberto desde abr/2025), caminho de worktree configurável, agente por sessão, Windows (refactor proposto sem merge) | issues #56, #121, #84, #248 | 2025-2026 · usuários | Alta |

**Sinal:** o incumbente de 8k stars parado é a evidência mais forte de que a categoria pune manutenção fraca — usuários chegam, batem nos mesmos bugs e vão embora (pro herdr/AoE). AGPL afasta uso corporativo.

**Lição pro maestro-console:** captura de conteúdo de pane é frágil por natureza (o projeto já sabe: memória TUI injection via PTY) — ter fallback e verificação host-side; e PR de comunidade parado é anti-padrão que mata confiança.

### 34. agent-of-empires (AoE)

**Identidade:** gerenciador Rust TUI+Web de agentes (Claude/OpenCode) com acesso mobile · MIT, **2.737 stars em ~6 meses**, site agent-of-empires.com · Windows só via WSL2 (admitido) · status: MUITO ativo, mantenedor corrige rápido (bug grave em <24h) · varrido em 2026-07-03. (Jogo Age of Empires filtrado.)

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Recursos nativos do Claude Code degradam sob o tmux do AoE** — clique de mouse não posiciona cursor, Shift+Enter sem multi-linha, colar imagem não funciona (ABERTA, 13 comentários) | "Normally in Claude Code, if I click somewhere in a text box, the cursor goes there. However, under AoE it doesn't" | [#2316](https://github.com/agent-of-empires/agent-of-empires/issues/2316) · 2026-06-22 · usuário | Alta |
| 2 | **Corrompeu o servidor tmux INTEIRO do usuário** — aviso público no HN ("WARNING!"); corrigido em <24h | "it corrupted my entire tmux session, leaving me to have to recreate the entire thing" | [HN](https://news.ycombinator.com/item?id=46588905) (118 pts) · 2026-01-13 · @chrisvalleybay | Alta |
| 3 | **Detach/attach matava o agente**; Ctrl-Z congela sem recuperação (sem job control) | "whenever I use Ctrl+b d to jump out… it gets killed" | [#435](https://github.com/agent-of-empires/agent-of-empires/issues/435) + [#145](https://github.com/agent-of-empires/agent-of-empires/issues/145) · jan-mar/2026 · usuários | Alta |
| 4 | **Regressões por ritmo acelerado** — copy/scroll do terminal web quebrou na v1.8.0 (wterm→xterm.js); OpenCode "funcionava antes"; input j/k invoca modal errado sob velocidade | "basic copy and scroll stopped working the way they did before" | [#1499](https://github.com/agent-of-empires/agent-of-empires/issues/1499) + #486 + #1926 · mar-jun/2026 · usuários | Alta |
| 5 | **Mobile (caso de uso anunciado) medíocre** — "tmux + claude code definitivamente não é ótimo no celular"; single-player (sem colaboração); conceitos confusos na doc (Project vs Group, atalho documentado que dá erro) | "tmux + claude code is definitely not great on mobile" | HN 2026-01-13 + [#2462](https://github.com/agent-of-empires/agent-of-empires/issues/2462) · usuários | Alta |
| 6 | **Ceticismo de valor** — "é só um wrapper de tmux?"; crítica à categoria: "muito desenvolvimento contornando a experiência ruim de um CLI terrivelmente lento" | "So this is a tmux wrapper? Does it provide any additional goodies other than a UI?" | HN · 2026-01-13 · usuários | Alta |

**Sinal:** o mais dinâmico da categoria CLI — mas herda TODAS as dores estruturais do tmux, e o ritmo de features gera regressões visíveis.

**Lição pro maestro-console:** construir SOBRE tmux economiza emulação mas importa as dores dele (mouse/imagem/multi-linha) — o VTE nativo do maestro-console evita isso; regressão por ritmo é o outro extremo do abandono: suite de regressão no fluxo de release.

# Parte 4 — Gigantes adjacentes (recorte multi-agente)

> Recorte obrigatório aplicado: só dores de multi-agente/orquestração — dores gerais dos produtos ficaram fora. Máx. 10 por produto.

### 35. Claude for Mac / Cowork (Anthropic)

**Identidade:** app desktop oficial da Anthropic, modo Cowork p/ tarefas agênticas · launch HN 2026-01-12 com 1.298 pts/565 comentários + thread paralela de segurança ("Claude Cowork exfiltrates files", 870 pts) · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Perda silenciosa de sessões — ADMITIDA como "limitação atual do Cowork"** — histórico e metadados somem da noite pro dia; suporte reclassificou de bug pra design; padrão cross-plataforma (Windows: ~1967 sessões truncadas; Linux: 31 destruídas por auto-update) | "all session chat histories and project metadata have disappeared overnight… Support later corrected this to a 'current Cowork limitation'" | [claude-code#45076](https://github.com/anthropics/claude-code/issues/45076) · 2026-04-08 · usuário + suporte | Alta |
| 2 | **App precisa ficar aberto e a máquina acordada** — tarefa (mesmo agendada) morre se fechar/dormir; quebra o "delegar e sair" | "If you close the Claude desktop application or your computer goes to sleep while a task is running, the task will stop" | docs Anthropic (via 2 fontes secundárias) · 2026-07 | Média |
| 3 | **Cowork queima cota muito mais rápido** — cada task = subagentes + tool calls; até Max 20x (US$200/mês) bate no teto | vendor admite: "Working on tasks with Cowork consumes more of your usage allocation than chatting" | help center (via secundário) · 2026-07 | Média |
| 4 | **Sem memória entre sessões** — re-explicar contexto a cada sessão nova (admitida) | "Cowork does not retain memory between sessions" | docs (via secundário) · 2026-07 | Média |
| 5 | **Sessões travadas** — "Starting session" por DIAS; "Working through…" 42+ min em prompt simples; fechada como "not planned" | "Cowork has been stuck on 'Starting session' for days" | [#45531](https://github.com/anthropics/claude-code/issues/45531) · 2026-04-09 · usuário | Alta |

**Sinal de mercado:** demanda enorme (HN 1.298 pts) e insatisfação suficiente pra gerar alternativas open-source no launch (OpenWork 231 pts, BrowserOS 88 pts); preocupação forte de segurança com agentes autônomos locais.

**Lição pro maestro-console:** o líder do mercado NÃO garante persistência de sessão — a captura de sessão/kill-and-resume do maestro-console ataca a dor nº 1 admitida do Cowork; e "app fechado = tudo para" valida o desenho de ciclo de vida por captura.

### 36. Codex App (OpenAI)

**Identidade:** "command center for agents" da OpenAI (desktop + cloud execution + Skills) · launch HN 2026-02-02 com 805 pts/638 comentários; 1M instalações Mac na 1ª semana · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Instâncias paralelas corrompem estado compartilhado (~/.codex/)** — session restore cruzado entre instâncias → contexto corrompido, falhas não-determinísticas em batch | "the instances interfere with each other by triggering session restore from shared state" | [codex#11435](https://github.com/openai/codex/issues/11435) · 2026-02-11 · usuário | Alta |
| 2 | **Tarefas longas em paralelo derrubam sessões** — output truncado, falhas silenciosas, terminais fechando sozinhos; sequencial funciona, paralelo falha | "Silent failures with no explicit error" | [#10887](https://github.com/openai/codex/issues/10887) (ABERTA) · 2026-02-06 · usuário | Alta |
| 3 | **Computer Use = um único desktop compartilhado** — sem isolamento por agente (janela/perfil/foco), sem arbitragem de recursos; N agentes não coexistem | "No per-agent desktop session, window lease, or browser profile isolation" | [#20852](https://github.com/openai/codex/issues/20852) (ABERTA, sem resposta) · 2026-05-03 · usuário | Alta |
| 4 | **Crash da thread orquestradora perde os subagentes juntos** — trabalho em estados incompletos difíceis de limpar | "it will lose their state as well… work being left in incomplete states" | [#26884](https://github.com/openai/codex/issues/26884) e relacionadas · 2026 · usuários | Média |
| 5 | **Consumo absurdo sob paralelismo** — relato de 70 GB de RAM, todos os cores travados, races criando worktrees em paralelo "e o agente não faz ideia de que falhou"; desktop inutilizável em threads longas (memória + churn de log) | "Codex (desktop) was eating up 70GB of RAM… The agent has no idea that it failed" | HN @jorl17 · 2026-06-22 + [#21134](https://github.com/openai/codex/issues/21134) | Média |
| 6 | **Review é o gargalo humano** — além de ~3-5 sessões, agentes extras empilham trabalho não-revisado ("mais lento que rodar menos") | Simon Willison: "the natural bottleneck on all of this is how fast I can review the results" | blogs de review · 2026-04 | Média |

**Sinal de mercado:** a OpenAI posiciona o app explicitamente como command center de agentes — as dores de orquestração são centrais, não periféricas; e o ecossistema de ferramentas "por cima" (Nimbalyst, Verdent…) existe porque a lacuna de coordenação/observabilidade de fleet é sentida. **Convergência com o Cowork:** os dois desktops oficiais sofrem das mesmas dores de fleet — estabilidade sob paralelismo, RAM/CPU, perda de estado, review humano.

**Lição pro maestro-console:** estado por nó ISOLADO (nunca compartilhado tipo ~/.codex) é requisito de paralelismo; e a dor do "review como gargalo" sugere que a UX do canvas deve facilitar revisar o trabalho de cada nó, não só rodá-los.

### 37. Cursor (recorte: background/parallel agents)

**Identidade:** IDE AI líder; background agents (cloud) + parallel agents (Cursor 2.0) · closed-source, fórum oficial como canal · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Background agents inutilizáveis por bug** ("something went wrong" — sem acessar/criar; staff confirmou) + falha de start por container Docker ("de às vezes pra sempre falha") | "Yes - Cursor is unusable" | [fórum](https://forum.cursor.com/t/cursor-background-agents-completely-unusable/154103) · 2026-03-09 + [thread](https://forum.cursor.com/t/background-agents-fail-to-start/108599) · 2025 · usuários + staff | Alta |
| 2 | **Agentes SOMEM do dashboard após merge do PR** — histórico irrecuperável, impossível continuar | "no sign of it in my Agent dashboard" | [fórum](https://forum.cursor.com/t/background-agents-disappearing/115269) · 2025-07 · 5 usuários | Alta |
| 3 | **Sessão "normal" vira conta de US$600+** — sem estimativa, sem alerta de runaway; US$40/hora sem saber o porquê; custo multiplica linear com N agentes (+20% MAX mode) | "a single normal-looking session can turn into a $600+ bill… pricing has become too opaque to use responsibly" | [fórum](https://forum.cursor.com/t/cursor-needs-better-pricing-guardrails-when-one-session-can-cost-600/156172) · 2026-03-29 + [thread](https://forum.cursor.com/t/best-practices-for-bringing-down-background-agent-costs/103186) · usuários | Alta |
| 4 | **Agentes travam até intervenção manual** ("Move to background" na mão); lê mal a saída do terminal | "consistently just stuck until I take action" | [fórum](https://forum.cursor.com/t/cursor-background-agent-hung-and-slow/112776) · 2025-07 · 4 usuários | Alta |
| 5 | **Parallel agents (2.0): propósito confuso + interferência entre agentes** — "Apply" de um confunde o outro rodando; sem coordenação (mesmo prompt pra todos), merges sobrepostos | "I don't get it - how is this useful?"; "Apply… interfered/confused model2 still running" | [fórum](https://forum.cursor.com/t/cursor-2-0-x-what-are-parallel-agents-doing/138911) · 2025-10/11 · usuários | Alta |

**Sinal:** poderoso na promessa, imaturo e arriscado na prática — confiabilidade e transparência de custo são os calcanhares. **Lição:** guardrail de custo ANTES de escalar agentes (o budget cap do maestro-console é exatamente isso) e histórico de agente nunca pode sumir.

### 38. Windsurf (recorte: Cascade paralelo / Devin / Command Center)

**Identidade:** IDE AI (Cognition); orquestração real só na 2.0 (~out-nov/2025, Agent Command Center + Devin) · feedback multi-agente ainda escasso (recurso novo) — maioria editorial · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Corrida de edições entre Cascades paralelos — a 2ª falha** (ADMITIDA na doc; contorno oficial: worktrees) | "If two Cascades edit the same file at the same time, the edits can race, and sometimes the second edit will fail" | [docs](https://docs.devin.ai/desktop/cascade/cascade) · jul/2026 · vendor | Alta |
| 2 | **Subagentes confiáveis só ~40% das vezes** em tarefas multi-step; delegado pula validações que o Cascade pegaria | "maybe 40% of the time on multi-step tasks" | [review Danilchenko](https://www.danilchenko.dev/posts/devin-desktop-review/) · 2026 · editorial | Média |
| 3 | **"Orchestration theater"** — Kanban de agentes só vale se os agentes são confiáveis; senão é "um jeito mais bonito de assistir estados de falha"; fricção pra dev solo (abre no board, não no editor) | "a Kanban board of agents can become a prettier way to watch failure states" | reviews · 2026 · editorial | Média |
| 4 | **Custo runaway sem teto** — overage a taxa bruta de API com uso "ilimitado" | via guias de pricing (snippets) | 2026 · editorial | Baixa |

**Sinal:** a comunidade não trata o Windsurf como referência em multi-agente. **Lição:** o conceito "orchestration theater" é o anti-padrão a evitar — painel bonito não substitui delegação verificável.

### 39. Cline (recorte: subagents/orquestração)

**Identidade:** agente open-source p/ VS Code · subagents nascentes e explicitamente experimentais · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **Subagent em loop infinito queimando tokens** — relia os mesmos arquivos recursivamente, sem mecanismo de parada | "the sub-agent entered an infinite loop, continuously deducting tokens" | [cline#9673](https://github.com/cline/cline/issues/9673) · 2026-03-05 · usuário | Alta |
| 2 | **Subagents DESABILITADOS no VS Code pelo próprio criador** — acesso a ferramentas e aprovação "precisam de mais escrutínio" | PR "fix(vscode): disable subagents": "the current behavior around subagent tool access and approval handling needs more scrutiny" | [PR #11847](https://github.com/cline/cline/pull/11847) · 2026-06-25 · mantenedor | Alta |
| 3 | **Subagents quebravam no limite da janela de contexto** (erros não-recuperáveis em tarefa longa) | [PR #9637](https://github.com/cline/cline/pull/9637) | 2026-03-02 · mantenedor | Média |
| 4 | **"Não é orquestração real"** — subagents read-only (não escrevem, sem MCP/browser/aninhamento); sessão fecha e o resultado completo se perde; sem controle do agente-mãe sobre subagente travado | "the agent cannot instruct the subagent to write its previous full research to a file or further orchestrate" | [docs](https://docs.cline.bot/features/subagents) + editorial + HN · 2026 | Média |

**Sinal:** a força da Cline segue no agente único; multi-agente é flanco fraco — a ponto de ser desligado por segurança. **Lição:** o episódio valida a cautela do maestro-console com autoridade/aprovação na delegação (ADR-21/22): até projeto de 50k+ stars recuou por não ter isso resolvido.

### 40. Warp Oz (recorte multi-agente)

**Identidade:** plataforma cloud de agentes da Warp (oz.warp.dev + app) · Free 4 agentes concorrentes / Build US$18 (20) / Max US$180 (40) · varrido em 2026-07-03.

| # | Dor | Evidência (citação + tradução) | Fonte · data · autor | Confiança |
|---|-----|-------------------------------|---------------------|-----------|
| 1 | **⚠️ Falha de isolamento entre sessões (confused deputy)** — agente da sessão A enumerou processos, achou um `pythonw` da sessão B e começou a investigar/planejar mudanças no projeto da OUTRA sessão sem autorização | "The agent should not proactively begin modifying or investigating processes it identifies as belonging to a separate Warp session" | [Warp#11577](https://github.com/warpdotdev/Warp/issues/11577) · 2026-05-22 · usuário | Alta |
| 2 | **Cloud agent não inicia** — falha de VM/imagem Docker ("pod phase = Failed"); "impede o uso diário" | "warp-agent status stopped exit code 2" | [#8772](https://github.com/warpdotdev/Warp/issues/8772) · 2026-02-26 · usuário | Alta |
| 3 | **Custo/tempo divergem entre o painel web e o app pro MESMO run** — observabilidade de custo inconsistente entre superfícies | "different credit usage and run times for the same agent run… values should be consistent" | [#10052](https://github.com/warpdotdev/warp/issues/10052) · 2026-05-04 · usuário | Alta |
| 4 | Extensão SSH do agente crasha (SIGILL) em CPU sem AVX; sinal fraco de crédito zerado cortando agente no meio da tarefa sem buffer | títulos de issues #12630, #9588 | 2026 · usuários | Média/Baixa |

**Sinal:** issues de Oz no tracker são majoritariamente de agente único; HN com engajamento baixíssimo (1-3 pts) — a orquestração cloud da Warp ainda não gerou comunidade. **Lição:** a dor nº 1 é literalmente o confused deputy que o maestro-console já blindou (ADR-21/22) — isolamento por sessão é diferencial auditável; e métrica de custo deve ser UMA fonte de verdade (o ledger host-side garante isso).

### 41. JetBrains Air (recorte multi-agente)

**Identidade:** ADE multi-agente da JetBrains (isolamento worktree/Docker, base Fleet) · preview: macOS primeiro, Linux jun/2026, Windows ainda não; exige API keys próprias · varrido em 2026-07-03. ⚠️ Quase todas as dores vêm de UM review forte (baeseokjae, 2026-04-30) — confiança "Alta" = citação lida, não consenso multi-fonte. (cosmtrek/air de Go descartado.)

| # | Dor | Evidência (citação + tradução) | Fonte · data | Confiança |
|---|-----|-------------------------------|--------------|-----------|
| 1 | **3+ agentes em arquivos relacionados = conflitos de merge que o Air expõe mas NÃO resolve** | "Three or more agents touching related files can still produce merge conflicts that Air surfaces but doesn't automatically resolve" | [review baeseokjae](https://baeseokjae.github.io/posts/jetbrains-air-review-2026/) · 2026-04-30 | Alta |
| 2 | **O isolamento que evita conflito também bloqueia transferência de contexto** — mudanças do Agente A não informam o Agente B (trade-off central da arquitetura isolada); sofre em monorepo com contexto compartilhado | "the isolation that prevents conflicts also prevents knowledge transfer" | mesma fonte | Alta |
| 3 | **Spin-up de 10-30s por agente** (worktree + Docker) anula o paralelismo em tarefa pequena; modo worktree exige reinstalar dependências a cada task | "offsets parallelism gains on small, fast tasks" | mesma fonte + doc oficial | Alta |
| 4 | **Custo = N × queima de tokens** — refactor de 20 min com 3 agentes custa 3x | "it costs 20 minutes × 3 agents' token burn" | mesma fonte | Alta |
| 5 | **~1 GB de RAM "sem fazer nada"** (herdado do Fleet) — agrava com N containers; sem integração com issue tracker; ceticismo pelo track record JetBrains (Fleet morto após 4 anos de preview, Space, Aqua) | "doing nothing takes up 1GB of RAM" | [rywalker](https://rywalker.com/research/air-jetbrains) + blogs · 2026 | Média |

**Sinal:** engajamento bom no HN (74 pts) mas crítica dominante é de prioridade ("consertem os IDEs"), não de orquestração; confiança minada pelo histórico de produtos descontinuados. **Lição:** o dilema isolamento × contexto compartilhado é O problema arquitetural do nicho — o modelo do Maestri (notas compartilhadas explícitas) e o de cabos/envelopes do maestro-console são respostas; formalizar isso como decisão consciente de design.

# Dores recorrentes do nicho (transversal)

Padrões que apareceram em **3+ produtos independentes** — o mapa de minas e oportunidades da categoria inteira, cruzado com as dores do Maestri (relatório-irmão). É esta seção que o agente deve reaproveitar primeiro.

| # | Padrão | Onde apareceu (exemplos) | Oportunidade/risco pro maestro-console |
|---|--------|--------------------------|----------------------------------------|
| P1 | **Bypass de permissões como default** — `--dangerously-skip-permissions` hardcoded ou forçado silenciosamente | superset (#2419), dmux (#7), cmux (update silencioso #3547); Cline DESLIGOU subagents por não ter isso resolvido | Invariante já do projeto (autoridade host-side, ADR-21/22): nunca bypassar; transformar em argumento de venda auditável |
| P2 | **Sessão morre com o app / não persiste** — quit/crash/restart = trabalho em voo perdido | Clave (#19), cmux (vendor admite), Cowork ("limitação atual" admitida!), Nimbalyst (#65), RunMaestro (Auto Run não sobrevive a restart), Codex (crash da thread-mãe leva subagentes), Aizen (#21), Maestri (A1) | **A feature atual (captura de sessão/kill-and-resume) ataca a dor mais universal do nicho** — nem os apps oficiais dos labs resolvem |
| P3 | **Custo de N agentes imprevisível, sem guardrails** — sessão de US$600, quota drenada em 2 min, N× tokens, métricas divergentes | Cursor, mux (#2489), Verdent (Trustpilot), Conductor (4x), Cowork (quota), JetBrains Air (N×), Windsurf (sem teto), Warp Oz (#10052), Maestri (E1) | Medidor de custo por nó + budget cap (v0.54-0.55) é resposta direta; falta só UX de pausa graciosa/retomada ao esgotar (lição RunMaestro #235) |
| P4 | **Delegação/orquestração não confiável** — o recurso central da categoria falha silenciosamente | Maestri (~70%, C1-C2), Dorothy (#45), RunMaestro (stall silencioso, commit sem aprovação), Windsurf (~40%), Cline (loop infinito), Cursor (sem coordenação), Maestro OSS (status errado), ai-maestro (cross-talk), shogun (executa em vez de delegar) | Delegação VERIFICÁVEL pelo host (envelope/ledger) é o diferencial técnico nº 1 possível; nenhum player entrega hoje |
| P5 | **Plataforma: macOS-only domina; Linux é a maior demanda reprimida** — a issue mais quente do produto mais estrelado é "Linux support?" (194 reações) | cmux (#330), superset (#405 aberto 7 meses), Conductor, Maestri, supacode, Aizen, vibecraft, Dorothy…; Windows = 2ª classe até nos cross-platform (Emdash, Jean, dmux, RunMaestro) | O maestro-console é Linux/ARM nativo — o único do levantamento; é o moat, confirmado pela 3ª fonte independente |
| P6 | **Ambiente do shell / detecção de CLI quebrada** — PATH sem nvm/direnv, keychain em sessão background, "Claude not found" com Claude instalado | mux (#797), Aizen (#22), herdr (#966), Crystal (#9, dor fundacional), supacode (#504), Jean (#387), Dorothy (pnpm), Cursor/Emdash ("not installed" com CLI instalado) | Lançar agentes via shell real do usuário (como o projeto já faz via VTE) elimina a classe inteira; testar com nvm/pyenv/direnv |
| P7 | **RAM/CPU explodem sob paralelismo** — 20 GB (Maestri), 70 GB (cmux, Codex), 2 GB base (superset), CPU 100% permanente (Nimbalyst), 1 GB idle (Air) | praticamente todos os desktop apps | Frugalidade é feature de 1ª classe no CM4; unload de nó + medição contínua = posicionamento único ("rode 5 agentes em 4 GB") |
| P8 | **Fidelidade de terminal/TTY é onde os apps morrem** — render corrompido, CJK/dead keys/teclado não-US, paste de imagem, links, scroll | herdr (cauda VT), Emdash, superset, parallel-code, Maestro OSS, AoE (mouse/multi-linha), dmux (CJK), supacode (dead keys!), Maestri (A3/A7) | VTE maduro do GTK evita reimplementação; dead keys/acentos = teste obrigatório pro público PT-BR |
| P9 | **Isolamento vazando** — agente age fora do escopo: outra sessão (Warp Oz!), branch main (Crystal #152), broadcast entre projetos (ai-maestro #241), estado compartilhado (~/.codex #11435) | 4+ produtos, incluindo os labs | O invariante de escopo por cabo/conexão explícita do maestro-console responde; nunca estado global compartilhado entre nós |
| P10 | **Fricções de worktree** — .env/node_modules não vêm (bootstrap manual), órfãos em disco, exigência de remote/GitHub até em projeto local | Conductor, Emdash, Air, superset, Polyscope, Constellagent (3ª vez a dor do `git fetch origin` incondicional) | Se adotar worktrees por nó: bootstrap de untracked + limpeza garantida + funcionar 100% offline/sem remote |
| P11 | **Status/observabilidade de agente não confiável** — "working" quando espera input, "idle" trabalhando, agentes que somem do painel, stall silencioso de horas | Maestro OSS (#204/#176), RunMaestro (#338/#235), Cursor (dashboards), Clave (#18), herdr (raso), Maestri (A5) | O monitor de atividade (v0.53) é aposta certa; a barra é baixa — status CONFIÁVEL já diferencia |
| P12 | **Review humano é o gargalo final** — além de ~3-5 agentes, trabalho empilha não-revisado ("mais lento que rodar menos") | Conductor, Codex (Willison), Cursor, Windsurf ("orchestration theater") | UX de revisão por nó no canvas (diff/resultado acessível) vale mais que suportar mais nós |
| P13 | **Churn brutal — a categoria pune abandono e recompensa cadência** — pioneiro morto (Crystal), líderes estagnados (claude-squad 8k stars parado), hypes abandonados (Maestro OSS, Constellagent, Aizen, Ami, tmux-ide) | ~1/3 dos 29 produtos varridos está morto, estagnado ou esfriando | Cadência sustentável + repo público ativo = confiança; e validar padrões dos concorrentes ANTES de copiar (podem estar mortos amanhã) |

**Leitura executiva:** o nicho inteiro (29 produtos, dos clones de 10 stars aos apps oficiais de Anthropic/OpenAI) converge nas mesmas ~13 dores — e as três mais universais (sessão que não persiste, custo sem guardrail, delegação não-verificável) são exatamente as que o maestro-console já tem em desenvolvimento ou resolvidas por arquitetura. O moat de plataforma (Linux/ARM) é confirmado por demanda medida (194 reações na issue de Linux do cmux). Nenhum concorrente combina: canvas espacial + Linux + open source + custo transparente + delegação verificável.

---

## Metodologia e Limitações (consolidado)

**Método:** prompt-template desenhado e criticado adversarialmente pelo Fable (verificação de identidade obrigatória contra homônimos; tetos de esforço P/M/G; recorte multi-agente pros gigantes; regras anti-fabricação). Execução em 13 lotes / 3 ondas de agentes paralelos (ondas 1-2 no modelo da sessão; onda 3 em Opus por decisão do usuário), 29 produtos + 12 homônimos descartados e registrados. Fontes primárias priorizadas: GitHub issues lidas via `gh` CLI (a maioria dos produtos tem tracker público — diferente do Maestri), fóruns oficiais, HN via API Algolia, reviews/diretórios, docs de vendor (limitações admitidas). Cada dor: citação original + tradução + URL + data + autor + tipo de fonte + confiança.

**Limitações transversais:**
- **Reddit ficou praticamente cego em TODOS os lotes** — o crawler é bloqueado pelo Reddit e `site:reddit.com` retornou vazio sistematicamente. r/cursor, r/ClaudeAI, r/warp etc. provavelmente têm densidade alta de dores não capturadas. É a maior lacuna do relatório; uma varredura manual de Reddit fecharia o buraco.
- **X/Twitter** sem busca nativa (só indexado); **Discords** dos produtos (canal primário de feedback de vários) fechados a indexação.
- Threads gigantes de HN (500-600 comentários nos launches de Cowork/Codex) foram mineradas por busca, não lidas na íntegra.
- Produtos com centenas de issues (cmux 2.4k, supacode 560, Nimbalyst 315): lidas as top ~30 por engajamento — cauda longa fora.
- Snapshot de 2026-07-03 num nicho de churn extremo: status "ativo/estagnado" envelhece em semanas.
- JetBrains Air depende de 1 review forte; Verdent/Trustpilot veio de snippets convergentes (403 no fetch direto); confianças marcadas caso a caso.

**Status da pesquisa: CONCLUÍDA em 2026-07-03.** Relatório-irmão: `docs/22-pesquisa-dores-maestri.md` (dores do Maestri).
