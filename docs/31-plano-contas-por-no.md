# Plano — Contas por nó (config-dir isolado por terminal)

> Promovido da fila (`docs/15`, item "Perfis de agente = conta/ambiente isolado por nó",
> reformulado pós-Fable 2026-07-12). **Design v2 pós-revisão adversarial (Fable 5, 12
> emendas — §9). Decisões D1-D8 VALIDADAS (2026-07-12, §10); implementado na v0.66.0
> (branch `feat/contas-por-no`, ADR-28).**
>
> **Nome do conceito: CONTA** (não "perfil") — "profile" já é o `AgentProfile` dos adapters
> TOML (`maestro/engine/adapters/base.py:32`, claude vs codex) e "papel/role" já é o
> `AgentSpec` de teams. Terceiro conceito exige terceiro nome; chave `node_cfg` = `account`.

## 1. Objetivo

Cada nó-agente pode ser associado (pelo ⚙, decisão humana) a uma **conta nomeada** =
diretório de config isolado (`CLAUDE_CONFIG_DIR` pro claude, `CODEX_HOME` pro codex) + env
extra. Casos de uso validados: trabalho vs pessoal simultâneos no mesmo canvas; conta de
cliente por projeto; API-key vs assinatura. Badge no card mostra a conta do nó. Sem conta
definida, o nó usa o default (`~/.claude`/`~/.codex`) — status quo byte a byte.

