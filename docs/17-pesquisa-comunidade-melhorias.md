# Pesquisa de comunidade — dicas de melhoria de usuários (2026-07-02)

> Data: 2026-07-02 · PT-BR · **Duas pesquisas paralelas independentes**: Opus 4.8 (agente
> Anthropic) + Codex/gpt-5.5 (CLI, web search). Foco pedido pelo usuário: **minerar comunidades
> atrás de dicas/pedidos/reclamações CONCRETAS que USUÁRIOS reais deram** para gestores VISUAIS
> de agentes de IA estilo canvas/Maestri — não estudar frameworks (isso foi o `docs/16`).
> Complementa `docs/08` (dores do Maestri) e `docs/16` (frameworks). **Nada aqui foi implementado.**

## Por que dois modelos (e o que cada um pegou)

Usar dois modelos cobriu **fontes diferentes** — foi o maior ganho do método:
- **Opus 4.8** garimpou reviews com nome+data (**Setapp, Product Hunt, agent-finder**) → pegou as
  **reclamações reais** do Maestri.
- **Codex** garimpou **GitHub Discussions/Issues** de Vibe Kanban e Claude Squad → pegou
  **feature-requests concretos** (username+data). Foi honesto: não conseguiu verificar queixas
  públicas do Maestri com autor+data (Product Hunt/Setapp/Reddit não renderizaram no fetch dele),
  então usou a "Wall of Love" (curada, desejos implícitos) pro lado Maestri — que o Opus cobriu.

## O insight central (os dois convergiram sozinhos)

O padrão recorrente na comunidade **não é "mais agentes" — é "menos babá" (*less babysitting*)**:
saber **quem precisa de você**, não perder follow-ups, recuperar sessões após crash, manter
contexto comum entre agentes, e revisar mudanças paralelas sem quebrar o fluxo. É essa a dor
central de um gestor visual de agentes — e é barata e local de atacar (casa com GTK4+VTE + cabos
+ Team Templates + Maestro mode, e respeita RAM/CPU/tela do CM4).

---

## 1. Dicas de usuários sobre o Maestri (fonte: Opus 4.8)

