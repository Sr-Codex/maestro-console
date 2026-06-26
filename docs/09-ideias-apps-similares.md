# Ideias de apps parecidos — catálogo para analisar e aplicar

> Data: 2026-06-26 · PT-BR · Objetivo: NÃO copiar o Maestri — colher ideias concretas de
> vários apps da categoria (orquestradores de agente, terminais de IA, editores de nó) e
> escolher o que aplicar no maestro console (Linux/ARM/GTK4, 1280×720, dev solo, engine
> headless+bwrap já existente). Fontes ao vivo no fim.

## Apps estudados (o que cada um faz de bom)
- **Conductor** (mac): cada agente tem workspace isolado (git worktree), **diff viewer forte + fluxo de PR**, suporta claude e codex.
- **Vibe Kanban** (open-source): cada workspace = branch + terminal + dev server; **10+ agentes** (claude/codex/gemini). *(empresa fechou abr/2026; segue community.)*
- **Claude Squad** (open-source, Go, TUI): tmux + **worktree por agente**, você tabula entre eles.
- **Nimbalyst / Antigravity / Windsurf**: **kanban de sessões** por fase (backlog→planning→implementing→done); **"Manager View"** que despacha N agentes paralelos; filosofia **"less typing, more directing"**.
- **Warp** (terminal de IA): **blocos** (comando+saída = unidade navegável/dobrável/compartilhável), **paleta de comandos**, **Workflows/Notebooks** (snippets salvos/compartilhados).
- **Zellij** (multiplexer): **barra de status que ENSINA** (mostra as teclas disponíveis em tempo real), **floating panes** (scratchpad sobreposto), layouts declarativos (KDL).
- **Editores de nó** (React Flow, NodeCanvas, ComfyUI): **minimapa**, **snapping/grid**, **grupos**, **comentários**, undo/redo, copy/paste, multi-seleção, busca de nós.
- **Dashboards de agente** (AgentOps & cia): **timeline de atividade**, **pause/redirect por passo** (steering), status proativo ("fazendo X"), **time-travel** do raciocínio.
- **Paleta de comandos** (VS Code, Linear, Raycast, Superhuman): Ctrl/Cmd-K + **fuzzy search** + descoberta de atalhos = "estado de fluxo".

---

## Catálogo de ideias (agrupado) — para você marcar o que quer

### A. Gestão de agentes / fluxo de trabalho
| # | Ideia (de quem) | Por que é boa | Como cai no nosso app | Fit/Esforço |
|---|---|---|---|---|
| A1 | **Diff/review por agente + commit assistido** (Conductor, Nimbalyst) | pedido recorrente; fechar o ciclo "agente mexeu → eu reviso → comita" sem sair do app | painel de diff do workspace do nó (git) + botão "comitar"; já temos workspaces isolados | 🟡 médio |
| A2 | **Kanban/estado das sessões** (Nimbalyst) | ver o workstream inteiro (o que está planejando/rodando/pronto) | uma faixa/coluna por estado dos nós; reusa nossos estados (idle/busy/blocked/done) | 🟡 médio |
| A3 | **"Manager View" — despachar N agentes** (Antigravity) | escala real: 1 objetivo → vários agentes paralelos | um comando "espalhar tarefa" cria N nós a partir de um preset | 🟡 médio |
| A4 | **Worktree por nó** (Claude Squad, Conductor) | isolamento real de git, cada agente em sua branch | evoluir nossos workspaces p/ git worktree opcional | 🟠 maior |

### B. Terminal / interação (a alma do app)
| # | Ideia (de quem) | Por que é boa | Como cai no nosso app | Fit/Esforço |
|---|---|---|---|---|
| B1 | **Blocos de comando** (Warp) | cada comando+saída vira unidade: rolar, dobrar, **copiar**, referenciar | marcar prompts no VTE → dobrar/copiar saída do agente | 🟠 maior (VTE) |
| B2 | **Barra que ENSINA atalhos** (Zellij) | descoberta sem decorar; mata a dor "não sei os atalhos" | rodapé contextual mostrando as teclas do modo atual (conectar, focar…) | 🟢 baixo ⭐ |
| B3 | **Floating pane / scratchpad** (Zellij) | terminal rápido sobreposto sem bagunçar o canvas | um nó-overlay temporário (Ctrl+atalho) que aparece/some | 🟡 médio |
| B4 | **Workflows/Notebooks — snippets salvos** (Warp) | reusar comandos/prompts campeões; conhecimento não se perde | biblioteca de prompts/comandos por workspace (já temos routines — expandir) | 🟢 baixo |

