# Architecture Document — maestro console

> 📌 **Cópia VERSIONADA da arquitetura** (espelha `_bmad-output/planning-artifacts/architecture.md`,
> gitignored). A **fundação** (headless, bwrap, envelope JSON, SQLite WAL, mutex) é **fiel ao código**.
> Ressalvas: §10 lista canvas/papéis como "futuro pós-MVP" mas **já foram entregues**; o §9 (ADRs)
> espelha só até ~ADR-12 — os **ADRs canônicos e completos (ADR-1..29)** estão em [`ADR.md`](ADR.md).
> **Estado atual:** [`STATUS.md`](STATUS.md). Mantido aqui p/ histórico git e backup.

> Produto: **maestro console** 🎼 · Repositório: `maestri-console`
> Artefato BMad · Tipo: Architecture · Data: 2026-06-21 · PT-BR
> Status: **APROVADO** — direção aprovada pelo usuário em 2026-06-21, com 4 correções obrigatórias + clarificação do tmux aplicadas (v2). Sem novos spikes.
> Base: `prd.md` (v3 APROVADO), `spike-fase0/0.1/0.2-resultados.md`, `docs/02-pesquisa-equipes-autonomas.md`

---

## 1. Princípios arquiteturais (derivados do spike)

1. **Headless é o caminho de DADOS.** Orquestração programática usa `claude -p` / `codex exec` (saída limpa, fim por `returncode`). Provado 100%.
2. **tmux é OBSERVABILIDADE/LOG da execução headless.** O pane mostra o stream/log do processo headless para o humano acompanhar (`tmux attach`) — **não** é uma TUI interativa do agente espelhada automaticamente, e **não** é fonte de dados. O agente não roda duas vezes.
2b. **Segurança por padrão (sandbox de SO).** Cada agente roda confinado por **bwrap (bubblewrap)**: workspace **rw**, `/tmp` **privado** (tmpfs), resto do sistema **read-only**, rede mantida, dirs de config/sessão do agente **rw**. As flags de permissão do CLI (claude `--permission-mode acceptEdits`; codex `--sandbox workspace-write`) evitam prompts, mas **NÃO** são o limite de segurança — o limite é o **bwrap**. Sem flags de bypass. **Fail-safe:** se bwrap ausente, recusa executar. *(Validado em E2-S2: claude+codex negam escrita em `$HOME`; `/tmp` não vaza para o host.)*
3. **Orquestrador-mediado, não agente↔agente direto.** Fluxo `orquestrador → A → orquestrador → B` (padrão orchestrator-worker, mais robusto).
4. **Engine desacoplada da UI.** Núcleo sem dependência de TUI/Web (NFR6).
5. **Agnóstico de agente via adapter declarativo.** Novo agente = novo perfil, sem tocar no core (NFR5).
6. **Estado externo, não na cabeça do agente.** Sessões, logs e tarefas persistidos em disco (sessões via `--resume`).
7. **Nunca travar por um agente.** Timeout + `returncode` + estado de erro isolam falhas.
8. **Leve.** Python puro, sem binários nativos; cabe no CM4 (validado: 4 agentes ativos, RAM folgada).

---

## 2. Visão geral (componentes)

