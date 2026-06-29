# Maestri — especificação de comportamento + auditoria do clone

> ⚠️ **HISTÓRICO (2026-06-26) — anterior a v0.34-37.** A auditoria do clone aqui não reflete
> física do cabo, editor de nota in-place nem minimapa (entregues depois). Estado real:
> [`STATUS.md`](STATUS.md). A *especificação do Maestri* (parte de cima) segue válida como referência.

> Data: 2026-06-26 · PT-BR · Fonte: docs oficiais `themaestri.app/en/docs` (terminals, connections, índice) consultadas ao vivo + `docs/01-pesquisa-maestri.md`.
> Objetivo: lista de REGRAS DE COMPORTAMENTO do Maestri para auditar o clone (maestro console). Legenda: ✅ temos · 🟡 parcial/diverge · ❌ falta.

## Terminais & Agentes
| # | Regra do Maestri (fonte: doc oficial) | Status no clone |
|---|---|---|
| T1 | Criar: ferramenta **Terminal** → **clicar-e-arrastar** desenha o terminal no tamanho desejado; modal escolhe o agente; pode dar **nome e ícone**. | 🟡 criamos no início + menu ➕ (shell/agente); **sem** desenhar-por-arrasto, **sem** nome/ícone |
| T2 | Roda **"a full interactive shell"** onde o agente trabalha. | ✅ (corrigido: IA roda dentro do shell) |
| T3 | **Ao sair da IA → vira shell normal** (terminal é um shell de verdade). | ✅ (corrigido agora) |
| T4 | Fechar: **⌘W** fecha e remove do canvas. | 🟡 temos botão ✕; **sem** atalho de teclado |
| T5 | Foco: **Shift+A** pula pro próximo terminal que precisa de atenção; **segurar tecla + número** foca o terminal N (até 9). | ❌ (temos paleta Ctrl-P "ir para"; sem Shift+A nem hold-número) |
| T6 | **Attention dot** vermelho no header quando o agente precisa de você + notificações do sistema. | ✅ temos atenção (⚠N) + notify-send (V11) |
| T7 | Seleção/cópia de texto, scrollback, redimensionar, mover. | ✅ VTE dá seleção/scroll; movemos e **redimensionamos** (⤡) |

## Conexões / Cabos
| # | Regra do Maestri | Status no clone |
|---|---|---|
| C1 | Conectar: selecionar terminal + ferramenta **Connection** (ou tecla **L**) → clicar no 2º nó. Cabo animado tipo corda. | 🟡 temos 🔌/**Ctrl+Shift+L** + 2 cliques (sem física de corda) |
| C2 | **Desconectar:** abrir o popover de conexões (clicar no badge) → botão **×**. | ❌→🟡 **corrigido agora**: toggle clicando nos 2 (em qualquer ordem). Popover × = futuro |
| C3 | Conexão **bidirecional** entre agentes. | ✅ (edge_allowed nos dois sentidos) |
| C4 | **Múltiplos** cabos por terminal. | ✅ |
| C5 | **Agent Skill** auto-carrega ("any agent that starts inside Maestri will know how this works"); senão, "Use maestri to ask [Agent]". | ✅ instalamos a skill no CLAUDE.md/AGENTS.md (`maestro-ask`) |
| C6 | Fim de turno: monitora terminais **não-focados**; quando o receptor termina, devolve a resposta. Selecionar o receptor = controle manual, para de monitorar. | 🟡 nosso modo é **mediado/síncrono** (delegate headless) — não depende de "deixar sem foco" (sem esse footgun) |

## Demais funcionalidades (índice oficial)
| Feature | Maestri | Clone |
|---|---|---|
| The Canvas (2D infinito, pan/zoom) | ✅ | ✅ (GTK4, zoom real, resize de cards) |
| Batuta Search (paleta) | ✅ | ✅ (Ctrl-P) |
| Notes (markdown, agent-edita) | ✅ | ✅ (+agent-to-note) |
| Floors (ambientes isolados) | ✅ | ✅ (git worktree) |
| Routines (prompts agendados) | ✅ | ✅ |
| Roles | ✅ | ✅ (badges/papéis) |
| Backup/Restore, Temas de terminal | ✅ | ✅ |
| Workspaces (multi-projeto, layout salvo) | ✅ | 🟡 dir por workspace; **sem** troca de projeto na UI |
| **File Tree** (árvore de arquivos no canvas) | ✅ | ❌ |
| **Maestro Mode** | ✅ | ❌ |
| **Portals** (browser embutido) | ✅ | ❌ (pesado, Fase 6) |
| **Ombro** (IA local) | ✅ | ❌ (pesado, Fase 6) |
| **Remote SSH** | ✅ | 🟡 (Web UI tem guia SSH; canvas nativo não) |
| Diff/git viewer | ✅ | ❌ |

## Gaps priorizados (o que falta, por valor/esforço)
1. ✅ **feito** — terminal vira shell ao sair da IA (T3).
2. ✅ **feito agora** — desconectar cabo sem depender da ordem (C2).
3. 🟢 baixo esforço: **⌘W/atalho fechar** (T4); ⚠️ Ctrl+W conflita com shell — avaliar.
4. 🟡 médio: **File Tree** no canvas; **multi-workspace** na UI; foco por **Shift+A / hold-número** (T5).
5. 🔴 pesado (Fase 6): Portals, Ombro, Maestro Mode, diff/git.

> Mecanismo: nosso handoff é **mediado** (ADR-11), não a quiescência-em-terminal-não-focado do Maestri — por escolha de robustez (o spike achou quiescência frágil). Isso elimina o footgun "não selecione o receptor" do Maestri.