**O que NÃO é (guardas de mercado/ToS, pesquisa 2026-07-12):** NUNCA rotação automática de
conta, NUNCA pool/relay de token, NUNCA burlar limite. Conta é **escolha humana explícita
por nó** — o padrão "Arquitetura B" que a própria Anthropic aceitou
([issue #261](https://github.com/anthropics/claude-code/issues/261), fechada como completed
em mar/2025); o que ela bane é extração de token OAuth pra harness de terceiros,
compartilhamento e evasão de limite (confirmação oficial de membro do time do Claude Code,
2026: "It's not against ToS to have multiple MAX accounts"). **Nuance honesta (E10): o
enforcement da Anthropic é discricionário e já houve ondas de ban imprecisas atingindo
multi-conta legítimo — este design MINIMIZA o risco (cliente oficial, credencial isolada,
zero automação de troca), não o zera.** Fontes:
[Two Multi-Account Architectures (dev.to)](https://dev.to/vainamoinen/two-multi-account-claude-code-architectures-one-anthropic-accepts-one-they-ban-2om7),
[MetricNexus](https://metricnexus.ai/blog/anthropic-banning-multiple-claude-accounts),
[grandlinux](https://www.grandlinux.com/en/blogs/claude-account-ban-risk.html).

## 2. O que já existe (REUSAR — não reinventar) — mapeado no código 2026-07-12

- **Injeção de env por nó JÁ existe**: `_node_envv(nid)` (`canvas.py:3272`) lê
  `node_cfg(nid,"env")`, merge com `os.environ`, e alimenta TODOS os spawns interativos
  (inicial `:3720`, respawn `:3342`, reload/reattach `:3778`). O bwrap não usa `--clearenv`
  → env externo propaga pro CLI.
- **Sandbox quase pronto**: `sandbox.wrap()` (`sandbox.py:29`) já aceita `rw_paths` e
  `setenv` **por chamada** (`:74-77`, `:82-83`). Só a máscara (§5.3) exige um parâmetro
  novo (`mask_paths`). **Armadilha**: o guard `if Path(rp).exists()` (`sandbox.py:76`)
  descarta silenciosamente dir inexistente → o dir da conta é criado ANTES do spawn.
- **Persistência por nó pronta**: `node_cfg`/`set_node_cfg` (`state.py:57/64`, chaves
  livres, sem migração) — mesmo trilho de `env`/`birth_group`/`autoapprove`. Diálogos ⚙
  seguem o padrão de `canvas.py:1705`.
- **Construção de argv: 4 pontos, todos mapeados (E2)** — criação
  (`_new_agent_terminal:6023`), rebuild (`_rebuild_agent_argv:3268`), resume one-shot do
  unload (`_resume_argv:3742`) e **restore do roster no boot (`canvas.py:7935`)**. A conta
  fica "assada" no argv → os 4 resolvem a conta, senão o furo é silencioso (boot
  respawnaria tudo na default).
- **Header do card (v0.60.0)**: badge nova entra ao lado da cápsula de papel
  (`head._agent`, `canvas.py:2284-2288`), refresh no padrão `_refresh_agent_cap` (`:3955`).
- **Leitores de sessão hardcoded em `~/.claude`/`~/.codex` — são TRÊS módulos, não um
  (E3)**: `usage.py:90/116` (medidor → budget cap), `session_capture.py:37` (unload/reload
  Bloco A′) e `orphans.py:35` (reattach pós-crash). Todos precisam seguir o config-dir.

## 3. Pesquisa ao vivo (2026-07-12) + PROVA no device

**Mercado/dor** (fontes coletadas 2026-07-12):
- 10+ issues duplicadas no anthropics/claude-code pedindo perfis/multi-conta (#20549 —
  canônica, jan/2026, fechada como dup SEM resposta da Anthropic em 6 meses —, #27359,
  #41048, #33307, #24337, #20131, #24963, #35856, #44687, #30031). Ecossistema paralelo:
  ClaudeSwitch, aliases de shell.
- Concorrentes: **Clave PR #23** (mergeado 2026-06-05) entregou exatamente isso — conta =
  label → config-dir, `CLAUDE_CONFIG_DIR` por PTY, badge no header — mas macOS/Keychain.
  **AgentsRoom** idem (`~/.agentsroom/claude-profiles/<id>/`, resolução em cascata). Vibe
  Kanban/Crystal/Conductor têm "profiles" de CONFIG (modelo/flags), não isolamento de
  conta. **Diferencial que resta pro maestro: canvas + Linux-ARM + simultaneidade por nó.**
- **Codex**: `CODEX_HOME` é nativo e documentado exatamente pra "múltiplas instâncias
  isoladas no mesmo host, cada uma com credenciais e histórico próprios" (config.toml,
  auth.json, sessions — tudo sob `$CODEX_HOME`).

**Prova no device (claude 2.1.207, 2026-07-12, medido — não presumido):**
```
CLAUDE_CONFIG_DIR=<dir-novo> claude -p "ok"
→ "Not logged in · Please run /login"          # NÃO caiu de volta pro ~/.claude ✅
→ criou <dir>/.claude.json                      # gotcha do Windows NÃO vale no Linux ✅
→ criou <dir>/projects/<slug-do-cwd>/           # usage/sessões nascem DENTRO do dir ✅
```
Três consequências: isolamento de credencial é real; login é o próprio CLI que guia (o
maestro NUNCA toca credencial — sem Keychain, sem cópia de auth); e `usage.py`/
`session_capture.py`/`orphans.py` PRECISAM seguir o config-dir do nó (§4.4), senão budget
cap fica cego e unload/reattach quebram.

## 4. Design v2 (pós-Fable)

### 4.1 Registro de contas (host-only)
- Blob JSON em `ui_state` (`Store.get_ui/set_ui`, padrão ADR-22): lista de contas
  `{name, agent, env}` — o config-dir é DERIVADO do nome (não é campo livre):
  `~/.maestro-accounts/<agent>/<slug(name)>/`. Raiz única de propósito (§5.3).
- CRUD na **cápsula principal (FAB)** → diálogo "Contas" (regra do AGENTS.md: config de
  software entra na cápsula 1). Criar = mkdir do config-dir; renomear não move dir (nome é
  label; slug congela na criação).
- **Excluir conta (E8b)**: desregistra + desassocia os nós — nó VIVO desassociado sofre
  rebuild+respawn na hora (badge nunca mente sobre a conta em execução); nó `unloaded` só
  troca cfg+argv, SEM acordar. O dir fica no disco (credencial não se apaga por engano; a
  mensagem diz o caminho).
- **Login**: conta nova nasce deslogada. Primeiro spawn do nó mostra o próprio prompt do
  CLI ("Not logged in · /login") — o humano loga UMA vez dentro do nó, credencial fica no
  dir da conta. Zero manuseio de segredo pelo app.

### 4.2 Seleção por nó — SÓ no ⚙ (corte E11)
- **Criação continua leve** (clique-pra-posicionar intacto, sem combo novo): nó nasce
  default; quem quer conta abre o ⚙ (caso raro paga 1 clique; a maioria não paga nada).
- **⚙ do nó**: diálogo no padrão `canvas.py:1705`; trocar conta → `set_node_cfg
  (nid,"account",...)` → **limpeza de sessão obrigatória (E3)**: limpa `node_cfg session`
  E a linha do nó na tabela `sessions` do engine (`session.py:38-45`) — senão o próximo
  headless faz `--resume` de sessão da conta antiga e falha. Depois:
  nó vivo → `_rebuild_agent_argv` + respawn (precedente autoapprove `:1849/1876`);
  **nó `unloaded` → só cfg+argv, SEM spawn (E8a — não ressuscitar nó que o dono descarregou
  pra liberar RAM).** Texto no diálogo: "trocar conta reinicia o terminal; sessões ficam na
  conta antiga".
- **Recruit** (`canvas.py:5031`): herda a conta do manager (mesmo espírito do
  `birth_group`/ADR-21 — decisão host no gesto; agente nunca escolhe conta).
- **Team Templates**: SEM campo novo nesta fase (YAGNI; mesmo corte do docs/30 E6).

### 4.3 Fiação — resolvedor único engine-side (E4)
- **Novo `engine/accounts.py` (gi-free)** é o ÚNICO resolvedor: `resolve(store, agent_id)
  → {config_dir, env_var, extra_env} | None`, lendo `node_cfg account` + registro no
  Store. Engine e UI consomem o MESMO resolvedor — cobre delegate/ask/chain/routine/
  handoff de uma vez (o `SessionManager` já tem `_store`; `cli_routine` constrói
  controller próprio mas passa pelo mesmo caminho).
- `agent_argv` (`native/agents.py:33`) ganha o parâmetro conta: **SUBSTITUI (não
  acrescenta — E1) os paths de config default do adapter** (`~/.claude`, `~/.claude.json`,
  `~/.config/claude` / `~/.codex`, `~/.config/codex`) pelo dir da conta no `rw_paths` da
  chamada + seta `CLAUDE_CONFIG_DIR`/`CODEX_HOME` via `setenv` do bwrap (vale igual pro
  interativo e headless). Com o env var setado o CLI não precisa do default (provado §3) →
  o `~/.claude` do dono fica só-leitura pro nó de conta (e §5.3 fecha o resto).
  `mkdir -p` antes do spawn.
- **Os 4 call-sites de argv** (§2) passam a conta; headless (`agent_run.py:44-53`,
  `orchestrator.py:322-337`) resolve por `agent_id` via `engine/accounts.py`.
- **Floor run** (`canvas.py:5813`) roda por agente BASE (sem identidade de nó) → **roda na
  conta default, decisão explícita** (D7), documentado no diálogo do floor.
- **Comando custom (E7)**: `_effective_argv` (`canvas.py:3221`) troca o argv por `bash -lc`
  SEM bwrap → o env da conta entra TAMBÉM no `_node_envv` (o caminho custom herda o env do
  VTE de graça; config-dir correto mesmo sem sandbox). Documentado: comando custom já era
  sem-sandbox (propriedade pré-existente); a conta segue via env.
- **Precedência de env (E6)**: `--setenv` do bwrap sobrescreve o env herdado → pra manter
  "nó vence conta", o resolvedor OMITE do setenv da conta as chaves que o env do nó define.
  Headless: só o env da conta se aplica (env por nó nunca se aplicou ao headless —
  assimetria pré-existente, documentada).

### 4.4 Budget/usage/sessões seguem a conta (E3)
- `usage_from_session` (`usage.py:125`) e os 2 leitores ganham `config_dir` opcional
  (default = atual); orchestrator (`:332`) passa o da conta do nó.
- **`session_capture.py:37` e `orphans.py:35` idem** — `project_dir`/`newest_session_id`/
  `detect_orphans` com `config_dir` do nó: unload/reload captura a sessão certa; pós-crash
  o nó de conta vira órfão-recuperável normalmente.
- **Semântica do cap INALTERADA**: teto GLOBAL do fleet (soma contas); cap por conta =
  YAGNI. `record_spend` (`budget.py:44-55`) já tolera troca (rotação → banca total novo);
  session_id é uuid4 (sem colisão entre contas); ledger é por-nid (E12 — verificado).
  **O turno LIVE injetado no VTE segue não-contado (lacuna pré-existente do ADR-26,
  backlog docs/15) — "budget segue a conta" NÃO cobre o live (E12).**

### 4.5 Badge no card (E9)
- Label `head._account` ao lado da cápsula de papel (`canvas.py:~2288`), **curta:
  `max_width_chars≈8` + ellipsize** (header de 420px já disputado por dot+título+papel+3
  chips+✕); nome completo + dir no tooltip. Oculta quando default;
  `_refresh_account_badge` no padrão `:3955`.

## 5. Invariantes de segurança (ADR-17 aplicado)

1. **Autoridade só do host**: associar/trocar/criar conta = SÓ UI. Nenhum comando `maestri`
   lê ou escreve conta (mesmo princípio do "zerar budget só no host" / brief host-only).
2. **Sem rotação automática, sem fallback silencioso**: conta configurada e dir sumiu →
   recria VAZIO (CLI pede login) — NUNCA cair calado pro `~/.claude` (vazamento de conta;
   é o padrão de automação que a Anthropic pune).
3. **Máscara das contas alheias no sandbox (E5)**: exige mudança REAL em `sandbox.py`
   (novo param `mask_paths` → `--tmpfs`), com 3 regras: (a) `--tmpfs ~/.maestro-accounts`
   entra ANTES do `--bind` do dir da própria conta (bwrap processa mounts em ordem);
   (b) a máscara vale pra **TODO spawn de agente, inclusive nós default** — senão nó
   default lê ro as credenciais de todas as contas via `--ro-bind / /`; (c) a raiz
   `~/.maestro-accounts/` é criada no 1º uso (guard `exists()` pula path inexistente).
4. **O default do dono protegido (E1)**: nó de conta NÃO monta `~/.claude` rw (substituição
   no §4.3) — sem isso, agente de conta cliente poderia sobrescrever a credencial principal.
5. **Budget íntegro**: usage segue o config-dir (§4.4) — sem isso o gate do ADR-22/26
   contaria só a conta default (buraco no controle de segurança do ADR-17).

## 6. Pontos no código (mapa fino v2)

| Camada | Arquivo:linha | Mudança |
|---|---|---|
| Resolvedor | novo `engine/accounts.py` (gi-free) | name→{config_dir,env_var,extra_env}; slug; mkdir; `resolve(store, agent_id)` |
| Storage | `state.py` (nada) | chave `node_cfg account` + blob `ui_state accounts` |
| argv | `native/agents.py:33/89-95` | conta → **substitui** rw_paths de config + setenv |
| call-sites argv (4) | `canvas.py:6023` (criar) · `:3268` (rebuild) · `:3742` (resume unload) · `:7935` (**restore no boot**) | todos resolvem a conta (E2) |
| headless | `agent_run.py:44-53`, `orchestrator.py:322-337` | resolve via `engine/accounts.py` por agent_id (E4) |
| sandbox | `sandbox.py:29+` | **novo `mask_paths`** (tmpfs antes dos binds — E5), em todo spawn de agente |
| usage | `usage.py:90/116/125`, `orchestrator.py:332` | `config_dir` opcional |
| sessões | `session_capture.py:37`, `orphans.py:35`, `session.py:38-45` | `config_dir` + limpeza na troca (E3) |
| env custom | `canvas.py:3272` (`_node_envv`) | env da conta no VTE (cobre `_effective_argv:3221` — E7) |
| UI CRUD | canvas.py FAB (cápsula 1) | diálogo Contas (criar/renomear/excluir com E8b) |
| UI nó | `canvas.py:1705` (padrão ⚙) | picker + limpeza de sessão + respawn (unloaded: sem spawn — E8a) |
| recruit | `canvas.py:5031/5047` | herda conta do manager |
| badge | `canvas.py:2284-2318`, `:3955` (padrão) | `head._account` curto+ellipsize+tooltip (E9) |

## 7. O que NÃO muda (guard-rails)

- Adapters TOML (`claude.toml`/`codex.toml`) intactos — conta é camada por-nó SOBRE o
  adapter, não um adapter novo.
- Semântica do budget cap (global, monotônico, reset só host — ADR-22/26).
- Nó sem conta = comportamento de hoje, byte a byte (default é ausência da chave) — exceto
  a máscara §5.3, que se aplica a todos os spawns (fecha furo, não muda função).
- Criação de nó (clique-pra-posicionar) sem passo novo (E11).
- Credenciais: o app nunca lê/copia/move `auth.json`/`.credentials.json`.

## 8. Definition of done (rascunho)

- gi-free (`test_accounts.py`): resolve/slug/mkdir; argv SUBSTITUI rw_paths (E1: assertar
  que `~/.claude` NÃO está rw quando há conta); fallback-nunca-silencioso; máscara na
  ordem certa (E5); precedência env nó>conta (E6); usage/capture/orphans com `config_dir`
  acham JSONL no dir alternativo (fixture sintética **+ prova da fonte real**: run headless
  com dir isolado logado); limpeza de sessão na troca (E3).
- gi (`test_accounts_ui.py`): picker persiste; troca → respawn (vivo) / sem spawn
  (unloaded — E8a); excluir conta → E8b; badge com ellipsize; recruit herda conta;
  **fechar/reabrir → nó volta com o ARGV da conta (E2 — não só o badge)**.
- **Prova de runtime no device** (usuário confirma): criar conta "teste" → ⚙ associa →
  respawn mostra "Not logged in" (isolamento visível) + badge; logar; rodar turno; custo no
  chip (usage seguindo o dir); fechar/reabrir → conta persiste; unload/reload na conta.
- CHANGELOG + bump (1 por PR) + ADR novo (contas por nó).

## 9. Revisão adversarial (Fable 5, 2026-07-12) — v1 → v2

**Veredito: APROVADO COM EMENDAS (12).** A v1 prometia "invariante em todas as entradas"
sem sobreviver ao código. Críticas (obrigatórias): **E1** rw_paths por ADIÇÃO deixava o
`~/.claude` do dono RW dentro do nó de conta (violação direta do que o §5.3 dizia fechar)
→ substituição; **E2** faltavam 2 dos 4 pontos de argv — restore do boot (`:7935`, pior
caso: silencioso em toda reabertura) e resume do unload (`:3742`); **E3** `session_capture`
e `orphans` hardcoded quebravam unload/reattach pra nó de conta + troca de conta exigia
limpeza de sessão; **E4** headless sem mecanismo de resolução (rotina/chain rodariam na
default) → resolvedor único engine-side. Médias: **E5** máscara tmpfs exige `mask_paths`
no sandbox.py (a v1 dizia "nada muda"), ordem tmpfs→bind, e vale pra nós default também;
**E6** precedência de env estava invertida (setenv do bwrap vence o herdado); **E7**
comando custom (`_effective_argv`) bypassava tudo → env da conta também no `_node_envv`;
**E8** trocar conta de nó unloaded não pode acordá-lo; excluir conta força
rebuild+respawn dos vivos. Baixas: **E9** badge com ellipsize (header 420px); **E10**
claims de ToS conferidos ao vivo e corretos, mas exigem URLs + nuance de enforcement;
**E11** corte YAGNI: sem combo na criação (conta só no ⚙); **E12** budget verificado ok
(rotação/uuid4/por-nid), mas o LIVE não-contado precisa ficar explícito.

## 10. DECISÕES — VALIDADAS com o usuário (2026-07-12, pós-Fable)

Todas as recomendações aprovadas como estão ("ok", 2026-07-12):

| # | Decisão | Validado |
|---|---|---|
| D1 | Nome na UI: "Conta" vs "Perfil" | **Conta** (colisão com AgentProfile/roles) |
| D2 | Config-dirs derivados sob raiz única `~/.maestro-accounts/` vs caminho livre por conta | **raiz única** (viabiliza a máscara §5.3; caminho livre = YAGNI) |
| D3 | Máscara tmpfs das contas alheias (§5.3) | **sim** (fecha exfiltração ro entre contas; custo: param novo no sandbox.py) |
| D4 | Recruit herda conta do manager | **sim** (padrão birth_group) |
| D5 | Campo conta em TeamTemplate | **adiado** (YAGNI, mesmo corte do docs/30 E6) |
| D6 | Escopo do PR: 1 PR único (M/G) vs 2 | **1 PR** (unidade coerente) |
| D7 | Floor run (roda por agente BASE, sem nó) na conta default | **sim, explícito e documentado** (E4) |
| D8 | Conta SÓ no ⚙ (sem combo na criação — corte E11) | **sim** (criação continua leve) |