```
                    ┌──────────────────────────────────────────────┐
                    │                  ORCHESTRATOR                  │
                    │  decompõe intenção → tarefas → delega/agrega   │
                    └───────────────┬───────────────────────────────┘
                                    │ (Envelopes FR15)
                    ┌───────────────▼───────────────┐
                    │           MESSAGE BUS          │  roteia envelopes
                    │     + Envelope (encode/parse)  │  entre orquestrador
                    └───┬─────────┬──────────┬───────┘  e agentes
                        │         │          │
              ┌─────────▼──┐  ┌───▼─────┐  ┌─▼──────────┐
              │  REGISTRY  │  │  QUEUE  │  │  DETECTOR  │  returncode (headless)
              │ estado dos │  │ tarefas │  │  / estado  │  / TUI-state (visib.)
              │  agentes   │  │ p/ idle │  │  conclusão │
              └─────────┬──┘  └───┬─────┘  └─┬──────────┘
                        │         │          │
                    ┌───▼─────────▼──────────▼────┐
                    │        AGENT ADAPTERS        │  perfil declarativo por CLI
                    │  (claude, codex, … futuros)  │  launch/onboarding/extract
                    └───┬───────────────────┬──────┘
                        │ DATA path         │ VISIBILITY path (opcional)
                ┌───────▼────────┐   ┌──────▼─────────────┐
                │ HEADLESS RUNNER │   │  TMUX VISIBILITY   │
                │ claude -p /     │   │  pane espelho +    │
                │ codex exec      │   │  estado-da-TUI     │
                │ + SESSION MGR   │   │  (tmux attach)     │
                └───────┬─────────┘   └────────────────────┘
                        │
                ┌───────▼────────┐        ┌──────────────────┐
                │  FILESYSTEM    │◄───────┤  PERSISTENCE/LOGS │ sessões, tarefas,
                │ artefatos/path │        │  (estado externo) │ histórico (JSON)
                └────────────────┘        └──────────────────┘

   Frontends plugáveis:  [ TUI (MVP) ]   ...   [ Web UI (futuro) ]
```

---

## 3. Componentes (detalhe)

### 3.1 Headless Runner (caminho de dados) — `engine/runner.py`
- Executa um agente via subprocesso headless (`claude -p …`, `codex exec …`).
- Captura `stdout`/`stderr`, **verifica `returncode`** (0=ok, ≠0=falha).
- Aplica **timeout** (generoso; Codex pode levar >10 s). Timeout → mata o processo → estado `FAILED`/`NEEDS_INPUT`.
- Concorrência via **asyncio** (`asyncio.create_subprocess_exec`) com **semáforo = teto de agentes** (configurável) **+ lock por sessão** (ver 3.2/§6).
- **Segurança:** aplica a `[headless.permissions]` do adapter — **workspace isolado** (cwd), `--permission-mode acceptEdits` (nunca bypass), `--add-dir`/`--allowedTools` restritos aos caminhos permitidos. *(O spike usou `--dangerously-skip-permissions` só para provar viabilidade; NÃO é o padrão de produção.)*
- Atende FR1(a), FR3(a), FR4(a). *(Fase 0.1/0.2: 100%.)*

### 3.2 Session Manager — `engine/session.py`
- Mantém um **ID de sessão por agente** para continuidade de contexto.
- Claude: `--session-id <uuid>` (1º turno) + `--resume <uuid>` (turnos seguintes).
- Codex: captura/resume via `codex exec resume`.
- Persiste o índice `agente → session_id` (sobrevive a reinício). Atende FR13. *(Fase 0.2: 100%.)*
- **Lock por sessão (correção obrigatória):** **no máximo UMA tarefa ativa por `agent_id`/`session_id`**. Cada sessão tem um mutex; um 2º prompt para a mesma sessão **enfileira** (Task Queue), nunca executa em paralelo — caso contrário o contexto da sessão corrompe. A concorrência do sistema é **entre agentes distintos**, não dentro de uma sessão.

### 3.3 Agent Registry — `engine/registry.py`
- Registra agentes ativos: `id`, `tipo`, `estado` (`idle|busy|error`), `session_id`, perfil.
- Fonte de verdade do estado para o orquestrador e a TUI. Atende FR7.

