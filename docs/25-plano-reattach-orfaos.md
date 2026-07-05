# Plano — Reattach / arquivar nós órfãos pós-crash

> Puxado do backlog (`docs/15`, item da pesquisa de comunidade `docs/17`) em 2026-07-05,
> promovido pela análise de dores `docs/24` §3 (item 5, Nível 2). Completa o ciclo de vida
> aberto pelo **unload** (v0.56, `docs/21` + ADR-23): unload = descarregar de propósito;
> reattach = recuperar o que ficou órfão de um **crash** (não-de-propósito). Reaproveita quase
> toda a infra do unload. **Este doc é o plano — não há código ainda; aguarda validação do
> usuário antes de virar stories.**
>
> **v2 (2026-07-05) — CORRIGIDO pela revisão adversarial do Fable** (4 furos, ver §10). Resumo do
> que mudou vs v1: (1) adicionado handler `SIGTERM/SIGHUP → quit` no R1 — sem ele todo logout/
> desligamento viraria falso "crash"; (2) **cortado** o módulo `liveness.py`/marcador `pid:starttime`
> e o spike de die-with-parent (over-engineering — `sandbox.py` já prova que o filho morre no crash);
> (3) órfão ganha **flag `orphan` própria e persistida** (não reusa `unloaded`, não fica só em
> memória) — senão crash-órfão vira indistinguível de descarregado-de-propósito; (4) R4 (worktree)
> explicitamente FORA do 1º PR. O núcleo ficou **mais simples** que o rascunho.

## 1. Objetivo (a dor)

Hoje o "abre igual fechou" restaura o **layout** do canvas, mas se o app **caiu** (crash, kill,
bateria do uConsole) em vez de fechar limpo, um nó que tinha agente vivo reabre com o **processo
morto** por baixo e o trabalho em voo fica sem caminho de volta. É a dor **P2** da pesquisa
(`docs/23`), a mais universal do nicho, confirmada em concorrentes:
- **Clave #19** — "quit/crash = perde todas as sessões" ("the most painful failure mode").
- **Emdash** — "zombie processes and orphaned sessions" admitido no troubleshooting.
- **superset #2863 / Polyscope #171** — "workspace deletion leaves orphaned worktree directories".
- **Cowork (Anthropic)** — perda silenciosa de sessão admitida como "limitação atual".

**Meta:** ao reabrir após um crash, detectar nós/dirs órfãos e oferecer, por nó, **Reanexar**
(retomar via `--resume`, reusando a máquina do unload) · **Novo agente** (spawn limpo) ·
**Arquivar** (fechar o nó preservando o workspace). Sem falso positivo, sem bloquear o startup,
sem apagar trabalho não-commitado.

## 2. O que já existe (NÃO reinventar) — confirmado por leitura de código (mapa 2026-07-05)

- **Captura/retomada de sessão (unload, Bloco A′/C):** `session_capture.newest_session_id(ws)`
  lê o `session_id` do JSONL mais novo em `~/.claude/projects/<slug-do-ws>/` — e o **Claude grava
  o transcript por evento** (ADR-23), então o JSONL de um agente que morreu no crash **já está no
  disco**. Recuperar não exige ter capturado antes: basta reler no boot.
- **Reload resume-aware:** `_reload_node(nid)` (`canvas.py` L3463) faz `--resume` one-shot via
  `_resume_argv` com **fallback explícito** pra spawn limpo se o resume falhar (ADR-23, story C).
- **Nó nasce dormente:** `_make_node_term` (L3430) — nó com flag `node_cfg unloaded=1` **nasce sem
  processo** (`_dead_terminal`). Um órfão pode ser tratado marcando `unloaded=1` no boot → card
  dormente → "Reanexar" = `_reload_node` **inteiro, sem código novo de retomada**.
- **Flag `unloaded`:** limpa no ponto único `_do_respawn` (L3081) e no `_close_node` (L2359).
- **Estado por nó / atenção (v0.52-53):** `_node_state`, `attention_nids`, contador ⚠ clicável,
  realce no minimapa — o canal pra sinalizar "N nós recuperáveis" **sem modal bloqueante**.
