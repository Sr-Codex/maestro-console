# Pesquisa Profunda — Maestri (themaestri.app)

> Relatório de deep research (verificação adversarial) — 2026-06-21
> 99 subagentes · 17 fontes · 85 afirmações extraídas · 25 verificadas · 21 confirmadas · 4 refutadas
> Objetivo: reunir o necessário para construir um clone funcional rodando no **ClockworkPi uConsole** (Kali Linux, ARM Cortex-A72 aarch64, 3.7 GB RAM sem swap, tela 1280×720, tmux, Node 24 / Python 3.13).

---

## Resumo executivo

**Maestri** é um **app nativo de macOS** (Swift/SwiftUI/AppKit, motor de canvas próprio, emulador SwiftTerm — sem Electron, sem nuvem, sem telemetria). Ele **não é um agente de IA**: é uma **camada de orquestração** — um *canvas infinito* onde cada terminal é um **nó arrastável** rodando um shell interativo completo, com agentes de codificação (Claude Code, Codex, OpenCode) que **o próprio usuário pré-instala**.

O mecanismo central é **orquestração via PTY**: ao ligar dois terminais com uma linha, o Maestri injeta em cada um uma **"Maestri Agent Skill"** que opera **no nível da CLI** (por isso é *agent-agnostic* — qualquer CLI fala com qualquer CLI). Um agente envia prompt e recebe resposta do outro; o Maestri **monitora apenas terminais NÃO focados** para detectar quando o receptor terminou e rotear a resposta de volta.

Como o Maestri é **macOS-only** (a razão de existir um clone Linux/ARM), as alternativas open-source viáveis no uConsole reproduzem o conceito via **tmux + PTY**. Os dois candidatos diretamente portáveis: **tmux-bridge-mcp** (Node, leve) e **CAO/cli-agent-orchestrator da AWS** (Apache-2.0, arquitetura supervisor-worker completa).

---

## 1. Arquitetura do Maestri `confiança: alta`

- Camada de orquestração / canvas infinito que **envolve agentes externos** — não é um agente em si.
- Cada **terminal é um nó visual** rodando um shell interativo completo; é onde o trabalho realmente acontece.
- Edições de arquivo caem no **disco do projeto**; o canvas é a camada de **direção**, não onde os arquivos vivem.

> Docs: *"Maestri is not an AI agent itself. It's the canvas and orchestration layer that sits around your agents."*

Fontes: themaestri.app/docs/intro, /docs/terminals, /docs/canvas, agent-finder.co/reviews/maestri

## 2. Comunicação agente-a-agente (via PTY) `confiança: alta`

- Usuário arrasta uma **linha** entre dois terminais → os agentes colaboram diretamente (delegar, perguntar, passar trabalho).
- Funciona "**como se o agente digitasse na outra janela**" — opera no nível do terminal.
- ⚠️ A versão **forte** "sem API/middleware, um agente literalmente digita no terminal do outro" foi **refutada (0-2)** quando ancorada só na homepage. A formulação confirmada é mais cautelosa: *PTY orchestration pipes*.
- Review independente mediu **~70% de handoffs automáticos** sem intervenção manual (ou seja: a detecção de conclusão é **heurística e frágil**).

Fontes: producthunt.com/products/maestri, themaestri.app/en, agent-finder.co

## 3. A "Maestri Agent Skill" `confiança: alta`

- Ao conectar dois terminais, o Maestri **instala uma skill em cada um**, dando ao agente o poder de **enviar prompts e receber respostas** de qualquer outro conectado.
- Opera **no nível da CLI** → *agent-agnostic* (Claude Code ↔ Codex ↔ OpenCode, qualquer combinação).

> Docs/connections (verbatim): *"When two terminals are connected, Maestri installs a Maestri Agent Skill in each one. This skill gives agents the ability to send prompts to, and receive responses from, any other connected agent."*

🚨 **CAVEAT crítico para o clone:** a **estrutura/protocolo exato** da skill (formato da mensagem, delimitação, como o sinal de "resposta pronta" é codificado) **NÃO é publicada**. É o detalhe técnico mais *load-bearing* e está em aberto.

Fontes: themaestri.app/docs/connections, /docs/intro

## 4. Detecção de fim de resposta `confiança: alta`