### 3.4 Agent Adapter (perfil declarativo) — `engine/adapters/`
- Um arquivo por agente (TOML), **sem código no core**. Campos:
  ```toml
  name = "claude"
  [headless]
  cmd          = ["claude", "-p"]
  session_set  = ["--session-id", "{id}"]
  session_resume = ["--resume", "{id}"]
  stdin        = "devnull"          # evita espera de 3s
  output       = "json"             # envelope JSON estrito (ver 3.5)
  [headless.permissions]            # POLÍTICA EXPLÍCITA — sem bypass
  mode         = "acceptEdits"      # claude --permission-mode (NUNCA bypassPermissions)
  workspace    = "{agent_workspace}"  # diretório isolado por agente (cwd do processo)
  allowed_paths = ["{agent_workspace}"]  # --add-dir; escrita só aqui
  allowed_tools = ["Read", "Write", "Edit"]  # --allowedTools mínimo necessário
  # codex equivalente: --sandbox workspace-write -C {agent_workspace} (NUNCA --dangerously-bypass-*)
  [visibility]                       # opcional (modo TUI)
  launch       = ["claude"]
  busy_token   = "esc to interrupt"
  ready_token  = "❯"
  input_mode   = "send-keys"
  onboarding   = []                  # ex.: codex => [["1","Enter"]]
  ```
- Adicionar agente = adicionar um `.toml`. Atende FR6, NFR5.

### 3.5 Envelope (protocolo compacto) — `engine/envelope.py`  *(FR15)*
- Contrato de mensagem agente↔orquestrador em **JSON ESTRITO com schema** (não texto tolerante a ruído):
  ```json
  {
    "v": 1,
    "message_id": "<uuid>",
    "task_id": "<uuid>",
    "from": "<agent_id|orchestrator>",
    "to": "<agent_id|orchestrator>",
    "state": "DONE|BLOCKED|FAILED|NEEDS_INPUT",
    "task": "<linha curta>",
    "result": "<linha curta | null>",
    "artifacts": ["<caminho>", "..."],
    "note": "<opcional, terse | null>"
  }
  ```
- **Validação estrita:** valida contra **JSON Schema**; `state` ∈ enum; campos obrigatórios (`v, message_id, task_id, from, to, state`). **Formato inválido → REJEITADO** (erro `FAILED`, log, retry limitado) — nunca "best-effort".
- **Limite em BYTES** por mensagem (config, ex.: 4 KB). Excedeu → rejeita; artefatos grandes **sempre por caminho** em `artifacts`, nunca inline.
- `message_id`/`task_id` dão **rastreabilidade** e **idempotência** (deduplicação).
- A engine instrui o agente a **responder SOMENTE com este JSON** (via `--output json`/prompt-wrapper) e valida. *(Fase 0.2 validou parse de envelope 100% em formato textual; produção endurece para JSON estrito — mais confiável.)*

### 3.6 Message Bus — `engine/bus.py`
- Roteia envelopes entre orquestrador e agentes de forma **desacoplada** (pub/sub interno em memória; assíncrono).
- Não conhece CLIs — fala só Envelope. Atende FR8.

### 3.7 Task Queue — `engine/queue.py`
- Enfileira tarefas de delegação; entrega ao agente quando ele está `idle` (Registry).
- Suporta entrega assíncrona e callback de resultado. Atende FR9.

### 3.8 Completion/Idle Detector — `engine/detector.py`
- **Headless:** fim do processo + `returncode` (determinístico) — padrão.
- **Visibilidade (TUI):** estado-da-TUI working→idle (`busy_token` some) → sentinel → quiescência → timeout.
- Atende FR4.

### 3.9 Orchestrator — `engine/orchestrator.py`
- Recebe a intenção, **decompõe** em tarefas (MVP: roteamento simples/explícito), **delega** via bus, **extrai** a resposta (envelope), **encaminha** ao próximo agente, **agrega**.
- Política de escalonamento ao humano (gates): em `BLOCKED`/`NEEDS_INPUT`/`FAILED` repetido → sinaliza à UI. Atende FR5, FR10.
- (Pós-MVP: decomposição inteligente, papéis Lead/Coder/Reviewer/Tester — cf. pesquisa 02.)