- **Workspace por nó:** `_node_ws(nid)` = `<base>/workspaces/<nid>` (dir por-nó; **não** é git
  worktree). Dirs em `<base>/workspaces/*` **sem entrada no `node_roster`** = candidatos a órfão-de-dir.
- **Roster (fonte da verdade dos cards):** `CanvasModel.node_roster()` (chave `canvas_nodes`).
- **Floors (git worktree):** `floors.py` — worktrees **project-global e opt-in**, SEM vínculo por
  nó e SEM limpeza ao fechar nó. Reconciliação de worktree é um bloco à parte (§4-R4), separado do
  workspace-por-nó.
- **Persistência:** `node_cfg` (`nodecfg_{nid}_{key}`) e `ui_state` (`get_ui/set_ui/delete_ui`).

### O GAP CENTRAL (confirmado — não existe hoje)
- **NÃO existe marcador de clean-shutdown.** `on_shutdown` (L7281) só fecha socket/store; não grava
  nada. Não há atexit/pidfile/lock/heartbeat de app.
- **NÃO existe PID persistido.** `term._child_pid`/`_pidfd` são **memória volátil** — somem no crash.
- **Consequência:** com `--die-with-parent` no bwrap, o filho morre junto com o app **tanto no
  fechamento limpo quanto no crash** → "PID sumiu no boot" **não** é sinal de crash por si só. O
  sinal tem que ser **introduzido**. Este é o coração da feature (§4-R1).

## 3. Veredito da pesquisa (fonte + data)

> A pesquisa externa longa caiu 2× por instabilidade de rede; os pontos load-bearing foram
> confirmados por busca direta em fonte primária (abaixo). As primitivas são estáveis (kernel/git),
> não voláteis.

1. **Detectar crash vs clean-shutdown → dirty-flag (sentinela).** Padrão clássico: gravar uma flag
   "sujo" no início e limpá-la no encerramento limpo; se no próximo boot a flag ainda está suja, o
   run anterior crashou. É o mecanismo de *recovery* de bancos/editores. **Decisão:** uma chave
   `ui_state["dirty_run"]` setada no `on_activate` e **limpa no `on_shutdown`** — se no boot já
   estiver setada, houve crash. Simples, 1 chave, sem dependência. Durabilidade OK: o Store é
   SQLite `WAL` + `set_ui` commita (`with conn`), então a flag suja **sobrevive a crash de
   processo**; só power-loss do SO (`synchronous=NORMAL`) arriscaria a última escrita — e esse é
   justamente o crash que queremos pegar.
   - **⚠ Furo achado pelo Fable (correção no R1):** `on_shutdown` do GTK dispara em `quit()`/última
     janela fechada — mas **NÃO** em `SIGTERM` do sistema, logout da sessão X ou desligamento. No
     uConsole o usuário desliga/fecha a tampa/faz logout em vez de clicar no X → cada uma dessas
     deixaria `dirty_run` sujo → **todo boot seguinte marcaria "crash" e degradaria o "abre igual
     fechou"** (nós vivos renasceriam dormentes). **Correção obrigatória:** instalar
     `GLib.unix_signal_add(SIGTERM/SIGHUP → app.quit())` — converte encerramento do sistema/logout
     em shutdown limpo. Sobra só SIGKILL/OOM/power-loss como "sujo" — exatamente o alvo.
2. **~~Validar PID reciclado via `starttime`~~ — CORTADO (Fable).** A v1 propunha um marcador
   `pid:starttime` por nó pra checar se o processo sobreviveu. Mas `maestro/engine/sandbox.py`
   L63-66 usa **`--unshare-pid` + `--die-with-parent`** (bwrap vira PID 1 do namespace; se o app
   morre, a árvore inteira morre) → **no crash do app o filho-agente SEMPRE morre**, nunca há
   sobrevivente a proteger. "Estava trabalhando?" também é derivável sem marcador: o **JSONL no
   disco** (`newest_session_id`) já é a prova de que houve agente rodando. Logo o marcador e o
   spike de die-with-parent são **ouro que não paga** — cortados (menos código na parte mais
   delicada do canvas, alinha com o ADR-23). A referência de `starttime` fica registrada caso
   precise no futuro: [proc_pid_stat(5) — man7](https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html).