- O Maestri **só monitora terminais que NÃO estão focados** (sem borda tracejada).
- Se você **seleciona** o terminal receptor, o Maestri assume controle manual e **para de monitorar** → o agente que espera nunca recebe a resposta.
- Quando o receptor termina de gerar, o Maestri **detecta e envia a resposta de volta**.

➡️ **Replicável:** detecção de **idle/quiescência** no PTY (estabilização do output).

Fonte: themaestri.app/docs/connections

## 5. Papéis de agente (Lead / Coder / Reviewer / Tester) `confiança: alta`

- Implementados iniciando cada agente em um **subdiretório do projeto** com seu próprio **CLAUDE.md / AGENTS.md**, mais um sidecar **role.json** portátil (nome, cor do badge, prompt).
- Papéis são **customizáveis**, não presets fixos.
- ➡️ **Trivial de replicar em Linux** (subdiretórios + arquivos de instrução).

Fonte: themaestri.app/docs/terminals

## 6. Plataforma e limitações `confiança: alta`

- **macOS-only** (macOS 15.2+/Apple Silicon), Swift/SwiftUI/AppKit, motor de canvas próprio, emulador **SwiftTerm** (escolhido sobre Ghostty porque libghostty não estava finalizada).
- **Sem Electron, sem web views, zero nuvem, sem telemetria** (armazenamento local JSON/Markdown). IA local "Ombro" usa Apple Foundation Models on-device.
- Pricing: tier **Pro** existe (uso em até 2 Macs); detalhes free vs pro não totalmente capturados.

➡️ **Implicação para o clone:** toda a pilha é **Apple-locked** (Swift, Metal, Foundation Models) — por isso não há build cross-platform e um clone Linux/ARM precisa **reconstruir do zero** a UI e o substrato de PTY.

Fontes: themaestri.app/docs/intro, producthunt.com, agent-finder.co

---

## 7. Alternativas open-source (comparativo)

| Projeto | Stack | Comunicação inter-agente | Licença | Linux/ARM | Peso | Veredito p/ clone |
|---|---|---|---|---|---|---|
| **tmux-bridge-mcp** (howardpen9) | Node 18+ / MCP sobre stdio | `capture-pane`/`send-keys`, padrão **read-act-read** | open-source | ✅ (Node+tmux) | 🟢 leve | ⭐ **Candidato mais direto** |
| **CAO / cli-agent-orchestrator** (awslabs) | Python / MCP | Sessões tmux isoladas + PTY real; **Handoff / Assign / Send Message**; supervisor-worker | Apache-2.0 | ✅ | 🟡 médio (runtime Python) | ⭐ **Arquitetura mais completa** |
| **cmux** (manaflow-ai) | Swift+AppKit / libghostty | — (paralelismo, não wiring) | GPL-3.0 | ❌ macOS-only | — | Referência de UX só |
| **mato** (mr-kelly) | Rust (88%) | — (organização/monitoramento; **sem** mensageria) | open-source | ✅ | 🟢 leve | Possível camada de UI |

**Detalhes principais:**

- **tmux-bridge-mcp** `confiança: alta` — *"lets AI agents (Claude Code, Gemini CLI, Codex, Kimi CLI) communicate with each other through tmux panes"*, *"It calls tmux directly (capture-pane, send-keys, list-panes)"*, *"no external dependencies beyond tmux itself"*. Padrão **read-act-read**: `tmux_read` → `tmux_type/message/keys` → `tmux_read` (verifica). ARM-viável (inferência sólida: Node+tmux nativos em aarch64).
- **CAO** `confiança: alta` — *"every agent runs in its own tmux session. Clean context separation, real PTY access, humans can `tmux attach` to steer at any time."* 3 modos: **Handoff** (transfere controle e espera), **Assign** (spawn assíncrono com callback), **Send Message** (entrega em inbox quando o terminal está idle). Suporta ~10 CLIs.
- **cmux** — terminal nativo macOS (GPL-3.0), 22.3k stars. Valida "terminal como host agent-agnostic", mas é **paralelismo**, não wiring automático. Existe fork `omd0/cmux-linux`.
- **mato** — workspace Rust (Desks/Tabs). **Não** conecta agentes para conversarem. Leve; poderia ser camada de organização + backend tmux-bridge.

---

## 8. Padrões técnicos & viabilidade no uConsole `confiança: alta`