### 3.10 tmux Observability — `visibility/tmux.py` (opcional)
- Exibe o **stream/log da execução headless** num pane tmux para o humano acompanhar/auditar (`tmux attach`).
- **NÃO** é uma TUI interativa do agente espelhada automaticamente; o agente **não roda duas vezes**. É puramente observabilidade da execução headless (mesma fonte do log).
- O caminho interativo de detecção (estado-da-TUI/`busy_token`) só se aplica se, no futuro, um modo interativo dedicado for adicionado — fora do MVP.

### 3.11 TUI — `tui/app.py`
- Lista agentes/estado, dispara delegação, acompanha respostas; teclado físico, 1280×720.
- Consome a engine por API interna (sem acoplamento). Atende FR11.
- Stack sugerida: **Textual** ou **prompt_toolkit** (Python, leve).

### 3.12 Persistence / Logs — `engine/state/`
- Estado externo (cf. pesquisa 02): índice de sessões, fila/estado de tarefas, **log de handoffs/envelopes**. Atende FR12.
- **Persistência segura (correção obrigatória):** **SQLite** (transacional, locking nativo, modo WAL) como armazenamento de sessões/tarefas/logs. *(Alternativa: escrita JSON atômica via `tmp+rename` com **processo escritor único**.)* **Proibido** escrita JSON concorrente direta — corrompe tarefas/sessões.
- Acesso ao estado é mediado por uma única camada (`engine/state/store.py`); writers concorrentes passam por transações SQLite.

---

## 4. Modelos de dados

```python
Envelope (JSON estrito): v, message_id, task_id, frm, to,
          state(DONE|BLOCKED|FAILED|NEEDS_INPUT), task, result,
          artifacts[list[path]], note   # validado por JSON Schema; limite em bytes
AgentProfile (TOML): name, headless{permissions{mode,workspace,allowed_paths,allowed_tools}}, observability{...}
AgentRecord: id, type, state(idle|busy|error), session_id, profile_ref, last_seen
Task: id, intent, target_agent|route, status(queued|running|done|failed), result_envelope, attempts
SessionIndex: { agent_id: session_id }      # SQLite
SessionLock: { session_id: busy? }          # 1 tarefa ativa por sessão
```
Armazenamento: **SQLite** (WAL) para SessionIndex, Tasks e log de Envelopes.

---

## 5. Fluxo de execução — delegação A→B (sequência)

```
Orchestrator: cria Task(intent) → Envelope(to=A, task=...)
   → Bus → Adapter(A).headless → Runner: claude -p --resume <sidA> "<prompt+wrapper envelope>"
        ↳ returncode==0 → parse Envelope(state=DONE, result=R, artifacts=[...])
   → Orchestrator: extrai R → Envelope(to=B, task=usar R / ler artifact path)
   → Bus → Adapter(B).headless → Runner: codex exec resume <sidB> "<...>"
        ↳ returncode==0 → parse Envelope(state=DONE, result=R2)
   → Orchestrator: agrega → Task.done
   (qualquer FAILED/timeout → registra, não trava; escala se necessário)
```
Artefatos grandes: A escreve em `./artifacts/...`, passa `artifacts: <path>`; B lê pelo caminho (validado na Fase 0.2).

---

## 6. Concorrência, recursos e erros

- **Modelo:** asyncio + **semáforo (teto de agentes)** entre agentes distintos + **mutex por sessão** (1 tarefa ativa por `agent_id`/`session_id`). *(Fase 0.2: 3 paralelos 100%.)*
- **Sessão:** prompts concorrentes à mesma sessão são **serializados via fila** (nunca paralelos) — proteção de integridade do contexto.
- **Recursos:** RAM folgada (Fase 0.1: 4 ativos ≥ 1699 MB livres); teto evita saturar CPU.
- **Erros:** `returncode≠0` → `FAILED`; timeout → kill + `NEEDS_INPUT`/`FAILED`; envelope inválido → `FAILED`; retry limitado; orquestrador nunca bloqueia (NFR7).

---

## 7. Stack & estrutura de diretórios

