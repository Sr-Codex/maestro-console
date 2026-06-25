# Pesquisa: comunicação interativa agente↔agente "estilo Maestri" (cabos que conversam)

> Data: 2026-06-25 (UTC) · PT-BR
> Origem: deep-research multi-fonte com verificação adversarial (104 agentes · 22 fontes · 24 claims confirmados, 1 refutado).
> Objetivo: implementar, de forma confiável e leve no uConsole, o "coração interativo" do Maestri — ligar um cabo entre dois terminais e os agentes conversarem (output de A → input de B, turn-taking), ao vivo.
> Relação com o código: hoje o handoff por cabo é **mediado** (envelope JSON / `controller.delegate`), não terminal-a-terminal. Esta pesquisa avalia como adicionar o modo interativo.

---

## Descoberta-chave: como o Maestri realmente funciona

O marketing diz "PTY puro, sem middleware, um agente digita no terminal do outro". A **doc oficial revela o mecanismo real**: ao conectar dois terminais, o Maestri **instala uma "Agent Skill" em cada um** — um **comando de nível CLI** (agnóstico de agente) que o agente chama via Bash:

```
maestri ask "Claude Code #6" "<prompt>"
→ Answer from Agent #6: ...
```

O app hospedeiro **monitora os terminais NÃO focados**, detecta o fim do turno por **quiescência** de output e **roteia a resposta de volta** ao agente original.

> ⚠️ A claim "PTY puro sem middleware, um agente literalmente digita no outro" foi **REFUTADA** na verificação — existe uma camada interna de gestão de contexto; "no middleware" = sem serviço/API externo, não ausência de orquestração. (Maestri é closed-source Swift/macOS; tudo vem de docs do fornecedor + reviews.)

**Implicação:** isso é quase o que o maestro console já tem (handoff mediado). A diferença é a **embalagem** — expor o handoff como uma **skill que o agente chama de dentro do terminal ao vivo**.

---

## Arquitetura recomendada

**Manter o handoff mediado (robusto, determinístico) como base e ADICIONAR um modo interativo por cima** — não substituir.

| Variante | Como | Confiabilidade | Risco |
|---|---|---|---|
| **(a) Skill → motor mediado** ⭐ começar aqui | cabo instala `maestro ask <nó> "<prompt>"` no workspace do agente; ele chama ao vivo; o host roda o destino pelo motor existente (headless/envelope + bwrap) e devolve a resposta no terminal de A | **Alta** (reusa headless ~100% + sandbox) | Baixo |
| **(b) Skill → terminal vivo do B** (Maestri "puro") | injeta o prompt no VTE do B, vigia o terminal do B e raspa a resposta | Média (depende de detecção de tela) | Alto (echoing, scraping) |

Razão: a confiabilidade do próprio Maestri sem intervenção é **~70%** (agent-finder.co) — por isso **não substituir** o caminho JSON robusto.

---

## Stack durável (verificada em fonte ao vivo)

| Componente | Status | Uso |
|---|---|---|
| **Python + GTK4 / VTE-3.91** | ✅ **0.84.0 (mar/2026), ativamente mantida** (cadência mensal, GitLab upstream) | canvas/terminal — manter |
| **tmux** (`send-keys`, `capture-pane`, `monitor-silence`, hooks) | ✅ estável, leve em ARM | espinha de automação p/ a variante (b) |
| **pexpect / ptyprocess** | mantido, releases espaçados (último 4.9.0, nov/2023) | fallback Python p/ controlar PTY (expect com lista de regex + timeout) |
| **pyte** | referência usual de emulação de tela | limpar saída TUI (reconstruir a tela; ansiparser cobre só SGR/CUP/ED/EL) |

**Detecção de fim-de-turno = combinar sinais** (nenhum isolado é robusto): **sentinela explícita + estado-da-TUI ("esc to interrupt") + quiescência temporal**. (O spike da Fase 0 já achou que estado-da-TUI ≈ 100%, vs quiescência pura 83–93% — combinar resolve a fragilidade.)

---

## Riscos sérios + guardrails OBRIGATÓRIOS

- **Echoing** (arXiv:2511.09710, Salesforce): em conversas autônomas A↔B, o agente **abandona o papel e vira eco do interlocutor**. Taxa **5%–70%** (≈70% Gemini-2.5-Flash; ≈5% GPT-5), começa por volta do **turno ~7-8**; mitigável a ~9% com resposta estruturada. → **limite de turnos**, **refresh de identidade a cada ~3 turnos**.
- **Loop A↔B** e **eco de terminal/prompt-echo** (nível de stream, distinto do echoing semântico) → anti-loop + limpeza de tela (pyte) + não realimentar o próprio eco.
- **Custo de tokens** → política de corte por orçamento.
- **Segurança** → manter o **sandbox bwrap** no modo interativo; tratar o output do outro agente como entrada não-confiável (risco de injeção).

---

## Ressalvas

1. Maestri é closed-source — afirmações vêm de marketing + reviews, sem verificação por código.
2. Quiescência (tmux `monitor-silence` ou "N s sem bytes") é heurística → falsos positivos em tool calls longos/streaming lento; o `TIMEOUT` do pexpect dispara por relógio, não por bytes.
3. O limiar de quiescência precisa de **calibração empírica no próprio uConsole** (CM4, 3.7 GB).
4. `tmux-bridge` (maxeonyx) **não** é modelo A↔B — é human-in-the-loop; não serve de receita.

## Perguntas em aberto

1. Limiar de quiescência ideal para CLIs de IA no CM4 (calibrar no hardware).
2. Claude/Codex expõem sentinela/estado-de-TUI estável e parseável como sinal primário? (inspecionar o output real de cada CLI).
3. tmux dirige confiavelmente um VTE embutido no canvas, ou os agentes do modo interativo deveriam rodar em sessões tmux separadas que o VTE só attacha/exibe?
4. Política ótima de corte (turnos / refresh) por orçamento de tokens e por modelo.

## Fontes principais

- Maestri docs (connections, terminals) — themaestri.app · reviews: agent-finder.co, zenn.dev, producthunt.com
- tmux — wiki Advanced-Use, releases
- pexpect/ptyprocess — readthedocs, GitHub · pyte/ansiparser — PyPI
- VTE — gitlab.gnome.org/GNOME/vte/-/tags (0.84.0)
- Echoing — arXiv:2511.09710 (Salesforce AI Research)
