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