**Stack:** Python 3.13 · asyncio · **SQLite (WAL)** para estado · tmux 3.6b (observabilidade) · Textual/prompt_toolkit (TUI) · TOML (perfis) · **jsonschema** (validação do envelope). Sem binários nativos. *(Reavaliar Go/Rust no core só se o consumo exigir — cf. brief.)*

```
maestri-console/
  maestro/
    engine/  runner.py session.py registry.py bus.py envelope.py
             queue.py detector.py orchestrator.py
             schema/  envelope.schema.json
             state/  store.py            # única camada de acesso ao SQLite
             adapters/  base.py claude.toml codex.toml
    visibility/  tmux.py                  # observabilidade do headless
    tui/  app.py
    state/  (maestro.db [SQLite WAL], logs/)
    config/  default.toml
  spike/        # código descartável das Fases 0/0.1/0.2 (referência)
  docs/         # pesquisas
  _bmad-output/planning-artifacts/   # brief, prd, arquitetura, spikes
  tests/
  README.md  LICENSE(MIT)  pyproject.toml
```

---

## 8. Rastreabilidade FR/NFR → componente

| Req | Componente |
|---|---|
| FR1, FR3, FR4 | Runner + Detector (headless) / tmux Visibility |
| FR2 | Runner (headless args/stdin) / tmux (send-keys) |
| FR5, FR10 | Orchestrator |
| FR6 | Agent Adapter |
| FR7 | Registry |
| FR8 | Message Bus |
| FR9 | Task Queue |
| FR11 | TUI |
| FR12 | Persistence/Logs |
| FR13 | Session Manager |
| FR14 | Runner + Filesystem (artefatos por path) |
| FR15 | Envelope |
| NFR1/2/3 | Runner + Concorrência (semáforo/teto) |
| NFR5 | Adapter (TOML) |
| NFR6 | Engine/UI desacoplados |
| NFR7 | Runner/Detector (timeout/returncode) |

---

## 9. Decisões arquiteturais (ADR resumido)

> **Fonte canônica/versionada dos ADRs: `docs/ADR.md`** (rastreado pelo git). Este `_bmad-output/`
> é GITIGNORED, então os ADRs foram movidos para `docs/ADR.md` em 2026-06-26 para terem
> histórico. O resumo abaixo é um espelho de conveniência — ao adicionar/alterar um ADR,
> edite `docs/ADR.md` (a verdade) e, se quiser, reflita aqui.