Todas as soluções (Maestri, tmux-bridge-mcp, CAO) usam o **mesmo substrato**: **PTY/tmux como transporte** e **leitura de output como sinal de conclusão**.

- **`tmux send-keys` (escrever) + `capture-pane` (ler), padrão read-act-read** → abordagem dominante, leve, **zero dependências compiladas** → ideal para ARM / 3.7 GB sem swap.
  - ✅ tmux já está no uConsole; baixíssimo RAM.
  - ❌ `send-keys` é frágil: timing, prompts multilinha, sequências de controle, detecção de idle imperfeita (~70%).
- **MCP sobre stdio** → protocolo estruturado (handoff/assign/inbox), mais robusto, **mas pesa um runtime extra**.
- **Detecção de "fim de resposta"** → por **quiescência/idle** do painel não-focado (estabilização do `capture-pane`), como o Maestri faz.

**Recomendação técnica:** usar **tmux como substrato de PTY** (não reimplementar PTY), padrão **read-act-read** para confiabilidade, e **detecção de idle por estabilização** do capture-pane.

---

## ⚠️ Caveats (força das fontes)

1. Tudo sobre o Maestri vem de **docs do próprio fabricante** + Product Hunt → fonte primária, mas **auto-descritiva**. App é **proprietário/fechado** → mecanismo PTY interno e, criticamente, o **formato/protocolo exato da Agent Skill NÃO são verificáveis nem publicados**.
2. "Zero telemetria/zero nuvem" é **auto-reportado**, sem auditoria independente.
3. "ARM-viável" para tmux-bridge-mcp e CAO é **inferência de engenharia** (correta, mas não afirmada literalmente pelos repos).
4. Dados de pricing/versão são de ~abr–jun 2026; listas de CLIs mudam rápido (CAO passou de 2 → ~10 CLIs).

## ❓ Perguntas em aberto

1. **Qual o formato/protocolo EXATO da "Maestri Agent Skill"** — como a mensagem é estruturada/delimitada no PTY e como o sinal de "resposta concluída" é codificado (heurística de idle? marcador sentinela? parsing do prompt do shell)? *Detalhe mais load-bearing para o clone.*
2. Como lidar com prompts interativos, spinners TUI e o estado "pensando vs. pronto" para CLIs diferentes (Claude Code vs Codex vs OpenCode)? (handoff ~70% sugere heurística frágil)
3. Limites exatos free vs Pro do Maestri (nº de terminais/conexões).
4. **Benchmark real de RAM no uConsole**: canvas web local é viável em 3.7 GB sem swap rodando 3-4 agentes CLI, ou TUI pura (Rust/Go sobre tmux) é obrigatória?

---

## 🎯 Recomendações concretas para o clone no uConsole

1. **Não reinventar o PTY**: usar **tmux** como substrato de transporte e isolamento (já instalado, leve, ARM-nativo).
2. **Reusar/estudar os dois projetos-âncora**: começar do **tmux-bridge-mcp** (mais simples/leve) e roubar a **arquitetura de modos do CAO** (Handoff/Assign/Send Message + supervisor-worker).
3. **Comunicação**: padrão **read-act-read** + **detecção de idle por estabilização** do `capture-pane` (replicar o "monitorar terminais não-focados" do Maestri).
4. **Papéis**: subdiretórios com `CLAUDE.md`/`AGENTS.md` + sidecar `role.json` — exatamente como o Maestri, trivial no Linux.
5. **Interface**: dado 3.7 GB sem swap, favorecer **TUI/headless sobre tmux** e evitar canvas gráfico pesado / runtimes macOS-locked. (Decisão final do usuário, pós-benchmark — ver pergunta em aberto #4.)
6. **Stack a validar**: Rust ou Go (leves) para o orquestrador/TUI; Node só se reusar tmux-bridge-mcp direto; Python só se seguir o caminho CAO.

---

### Fontes primárias
- themaestri.app — /docs/intro, /docs/connections, /docs/terminals, /docs/canvas, /en
- producthunt.com/products/maestri · agent-finder.co/reviews/maestri
- github.com/howardpen9/tmux-bridge-mcp
- github.com/awslabs/cli-agent-orchestrator · aws.amazon.com/blogs/opensource/introducing-cli-agent-orchestrator
- cmux.com · github.com/manaflow-ai/cmux · github.com/mr-kelly/mato