Fontes: [Setapp reviews](https://setapp.com/apps/maestri/customer-reviews) (94%, 36 avaliações),
[Product Hunt](https://www.producthunt.com/products/maestri), [changelog oficial](https://www.themaestri.app/en/changelog),
[agent-finder](https://agent-finder.co/reviews/maestri). Todas acessadas 2026-07-02.

- **Congelamento de UI sob uso prolongado** — "terminais trabalham, mas não consigo arrastar e os
  botões ficam sem resposta" (Abu Nowshad, PH); "botões com lag" (John B, Setapp 31/mai).
  **Reclamação nº1 de estabilidade.** *Lição: a thread de UI não pode ser bloqueada pelo I/O dos PTYs.*
- **Teclado para de responder no meio da sessão, com perda de trabalho** (Brandan, Setapp 15/mai).
- **RAM: 20GB com vários Claude Code** (Paul Chambers, Setapp 18/mai). Maestri respondeu na v0.29
  com **"unload terminals and portals"** (descarregar nó sem fechar). *Crítico pro CM4.*
- **Handoff inconsistente (~70%)** — às vezes cria sub-agente em vez de delegar; conectar agente a
  shell "não executa comandos como esperado" (Abu Nowshad; agent-finder).
- **Remote agents rodando num Raspberry Pi** (Brice Le Blevennec, Setapp 11/mai) — **a bandeira
  ARM/uConsole é um pedido REAL da comunidade**, não só uma restrição nossa.
- Menores: Nerd Font no terminal (Brian Morin, 22/mai); scroll horizontal quebrado com mouse
  (Abdul Habeeb, 4/mai); rotinas/cron "enterradas em menus" (IVG, 10/mai); falta clareza de
  janela de contexto com N agentes (Takahito Yoneda, PH).
- Recursos que o Maestri **já entregou por demanda** (valem observar): paleta Cmd+P "Batuta"
  (v0.29), **notificação nativa "agente precisa de atenção"** (v0.26), grupos com header
  compartilhado (v0.26), roteamento de cabo ao redor dos nós (v0.30), temas iTerm2 (v0.26).

## 2. Pedidos em ferramentas similares (fonte: Codex — GitHub Discussions/Issues)

### Atenção, navegação e logs
- **Scrollbar + "go to present"** ao alternar workspaces (bmajkut, Vibe Kanban, 01/03,
  [disc #2992](https://github.com/BloopAI/vibe-kanban/discussions/2992)).
- **Copiar logs grandes + ver subagentes + perguntas que não aparecem** (JoshuaDietz, VK, 02/06,
  [disc #3424](https://github.com/BloopAI/vibe-kanban/discussions/3424)).
- **Modo compacto acima de ~10 sessões** (henricook, Claude Squad, 22/05,
  [issue #296](https://github.com/smtg-ai/claude-squad/issues/296)) — direto pro 1280×720.

### Fila de prompts e controle de execução
- **Fila FIFO real de follow-ups** (empilhar instruções sem interromper, reordenar, cancelar) —
  ARCJ137442 (VK, 27/02, [disc #2953](https://github.com/BloopAI/vibe-kanban/discussions/2953)).
- **Estados travados precisam de recuperação visível** (fila presa, stop exige reload, "running"
  na sessão errada) — JoshuaDietz (VK #3424). *Separar estado do PTY, do agente e do worktree.*
- **Máquina de estado por tarefa** (todo/running/review/done/blocked) — thread ORCH via Claude
  Squad ([disc #228](https://github.com/smtg-ai/claude-squad/discussions/228)).

### Contexto, planejamento e handoff
- **Chat de planejamento ANTES de criar worktree** (josephschmitt, VK 18/02, [disc #2813](https://github.com/BloopAI/vibe-kanban/discussions/2813)).
- **Briefing persistente por worktree** injetado automaticamente em novas sessões (JoshuaDietz, VK #3424).
- **Consciência read-only entre workspaces irmãos** (listar irmãos, ler status/diff sem escrever) —
  jakobpirk (VK 31/03, [disc #3308](https://github.com/BloopAI/vibe-kanban/discussions/3308)).
- **Nomes gerados** melhores que o início da mensagem, p/ sessões/branches (JoshuaDietz, VK #3424).

### Worktrees / ambiente / Git
- **Setup hook pós-worktree** (copiar `.env`, portas isoladas, Docker namespace) — rohansx
  (Claude Squad 05/03, [issue #260](https://github.com/smtg-ai/claude-squad/issues/260)).
- **Reabrir worktree/sessão após crash** (timmfin 29/07, andrewaddo 06/08, Claude Squad
  [disc #190](https://github.com/smtg-ai/claude-squad/discussions/190)).
- **Mesclar N worktrees numa branch de teste** antes de push (CodyBontecou, Claude Squad
  [disc #101](https://github.com/smtg-ai/claude-squad/discussions/101)).
- **Diff desde o último feedback** (não só "tudo no worktree") — JoshuaDietz (VK #3424).

### Portais / preview
- **URL do browser panel configurável** por processo (JoshuaDietz, VK #3424); Maestri evoluiu
  portais p/ user-agent/viewport/resize (changelog 0.30.3/0.30.7, 20-23/06).

---

## 3. Síntese cruzada — o que os DOIS acharam (sinal forte) e o ranking

**🔴 Convergência (os dois, independentes):**
1. **Status por nó + "precisa de você" + pular pro próximo** — **#1 nos DOIS.** Estados visuais
   (rodando/esperando-input/ocioso/erro/precisa-revisão/concluído) + atalho global. Pedido mais
   universal da categoria. *(Ver `docs/18` — grande parte JÁ existe no código.)*
2. **"Unload" de nó** (matar o PTY, manter o nó) — dor de RAM, decisiva no CM4 (Maestri v0.29).
3. **Recuperação/reattach + arquivar em vez de fechar** — nó/worktree órfão após crash.
4. **Paleta de comandos** — os dois. *(Já existe no projeto: Ctrl-P.)*
5. **Custo/tokens por nó (lean)** — converge com o **F1** (`docs/15`, elevado pelo Fable). Agora
   **triplo-confirmado** (docs/16 + Fable + esta pesquisa).

**🟡 Joias de fonte única (Codex/GitHub):** fila FIFO de follow-ups; briefing persistente por
grupo; modo compacto 1280×720; consciência read-only entre nós irmãos; setup hooks de worktree.

**Descartado como caro/fora de contexto (os dois sinalizaram):** dashboard web/mobile completo,
DevTools embutido pesado, orquestração 100% autônoma 24/7, integrações SaaS de organização/time.

**Já entregue no projeto (não confundir com pendência):** paleta Ctrl-P; worktree por agente
(Floors); grupos; minimapa; notas; monitorar atividade (dot+som); estados de nó com glyph/cor.

## Encaminhamento (decisão do usuário, 2026-07-02)
- **#1 (estado por nó / "precisa de você")** → promovido a plano: `docs/18-plano-estado-por-no.md`.
- **Restante** → capturado no backlog (`docs/15`) como ideias a entender melhor antes de puxar.