- **ADR-1:** Headless como caminho de dados (vs. raspar TUI). *Motivo:* 100% confiável, sem ANSI/eco. *Trade-off:* TUI vira só visibilidade.
- **ADR-2:** Orquestrador-mediado (vs. agente↔agente direto estilo Maestri). *Motivo:* robustez, controle, escalonamento.
- **ADR-3:** Python + asyncio no MVP (vs. Go/Rust). *Motivo:* velocidade de prototipagem, validado no spike; reavaliar core depois.
- **ADR-4:** Perfis TOML declarativos (vs. código por agente). *Motivo:* extensibilidade sem tocar no core.
- **ADR-5:** Sessões persistentes via `--resume` (vs. stateless ou prompt gigante). *Motivo:* contexto multi-turno barato; validado.
- **ADR-6 (segurança) [revisado E2-S2]:** Confinamento real via **bwrap** (workspace rw, `/tmp` privado tmpfs, resto read-only, rede mantida, config/sessão do agente rw), **fail-safe** se ausente. As flags de CLI (`--permission-mode acceptEdits` / `--sandbox workspace-write`) só evitam prompts — **não** confinam (teste real provou que `acceptEdits` sozinho escreve em `/tmp`; o limite efetivo é o bwrap). Sem `--dangerously-*`. *Motivo:* isolamento é fundação (multi-agente + publicação); flags de CLI dariam garantia falsa.
- **ADR-7 (protocolo):** Envelope em **JSON estrito validado por schema** (vs. texto tolerante). Campos `message_id`/`task_id`, limite em bytes, **rejeição de formato inválido**. *Motivo:* falhar alto > corromper silenciosamente; rastreabilidade/idempotência.
- **ADR-8 (concorrência):** **Mutex por `agent_id`/`session_id`** — 1 tarefa ativa por sessão; concorrência só entre agentes distintos. *Motivo:* prompts paralelos na mesma sessão corrompem contexto.
- **ADR-9 (persistência):** **SQLite (WAL)** (ou JSON atômico com escritor único). *Motivo:* escrita JSON concorrente direta corrompe estado; SQLite dá transações/locking.
- **ADR-10 (interop/bridge — futuro, condicional) [2026-06-25]:** Avaliado *driving* de CLIs interativas (raspar PTY/TUI) para uma eventual **interop multi-ferramenta** (estilo Maestri: Claude↔Codex↔OpenCode entre terminais). **Decisão:** o caminho de dados **permanece headless + orquestrador-mediado (reafirma ADR-1 e ADR-2)** — raspar PTY **não** é caminho de dados confiável nem porta o Envelope JSON. *Se* a interop com agentes externos que só expõem TUI for adotada, será um **adapter OPCIONAL e ISOLADO** (Camada Anticorrupção — regra 5 de stack durável), tratado como bridge *best-effort*/visibilidade, com **detecção de quiescência explícita** (sentinela), nunca como protocolo confiável.
  - **Mecanismo escolhido (se/quando):** **tmux** (`send-keys` + `capture-pane`) — robusto/battle-tested para TUIs full-screen.
  - **Alternativas rejeitadas:** **pexpect** (ANSI de TUI quebra o rendering — partial/broken); **tmux-bridge** (é *human-in-the-loop* p/ sudo/auth, não turno autônomo); **agente↔agente direto como caminho primário** (já rejeitado no ADR-2; reforçado pelo *echoing* — colapso de identidade multi-agente, arXiv 2511.09710).
  - **Risco registrado:** a interop heterogênea da Maestri é **afirmada mas não testada** (demos só Claude↔Claude) — não tratar como pronta.
  - **Longevidade verificada (consulta 2026-06-25, via pesquisa da sessão):** *tmux* — ativo, maduro, battle-tested. *pexpect 4.9.0* (lançado 25/nov/2023; major anterior 4.8.0 em jan/2020 → cadência lenta ~3–4 anos; Production/Stable; depende de `ptyprocess>=0.5`). Nenhum é dependência do core hoje. *Motivo:* falhar alto > corromper silenciosamente; isolar o volátil; não reabrir fundação sem necessidade comprovada. Imutável (mudança = novo ADR).
- **ADR-11 (cabos interativos — skill `ask` iniciada pelo agente, mediada pelo host) [2026-06-25]:** Para reproduzir o "cabo que conversa" do Maestri SEM abrir mão da robustez, adota-se um modo **interativo iniciado pelo agente e mediado pelo host** (variante "a" da pesquisa): ligar o cabo A→B instala uma **skill de CLI agnóstica** (`maestro-ask B "<prompt>"`) que o agente A chama de dentro do seu terminal ao vivo; o host roteia via **`controller.delegate` (headless + bwrap + Envelope)** e devolve a resposta. **Decisão:** isto **NÃO é raspagem de PTY** (distinto do ADR-10) e **mantém o caminho de dados mediado** (reafirma ADR-1/2/6/7) — a única novidade é a *iniciativa* do handoff passar do humano/orquestrador para o **agente**, com guardrails. A variante "raspar o terminal vivo de B" (visibilidade ambos-ao-vivo) fica **adiada**; quando feita, recai no ADR-10 (bridge isolado/best-effort).
  - **Transporte:** *mailbox* de arquivos (req/resp JSON) num dir montado rw via o `shared_paths` **já existente** do bwrap — vs Unix socket. *Motivo:* reusa a montagem de sandbox atual, zero plumbing novo, stdlib.
  - **Identidade do remetente:** `--setenv MAESTRO_NODE <nó>` no bwrap; o cliente lê do env.
  - **Sessão do destino (MVP):** sessão **efêmera** no `delegate` do ask (vs resumir a sessão interativa de B) — evita contenção com o mutex por-sessão do terminal vivo (ADR-8); reavaliar "responder em contexto" depois.
  - **Guardrails obrigatórios** (pesquisa: *echoing* 5–70% a partir do turno ~7, arXiv 2511.09710): **limite de turnos por cabo**, **refresh de identidade (~3 turnos)**, **anti-loop A↔B (teto de profundidade)**, teto de bytes (reusa o limite do Envelope), e input do outro agente tratado como **não-confiável** (já roda em bwrap).
  - **Stack/longevidade (verificada 2026-06-25):** reusa a stack atual (Python + GTK4/VTE 0.84, mantida); mailbox = stdlib (sem dependência nova no MVP). Detalhes em `docs/05-pesquisa-cabos-interativos.md`. Imutável (mudança = novo ADR).
