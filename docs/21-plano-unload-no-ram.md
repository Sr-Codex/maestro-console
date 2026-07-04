# Plano — "Unload" de nó: descarregar/retomar p/ liberar RAM no CM4

> Data: 2026-07-03 · PT-BR · Origem: `docs/15` item #3 ("Unload de nó", 🧊 puxado pelo usuário) +
> **investigação de ciclo de vida** (`_bmad-output/.../agent-node-lifecycle-investigation.md`) +
> **medição de RAM ao vivo** + **TR revisada pelo Fable (adversarial)** + **spike de runtime
> PROVADO** + **revisão adversarial DO PLANO pelo Fable** (todos 2026-07-03). Protocolo do
> `AGENTS.md`: **analisar → planejar → pesquisar → validar → codar.**
>
> **⚠️ v2 (pós-revisão do plano):** a rota (kill-and-resume) está provada, mas a **mecânica de
> sessão** foi corrigida — **CAPTURA da sessão pelo workspace do nó**, NÃO injeção de `--session-id`
> fixo (que quebraria o restart e colidiria com o medidor F1). Ver §3.6 e §4.

## 1. Objetivo (a dor)
- **RAM é a dor decisiva no CM4.** Medido ao vivo: aparelho de **3.7 GB**, ~200–370 MB livres; os
  processos `claude`/`codex` somam **~1.460 MB (~40% da RAM)**; `zram` de 3 GB já ~50% usado. Um
  `claude` vai de ~38 MB a **~447 MB** (dos quais **~323 MB privados** → recuperáveis ao matar).
- **Precedente:** o Maestri implementou unload na v0.29. **Meta:** descarregar um nó (liberar sua
  RAM) e retomar depois **com a conversa intacta**, reusando ao máximo a infra existente.

## 2. O que já existe (NÃO reinventar) — confirmado por leitura de código
- **Máquina kill→respawn** (`maestro/native/canvas.py`): `_respawn_node` (`:3038`), `_signal_child`
  (`:2984`), `_on_child_exited` (`:3003`), `_do_respawn` (`:3024`); guarda `_child_pid`+`_pidfd`
  (`:363-368`). **Padrão de "matar SEM respawnar" já existe:** `_kill_all_agents` (`:3943`) chama
  `_signal_child(term, SIGKILL)` direto, sem tocar `_respawn_state` → `_on_child_exited` NÃO
  respawna (só respawna se `_respawn_state=="killing"` ou `_respawn_pending`, `:3018-3022`).
- **⚠️ Acoplamento a conhecer:** a **escalada graciosa** SIGTERM→1500ms→SIGKILL vive DENTRO de
  `_respawn_node`, que seta `_respawn_state="killing"` (`:3052-3061`) — reusá-la traz o respawn
  junto. Descarregar com escalada exige um **3º estado** na máquina (ver Bloco B).
- **Sandbox `--unshare-pid`** (`sandbox.py:65`, `--chdir ws` `:62`): SIGKILL no bwrap colapsa a
  árvore; a sessão do claude é gravada sob o cwd = **workspace do nó**.
- **Workspace POR-NÓ:** `_node_ws(nid)` = `Workspace(.../workspaces).path(nid)` (`canvas.py:3267`)
  → `~/.claude/projects/<slug-do-ws-do-nó>/` é **exclusivo do nó** (base da captura, §4-A′).
- **Modo `captured` de sessão já existe:** `session.py:97 _run_captured` + `profile.extract_session_id`
  — o padrão a espelhar (1ª exec cria, capturamos o id real; seguintes retomam).
- **Primitiva de "ocupado" on-demand:** `tui_busy(_term_text(term))` (usada por `_mon_quiet`,
  `canvas.py:3556-3561`) — este é o guard consultável, **não** o "monitor v0.53.0" (que é
  orientado a evento, ignora o nó em foco `:3538`, e pode estar desligado).
- **Tabela `sessions`** (`store.py:233`) **é do orquestrador e keyed por `agent_id` = o `nid` do
  canvas** (`controller.py:46-58`, `orchestrator.py:284-296`) → **NÃO usar pro session interativo**
  (colide com o medidor/budget F1). Usar chave própria (§4-A′).