### C. Canvas / nós (nossa identidade visual)
| # | Ideia (de quem) | Por que é boa | Como cai no nosso app | Fit/Esforço |
|---|---|---|---|---|
| C1 | **Minimapa** (React Flow, NodeCanvas) | navegar canvas grande sem se perder | cairo no overlay; clicar move o viewport | 🟡 médio |
| C2 | **Grupos / "áreas"** (NodeCanvas) | organizar agentes por projeto/tema (retângulo rotulado) | caixa de grupo arrastável atrás dos nós | 🟡 médio |
| C3 | **Snapping + grid** (editores de nó) | alinhamento limpo, menos bagunça | snap ao soltar nó/redimensionar; grid de pontos (era a UI-3) | 🟢 baixo |
| C4 | **Comentários/post-its no canvas** (NodeCanvas) | anotar o "porquê" perto dos agentes | já temos NOTAS — reforçar (cor/fixar) | 🟢 baixo |
| C5 | **Cabos curvos tipo corda** (Maestri) | leitura de direção/fluxo muito melhor | bezier no cairo (era a UI-2) | 🟢 baixo |

### D. Velocidade / teclado
| # | Ideia (de quem) | Por que é boa | Como cai no nosso app | Fit/Esforço |
|---|---|---|---|---|
| D1 | **Paleta de comandos com fuzzy** (VS Code/Linear/Raycast) | "universal search" de ações = fluxo; já temos Ctrl-P básico | turbinar: fuzzy match + ações + atalhos visíveis + recentes | 🟢 baixo ⭐ |

### E. Observabilidade / controle (sessões longas)
| # | Ideia (de quem) | Por que é boa | Como cai no nosso app | Fit/Esforço |
|---|---|---|---|---|
| E1 | **Steering por passo: pause/redirect/nudge** (AgentOps & cia) | controlar sessão longa sem matar tudo; injetar correção | pausar/cutucar um nó via o barramento de ask que já temos | 🟡 médio ⭐ |
| E2 | **Timeline de atividade** (dashboards de agente) | ver o que cada agente fez/está fazendo, sem ler scrollback | linha do tempo por nó (eventos: iniciou, perguntou, terminou) | 🟡 médio |
| E3 | **Status proativo** ("fazendo X") (Agent UX 2026) | confiança: você sabe o que ele está fazendo agora | rótulo de atividade no card além do dot de estado | 🟢 baixo |

> Nota: o **medidor de custo/tokens** (F1, em pausa no PR #9) também aparece como item de
> dashboard ("token usage") — mas você não viu valor agora, então fica reservado, não some.

## Fontes (consulta 2026-06-26)
- Multi-agente: [Nimbalyst — best multi-agent tools](https://nimbalyst.com/blog/best-multi-agent-coding-tools-2026/) · [Augment — orchestrators](https://www.augmentcode.com/tools/open-source-agent-orchestrators) · [Vibe Kanban](https://github.com/BloopAI/vibe-kanban)
- Warp: [warp.dev/terminal](https://www.warp.dev/terminal) · [guia 2026](https://aiproductivity.ai/guides/warp-terminal-guide/)
- Visual/diff/kanban: [Nimbalyst vs Cursor vs Windsurf](https://nimbalyst.com/blog/nimbalyst-vs-cursor-vs-windsurf/) · [workspaces além do terminal](https://nimbalyst.com/blog/best-ai-coding-workspaces-beyond-the-terminal/)
- Editores de nó: [React Flow](https://reactflow.dev/) · [NodeCanvas](https://nodecanvas.paradoxnotion.com/)
- Zellij: [github zellij](https://github.com/zellij-org/zellij) · [about](https://zellij.dev/about/)
- Observabilidade/steering: [Agent UX 2026](https://fuselabcreative.com/ui-design-for-ai-agents/) · [aimultiple — observability](https://aimultiple.com/agentic-monitoring)
- Paleta: [UX Patterns — command palette](https://uxpatterns.dev/patterns/advanced/command-palette) · [Superhuman](https://blog.superhuman.com/how-to-build-a-remarkable-command-palette/)