- **ADR-12 (canvas infinito — modelo câmera + container) [2026-06-26]:** O canvas nativo usa **modelo de câmera** (`tela = base·zoom + cam`; sem parede), com os filhos posicionados por `Gtk.Fixed.set_child_transform` e a câmera (`self._cam`) movida no pan. **Container = `Gtk.ScrolledWindow` em policy `EXTERNAL`** (NÃO `NEVER`). *Motivo:* com `NEVER` o ScrolledWindow não rola e por isso exige o **mínimo INTEIRO do filho**; como o `Gtk.Fixed` mede a caixa dos filhos incluindo o transform (câmera assada), o mínimo crescia ao panar e **empurrava o toplevel** (janela inchava/saía da tela; maximizar quebrava). `EXTERNAL` rola programaticamente (sem barra) e **recorta na viewport** → a câmera dá alcance infinito sem crescer a janela. Complemento: `Viewport.set_scroll_to_focus(False)` (evita deslize ao focar um filho). **Validado em runtime no CM4** (5+ min de pan/zoom, sem OOM de GPU) — **reverte o "adiado pro CM5"** (a inviabilidade anterior era GPU contaminada por crash prévio, não limite real).
  - **Lição (rejeitado):** sobrescrever `do_measure` numa subclasse de `Gtk.Fixed` p/ capar o tamanho **NÃO funciona** (é ignorado — `GtkFixedLayout` segue medindo os filhos); a alavanca correta é a **policy do ScrolledWindow**.
  - **Entrada de pan:** no uConsole, **SELECT + trackball gera eventos de scroll** (firmware/X11, ver `docs/uconsole.md`/INVENTARIO); um `Gtk.EventControllerScroll` traduz os deltas em movimento de câmera (pan suave, sem clicar).
  - **Seleção + roteamento de scroll:** clicar seleciona nó/nota/árvore (borda azul tracejada via `outline`); o controller de scroll roda na **fase CAPTURE** → o pan é interceptado antes do VTE e **nunca é roubado** ao passar sobre uma janela; o scroll só "entra" no elemento **selecionado e sob o cursor** (ex.: scrollback do terminal).
  - **Método de diagnóstico (registro):** a causa-raiz só fechou com **medição ao vivo** (`xprop`/`xwininfo` + log de `measure()` por frame). Teoria, percepção, um workflow multi-agente e teste via `xdotool` deram **falsos resultados** — lição: medir o estado real cedo. Imutável (mudança = novo ADR).

---

## 10. Futuro (pós-MVP)

- **Web UI** (canvas com nós/cabos) sobre a mesma engine (servidor local → notebook/celular).
- **Agente local/offline** (SLM via ollama/llama.cpp) como novo adapter → caminho para offline real.
- Papéis (Lead/Coder/Reviewer/Tester), memória compartilhada avançada, skills, auditoria.

---

## 11. Próximo passo

→ **Epics & Stories** (`bmad-create-epics-and-stories`), derivando os 5 épicos do PRD + as stories não-bloqueantes (VS-1, VS-2), depois **roadmap/sprint planning**.