- **Reusáveis visuais:** monitor de atividade (v0.53.0), medidor de custo por nó (v0.54/0.55, padrão
  de badge), roster + `ui_state` (reconstroem o card no startup).

## 3. Veredito da pesquisa (fonte + data 2026-07-03 · revisado pelo Fable)
1. **Matar-e-retomar funciona nas duas CLIs.** `claude --resume <uuid>`; `codex resume` (picker).
   Ressalva: o resume **relê o transcript** → re-ingestão de tokens (custo único e condicional).
   Fontes: [OpenAI Codex CLI](https://developers.openai.com/codex/cli/features),
   [Codex resume](https://inventivehq.com/knowledge-base/openai/how-to-resume-sessions).
2. **✅ SPIKE PROVADO (runtime, `sandbox.wrap()` real + `claude -p`):** `--session-id` dentro do
   bwrap grava sessão no host; `--resume` recupera contexto; **reusar `--session-id` → `Error:
   already in use`** (por isso NÃO se injeta id fixo — §3.6).
3. **Ganho de RAM real e duplo:** matar libera a RAM privada (~250–350 MB/nó pesado) + os slots de
   `zram` do nó. Compartilhamento medido é modesto (PSS≈RSS).
4. **Congelar (SIGSTOP/freezer): DESCARTADO.** SIGSTOP no bwrap não desce no namespace (exigiria
   `cgroup.freeze` por-nó, infra inexistente); zram a 50% → risco OOM; kernel já faz sozinho.
5. **CRIU: DESCARTADO.** ARM64 buga restore (mremap/vdso) + bwrap complica. Fontes:
   [CRIU When C/R fails](https://criu.org/When_C/R_fails), [criu#90](https://github.com/checkpoint-restore/criu/issues/90).
6. **⚠️ Correção do plano (Fable):** injeção de `--session-id` **fixo persistido** quebra no 2º
   spawn (o argv é reusado em ~8 gatilhos de respawn: `canvas.py:1621,1627,1688,1715,1887,4247,
   4301,5940`) → nó cairia no `exec bash -i` pelado. **Solução: CAPTURA** — ler o JSONL mais novo
   no dir exclusivo do nó (`_node_ws`) e retomar com `--resume`. Robusto a fork de id (sempre pega
   o mais novo), não toca o argv, não colide com o F1.

## 4. Plano cirúrgico (blocos → stories)
**Bloco A′ — ciclo de vida de sessão por CAPTURA (não injeção):**
- No unload (e/ou continuamente), ler o **JSONL mais novo** em `~/.claude/projects/<slug de
  `_node_ws(nid)`>/` → é a sessão viva do nó. Persistir em **chave própria do canvas**
  (`nodecfg_{nid}_session`, no `ui_state` — sobrevive a restart), **NÃO** em `sessions[nid]`.
- **Limpar `nodecfg_{nid}_session` no `_close_node`** (hoje não limpa nada disso → nid reciclado
  herdaria a sessão de um nó morto — classe de bug de id órfão já conhecida no projeto).
- Espelha `_run_captured`/`extract_session_id` (`session.py:97`). `codex`: sem captura de argv — o
  reload usa o picker (Bloco C).

**Bloco B — descarregar (o "unload"):**
- Ação **"Descarregar"** na cápsula contextual do nó.
- **Guard de ociosidade = `tui_busy(_term_text(term))` on-demand** (NÃO "o monitor"): se ocupado,
  avisar (matar perde trabalho em voo; o resume só devolve transcript).
- **3º estado na máquina — `"unloading"`:** escala SIGTERM→1500ms→SIGKILL como o respawn, MAS
  `_on_child_exited` **não** dispara `_do_respawn` nesse estado. (Alternativa mínima: SIGKILL direto
  como `_kill_all_agents`, abrindo mão da escalada graciosa — decidir na story.)
- **Desligar o monitor de atividade do nó no unload** (senão o banner de morte vira falso "é sua
  vez" — cf. o `skip` de `canvas.py:3032`).
- Persistir flag **"descarregado"** no `ui_state` (estado visual; **precisa persistir** — "abre
  igual fechou"). Card fica leve, RAM liberada.

**Bloco C — retomar (reload) + STARTUP:**
- Clicar no nó descarregado → respawn **resume-aware** (mutar `_base_argv` como `_rebuild_agent_argv`
  `:2956`, ou variante): **claude** `--resume <session capturada>`; **codex** `codex resume`
  (picker; humano escolhe).
- **Decidir a semântica do restart pós-resume:** depois de retomar, o botão "reiniciar" deve zerar
  ou continuar retomando? (mudança silenciosa se `_base_argv` virar resume-argv — decidir, não
  descobrir.)
- **Caminho de STARTUP (onde mora o maior ganho):** o roster hoje **spawna todos os nós ao abrir o
  app** (`canvas.py:6909+`). Nó com flag "descarregado" precisa **nascer SEM spawn** — senão
  reabrir o app ressuscita 6 agentes e o estado persistido vira mentira visual.
- Edge case: nó com `command` custom bypassa `_base_argv` (`_effective_argv:2919`) — tratar.

**Bloco D — visibilidade (opcional, reusa padrão):**
- Badge de RAM por nó (`/proc/<pid>/smaps_rollup` da árvore) reusando o padrão do medidor de custo;
  indicador visual claro de "descarregado".

## 5. Decisões abertas / spikes
- **Spike barato pendente (não bloqueia, mas confirma):** 2 ciclos unload→resume→conversar→unload→
  resume — verificar se o `--resume` **mantém ou forka** o session-id. (A captura resolve os dois
  casos por design; o spike só documenta o comportamento.)
- **Interativo vs `-p`:** spike provou `-p`; confirmar no 1º nó interativo real (alta confiança).
- ✅ **Re-ingestão no resume (DECIDIDO na story C):** sem diálogo extra — **"Retomar" = resume;
  "Reiniciar" = "esquecer"** (o respawn normal já usa o argv natural e limpa a flag). Dois
  caminhos que já existem na UI; um 3º prompt seria cerimônia.
- ✅ **Semântica do restart pós-resume (DECIDIDO na story C):** o argv de resume é ONE-SHOT
  (nunca muta `_base_argv`) → "Reiniciar" SEMPRE começa do zero. Sem mudança silenciosa.
- ✅ **Gatilho do reload (DECIDIDO na story C):** clique no **terminal** do nó descarregado
  (não no frame — arrastar pelo header não pode ressuscitar) + ⏏ da cápsula vira toggle.
- **codex + cwd:** o picker do `codex resume` não separa nós sozinho; o humano separa. Documentar.
- **Escopo:** F separada; **não** encadear com "reattach de órfãos pós-crash" (item vizinho no
  `docs/15`).

## 6. Sequência de stories (revisada pelo Fable)
1. **A′ — captura + persistência (chave própria) + limpeza no `_close_node`.** Plumbing testável,
   sem mudança visível. (B pode vir antes mecanicamente, mas B sem A′ = "unload que esquece",
   meio-produto perigoso de mergear.)
2. **B — ação descarregar** (estado `"unloading"`, guard `tui_busy`, kill, desliga monitor,
   persiste flag).
3. **C — reload resume-aware + startup-sem-spawn** + semântica do restart + edge de command custom.
4. **D — badge de RAM** (opcional).

## 7. Fora de escopo (decidido)
- Congelar (SIGSTOP/freezer) e CRIU — descartados (§3.4/§3.5).
- `swappiness`/`zram writeback` — alavanca de **sistema**, separada (regras de boot/kernel do
  uConsole em `/home/kali/AGENTS.md`; não é feature do app).

## 8. Story D — plano cirúrgico (badge de RAM + indicador "descarregado")

> Escrito 2026-07-04, após A′+B+C entregues e testados ao vivo. Revisão adversarial do
> Fable: ver §8.5.

### 8.1 Objetivo
Fechar o loop **medir → decidir → descarregar → retomar**: hoje o usuário descarrega "no
chute". (a) **Badge de RAM por nó** no header (padrão do medidor de custo F1); (b) **estado
visual "descarregado"** de verdade (hoje o nó morto fica "idle" — indistinguível de um vivo
ocioso no card e no minimapa).

### 8.2 O que já existe (reusar, não reinventar)
- **Método de medição VALIDADO ao vivo** (investigação 2026-07-03): `/proc/<pid>/smaps_rollup`
  — RSS (visto), **PSS (fatia real)**, **Private (piso garantido a liberar no kill)**. Números
  reais: claude ≈ 232-447 RSS / 175-350 PSS / 156-323 Private (MB).
- **Árvore do nó**: `term._child_pid` é o bwrap; filhos via `/proc/<pid>/task/*/children`
  (recursivo). `--unshare-pid` não esconde os filhos do host.
- **Padrão de badge**: `head._cost` + `.node-cost` (10px discreto) + `_fmt_cost`/
  `_refresh_node_cost` (F1). O D espelha com `head._ram` + `.node-ram` + `_fmt_ram`/
  `_refresh_node_ram`.
- **Padrão de estado**: `set_node_state` + `STATE_COLORS`/`_STATE_ICON` (Lucide pré-colorido
  `maestro-state-<st>`)/`_STATE_PT` + minimapa pinta pela cor do estado.
- **Padrão de tick**: `GLib.timeout_add_seconds` (routines 30s, attention 10s).

### 8.3 Decisões (v2 — CORRIGIDAS pela revisão adversarial do Fable, §8.5)
1. **Métrica do badge = PSS** (peso real; a soma dos PSS da frota ≈ uso real total).
   Tooltip com **2 números** (não 3): "peso real (PSS) X MB · liberável ao descarregar
   (Private) Z MB" — RSS não muda nenhuma decisão do usuário.
2. **Worker THREAD daemon (tick 10s) + `GLib.idle_add` só pra setar labels** — main loop
   nunca mede. Motivo (Fable): a árvore real de um nó é 3-6 processos (bwrap→bash→claude+
   filhos node/MCP); 8 nós ≈ 25-50 reads de `smaps_rollup`/tick, e o rollup varre TODAS as
   VMAs no kernel (claude ~400MB tem milhares) → ~100-150ms de jank por tick no CM4 se
   fosse na main loop. Precedente idêntico no próprio arquivo: `usage_bus` marshalado
   (canvas.py:450-452). O worker relê `term._child_pid` A CADA passada (nunca cacheia a
   árvore — respawn no meio do tick mede o processo novo ou nada, nunca um estranho).
3. **"Descarregado" é CAMADA DE VISTA, NÃO estado da máquina.** Furo achado pelo Fable:
   um nó descarregado **continua recebendo trabalho headless pelos cabos** (o orquestrador
   spawna `claude -p` próprio, não usa o PTY) — `_on_step_ts`/`_refresh_attention` chamam
   `set_node_state(busy/idle/...)` direto e **apagariam um estado "unloaded" silenciosamente**.
   Solução: a RENDERIZAÇÃO deriva — `set_node_state` (e o init do dot) mostram eject/rótulo
   "descarregado" quando `s == "idle" and _node_unloaded(nid)`. Máquina intocada (nada em
   `STATE_COLORS`/`ATTENTION_VISUAL_STATES`/attention/web); busy headless aparece como busy
   (correto); ao voltar a idle o eject reaparece sozinho; zero transição nova.
4. **Ícone: copiar/recolorir do lucide-static À MÃO** (não existe pipeline/script — os 6
   SVGs são copiados e recoloridos manualmente, conferido no git log). **Lucide NÃO tem
   "eject"** → autorar um eject trivial (triângulo+barra) pra manter consistência com o ⏏
   da ação, ou usar `moon`; decidir na implementação. Tabelas de estado vivem em **3
   lugares** — `canvas._STATE_GLYPH/_STATE_ICON/_STATE_PT`, `state.STATE_ACTIVITY` (rótulo
   E3; sem entrada o status fica vazio) e `agents.STATE_COLORS` — com a camada-de-vista,
   só os rótulos/ícone locais ganham entrada; `STATE_COLORS` fica INTOCADO.
5. **Módulo novo sem GTK** `maestro/engine/proc_ram.py` (`tree_pids(root)` via
   `/proc/<pid>/task/*/children` — exige CONFIG_PROC_CHILDREN, ok no kernel 6.12 do device;
   `tree_ram(root) -> (rss, pss, private)`), unit-testável no venv contra árvore REAL
   spawnada (bash+sleep filhos). PID morto entre listdir e read → retorno parcial silencioso.
6. **Badge do nó descarregado = vazio, zerado NO PRÓPRIO `_unload_node`** (não esperar o
   próximo tick — 10s de número velho é mentira temporária).
7. **Notificação de RAM configurável (pedido do usuário, 2026-07-04):** limiar X MB
   **GLOBAL por-nó** (caso de uso real do CM4: "nó passou de 500MB → considere descarregar");
   por-nó no ⚙ e total-da-frota CORTADOS (YAGNI — Fable). Persistido em `ui_state`;
   UI no diálogo do 💰 que vira "Limites" ($ e RAM) — **documentar a dual-persistência**
   (budget no store, RAM no ui_state) pra ninguém "unificar" depois. Ao cruzar: `notify()`
   + css `.node-ram-high` no badge. **Anti-flapping: HISTERESE** — notificação re-arma só
   abaixo de **0.9·X** (o css pode seguir o limiar exato; só a notificação usa histerese).
   Input: MB inteiro; "" = off (default); parse inválido = off, nunca crash.

### 8.4 Riscos conhecidos (mitigação no desenho)
- smaps_rollup de processo que morreu entre o listdir e o read → `ProcessLookupError`/
  `FileNotFoundError` silenciosos (best-effort, nunca levanta).
- **Minimapa NÃO pinta pela cor do estado** (claim v1 era FALSA — só recolore nós em
  `ATTENTION_VISUAL_STATES`; o resto é azulado fixo): a distinção de descarregado exige
  **branch explícito no `_mm_items`** (`_node_unloaded` → cinza apagado).
- **Nó shell** (bash ocioso ≈ 3-5MB): badge aparece em todo nó com filho vivo — informação
  barata e consistente; documentado como decisão (não bug).
- **`_close_node` limpa o estado do worker de RAM** (dict de medições/alertas) — classe de
  bug de id reciclado já conhecida no projeto.
- Web UI (`canvas.js` tem `COLORS` próprio já divergente, sem "waiting") — dívida
  PRÉ-EXISTENTE, não tocar neste bloco.

**Critérios numéricos do teste vivo (aceite):**
(a) trabalho na main thread por tick < 5ms (só `set_text`); (b) duração da medição no
worker logada e < 300ms com 4+ nós claude reais no CM4; (c) badge vs `smem`/`ps` do mesmo
processo: divergência ≤ 10%; (d) cruzar o limiar notifica 1x; oscilar ±5% em volta do
limiar NÃO re-notifica (histerese provada); (e) reabrir o app com nó descarregado →
dot/badge/minimapa corretos sem processo.

### 8.5 Revisão adversarial (Fable) — resultado (2026-07-04)
- **Item 1 SUSTENTADO** (ajuste: tooltip com 2 números, RSS cortado).
- **Item 2 DERRUBADO** → worker thread + idle_add (conta refeita: 25-50 reads/tick,
  ~100-150ms de jank na main loop do CM4).
- **Item 3 DERRUBADO** → camada de vista, não estado: handoff headless num nó descarregado
  sobrescreveria o estado "unloaded" silenciosamente (`_on_step_ts` chama `set_node_state`
  direto — verificado no código). A alternativa é estritamente melhor: zero consumidor novo.
- **Item 4 AJUSTADO**: premissa "mesmo pipeline" era falsa (SVGs copiados à mão); lucide
  não tem eject; 3 tabelas de estado mapeadas.
- **Itens 5/6 SUSTENTADOS** (com contrato de PID-morto e zerar badge no unload).
- **Item 7 SUSTENTADO no global; AJUSTADO**: histerese 0.9·X contra flapping (furo
  confirmado); por-nó e frota cortados (YAGNI); dual-persistência documentada.
- **Furos adicionais incorporados** (§8.4): minimapa (claim falsa), nó shell, PID
  reciclado no tick, critérios numéricos do teste vivo, limpeza no `_close_node`.