3. **Reconciliar git worktree órfão SEM perder trabalho.** `git worktree list --porcelain` (formato
   estável p/ script) lista os worktrees e marca `prunable` os cujo dir sumiu; `git worktree remove`
   **recusa** remover worktree com mudança não-commitada/untracked (exige `--force`); `git worktree
   prune --dry-run` mostra o que removeria sem apagar. Fonte:
   [git-worktree — git-scm](https://git-scm.com/docs/git-worktree), consultado 2026-07-05. **Decisão:**
   nunca `--force`, nunca `prune` automático destrutivo — só **detectar e oferecer**; "Arquivar"
   preserva o dir.
4. **UX de recuperação sem irritar.** Padrão consagrado (VS Code "Restore previous session",
   browsers "restore tabs"): **não bloquear o boot**, **não auto-restaurar algo quebrado**, oferecer
   de forma discreta e reversível. **Decisão:** órfãos entram como nós **dormentes** (nascem sem
   processo, RAM zero) + sinalização no sistema de atenção existente (⚠ N + realce), NUNCA um modal
   no startup. O usuário decide por nó, quando quiser.
5. **`--resume` de transcript truncado (agente morto no meio de uma tool_use).** Risco já conhecido
   e **já endereçado** no unload (ADR-23, story C): `_reload_node` trata `--resume` falho com
   fallback explícito (avisar + spawn limpo). Reusar inteiro; adicionar só o aviso claro ao usuário
   de que a retomada pode ter perdido a última ação em voo.

## 4. Plano cirúrgico (blocos → stories)

**Bloco R1 — fundação: dirty-flag + handler de sinal (o gap do §2). ENXUTO (sem `liveness.py`).**
- `ui_state["dirty_run"]`: setada cedo no `on_activate`; **limpa no `on_shutdown`**.
- **Handler de sinal (correção Fable, §3.1):** `GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,
  signal.SIGTERM, → app.quit())` e idem SIGHUP — para que desligamento/logout do sistema vire
  shutdown limpo e não falso-crash. (SIGKILL/OOM/power-loss não são captáveis — e são exatamente o
  que queremos flagar.)
- **NÃO** há módulo `liveness.py` nem marcador `proc` (cortados, §3.2).
- **Teste:** dirty-flag setada no boot e limpa no quit; simular SIGTERM → quit → flag limpa (não
  vira falso-crash). Gi-free onde der (a lógica de dirty é `Store.set_ui/get_ui/delete_ui` pura).

**Bloco R2 — detecção de órfãos no boot + flag `orphan` própria (reusa dormência do unload).**
- Critério de órfão (derivado, sem marcador de PID): um nó é **órfão-recuperável** sse
  **`dirty_run` estava setada** (crash) **∧** `kind == agent` **∧** **NÃO** estava `unloaded=1` de
  propósito **∧** `newest_session_id(_node_ws(nid))` existe no disco (há transcript pra `--resume`).
- Em `on_activate`, após montar o `roster` e ANTES do loop de `_add_node`: para cada nó que bate o
  critério → **persistir `nodecfg_{nid}_orphan=1`** (flag PRÓPRIA, não `unloaded`) + persistir o
  `session` capturado.
- **Nascer-dormente honra `unloaded` OU `orphan`:** `_make_node_term` passa a checar as duas → o
  órfão nasce sem processo (RAM zero) reusando a máquina do unload, SEM sobrecarregar a semântica de
  `unloaded`.
- **Por que flag própria e persistida** (furo Fable, §4): (a) distingue crash-órfão de
  descarregado-de-propósito — os dois seriam `unloaded=1` e ficariam visualmente iguais; (b) um set
  `_orphans` só em memória **evaporaria** se o usuário fechasse limpo sem agir (no boot seguinte
  `dirty_run` está limpo → detecção não roda → perderia o rótulo). A flag `orphan` no `node_cfg`
  sobrevive a boots até o usuário resolver.
- **Teste:** boot com `dirty_run=1` + nó agent com JSONL no disco e sem `unloaded` → nasce com
  `orphan=1`, dormente; nó `unloaded=1` de propósito → NÃO vira órfão (fica descarregado normal);
  boot limpo (sem `dirty_run`) → nenhum órfão.

**Bloco R3 — UX de recuperação (não-bloqueante) + ações por nó.**
- Sinalização: nós com `orphan=1` entram no sistema de atenção (⚠ N + estado visual "recuperável",
  distinto de "aguardando"/"erro"/"descarregado"; realce no minimapa). Sem modal no startup.
- Cápsula contextual do nó órfão ganha 3 ações (espelha o padrão da pílula/⏏ do unload) — **todas
  limpam `orphan`**: **Reanexar** = `_reload_node(nid)` (já existe, resume-aware, com aviso de
  possível perda da última ação em voo); **Novo agente** = `_do_respawn(nid)` (spawn limpo, descarta
  o transcript órfão); **Arquivar** = `_close_node(nid)` preservando o dir do workspace (não apaga).
- **Nó shell órfão** (sem sessão pra resumir): só **Novo** ou **Arquivar** (Reanexar desabilitado).
  Na prática o critério do R2 (`kind==agent`) já não marca shell como órfão-recuperável.
- **Teste:** cada ação a partir de um nó `orphan=1` faz a transição certa e **limpa a flag**
  (Reanexar→resume; Novo→respawn limpo; Arquivar→sai do roster sem apagar o dir).

**Bloco R4 — reconciliação de worktree/dir órfão. FORA DO 1º PR (decisão Fable).**
- Os dirs `workspaces/*` **não são git worktrees** e os Floors são globais/opt-in/sem vínculo a nó
  → R4 mistura dois concerns fracos e adiciona superfície de git. R1-R3 já entregam o valor central
  (nós órfãos). **R4 vira 2º PR ou volta pro backlog.** Quando/se feito: só **detectar e oferecer**
  (via `git worktree list --porcelain`, marca `prunable`); "Arquivar" preserva; limpeza usa
  `prune --dry-run` e **nunca** `--force` (o git já recusa remover com mudança pendente).

## 5. Decisões abertas (pra validar com o usuário)

1. **App NÃO é single-instance** (`canvas.py` L7192: `Gio.ApplicationFlags.NON_UNIQUE`) — duas
   instâncias PODEM rodar sobre o mesmo `state.db`, e aí o `dirty_run` global colidiria.
   **DECIDIDO (usuário, 2026-07-05): premissa "1 instância por vez", documentada — SEM `flock`.**
   Motivo: o aparelho é handheld com pouca RAM (2 instâncias dobram a RAM, contra o propósito do
   unload); multi-workspace já existe DENTRO de uma instância; e o risco residual é **não-destrutivo**
   (no pior caso, um crash não detectado numa sessão — nunca corrompe/apaga). Se multi-instância
   virar real algum dia, somar um `flock` no lockfile ao lado do `state.db` é barato — fica
   registrado aqui como saída futura.
2. **Nó shell órfão:** resolvido no desenho — o critério do R2 (`kind==agent`) não marca shell como
   recuperável; se um shell precisar de tratamento, é "Arquivar" apenas. Sem ação pendente.
3. ~~Spike die-with-parent~~ — **descartado** (provado por leitura de `sandbox.py`, §3.2).
4. **R4 fora do 1º PR** — decidido (§4-R4).

## 6. Sequência de stories (revisada pelo Fable)
R1 (dirty-flag **enxuto** + handler de sinal) → R2 (detecção via `dirty ∧ agent ∧ ¬unloaded ∧
session-no-disco` + flag `orphan` própria) → R3 (UX de atenção + 3 ações que limpam `orphan`).
**R4 (worktree) fora deste PR.** Acumular numa branch (`feat/reattach-orfaos-pos-crash`), 1 PR pra
feature (como o unload), bump 1× no fim + ADR curto (o dirty-flag/handler de sinal é decisão
arquitetural de ciclo de vida — candidato a ADR-25). Cada story com teste (gi-free onde der; canvas
via `CanvasWindow.__new__` + mock de `_spawn_into`/`installed_agents`, molde de
`test_unload_reload_canvas.py`).

## 7. Fora de escopo (decidido)
- Recuperar **resposta parcial em voo** (a última tool_use que não fechou) — perde-se igual ao
  unload (ADR-23); só avisamos.
- Auto-reanexar sem o humano — contra a UX §3.4 (não auto-restaurar algo possivelmente quebrado).
- Sincronizar/limpar Floors global agressivamente — só detectar/oferecer, e fora do 1º PR (§4-R4).
- Marcador de PID / `liveness.py` / spike die-with-parent — cortados (§3.2).

## 8. Riscos conhecidos (mitigação no desenho)
- **Falso positivo (logout/desligamento vira "crash")** → handler `SIGTERM/SIGHUP → quit` (§3.1);
  este era o furo nº 1 do Fable — sem ele a feature se auto-sabotava.
- **Falso negativo (crash não detectado)** → dirty-flag é o mecanismo canônico; se `on_shutdown` não
  roda (crash real), a flag fica suja = detecta. Durabilidade garantida pelo WAL (§3.1).
- **Confundir crash-órfão com descarregado-de-propósito** → flag `orphan` própria e persistida,
  distinta de `unloaded` (§4-R2).
- **Apagar trabalho** → "Arquivar" nunca apaga; worktree (R4, futuro) só `remove` sem `--force`
  (git recusa com mudança pendente) e `prune --dry-run`.
- **Duas instâncias colidindo no dirty-flag** → guarda de instância `flock` OU premissa "1 instância"
  documentada (§5.1, decisão do usuário).
- **Poluir o boot** → nós órfãos nascem dormentes (RAM zero) + atenção não-bloqueante; zero modal.

## 9. Próximo passo
Validar este plano (v2) com o usuário → virar stories R1..R3 (R4 depois). A fundação (dirty-flag +
handler de sinal + flag `orphan`) provavelmente vira **ADR-25** (decisão de ciclo de vida).

## 10. Revisão adversarial (Fable) — resultado (2026-07-05)
Rodada sobre a v1 do plano; achou **4 correções pontuais, nenhum furo de fundação** (a abordagem
dirty-flag + reuso da máquina do unload foi endossada). Incorporadas todas:
1. **[R1, crítico]** Handler `SIGTERM/SIGHUP → quit` — sem ele todo logout/desligamento no uConsole
   viraria falso-crash e degradaria o "abre igual fechou". → §3.1, §4-R1.
2. **[R1, corte]** Eliminado `liveness.py`/marcador `pid:starttime` e o spike — `sandbox.py`
   (`--unshare-pid --die-with-parent`) já prova que o filho morre no crash; "estava trabalhando" =
   JSONL no disco. Menos código na parte delicada. → §3.2.
3. **[R2, corretude]** Flag `orphan` própria e **persistida** (não reusar `unloaded`, não set em
   memória) — senão crash-órfão vira indistinguível de descarregado-de-propósito e o rótulo evapora
   num boot limpo. → §4-R2.
4. **[escopo]** R4 (worktree) fora do 1º PR; `NON_UNIQUE` confirmado (app não single-instance) →
   guarda de instância vira decisão do usuário. → §4-R4, §5.1.
Resultado: o núcleo ficou **mais simples** que o rascunho (um módulo e um spike a menos) e sem a
colisão semântica.
