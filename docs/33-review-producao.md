# Review de prontidão pra produção — por fases (doc vivo)

> **Objetivo:** responder "está realmente pronto pra produção real?" com evidência, não impressão.
> "Produção" aqui = app single-user rodando no uConsole CM4 do dono: funciona de verdade no
> device, não perde dado, o sandbox segura agente hostil, se recupera de crash.
> **Método:** 7 fases (docs → código → segurança → testes → runtime no device → UX por estado →
> veredito adversarial Fable), cada uma com relatório aqui. Achado vira fix ou item de fila —
> nunca "anotado e esquecido". Nível escolhido pelo usuário: **avançado (todas as fases)**.
> Iniciado: 2026-07-18 · baseline **v0.67.0** (`2a6c77a`).

---

## Fase 1 — Verdade dos docs (drift docs↔código) — ✅ CONCLUÍDA 2026-07-18

**Método:** leitura direta dos docs-âncora + 3 verificadores independentes em paralelo
(STATUS.md↔código · CHANGELOG↔git · ADR-1..29↔código), cada um reportando só divergência
com evidência `file:line`.

### Veredito da fase

**Os docs são substancialmente VERDADEIROS.** Nenhuma feature afirmada que não exista; nenhum
ADR violado no código atual — incluindo TODOS os invariantes de segurança (ADR-17/18/21/22/23/
25/26/27/28/29) e os 19 testes-prova citados, todos presentes. O drift encontrado é de
**contadores/carimbos não re-atualizados** (padrão claro: conteúdo novo entra certo; os ranges
"v0.X→v0.Y / ADR-1..N" dos docs-âncora ficam congelados) + 1 achado de processo (tags).

### Achados (A1..A10)

| # | Sev | Onde | O que |
|---|-----|------|-------|
| A1 | 🟡 média | `docs/index.md` (cabeçalho + linhas canônicas) | Diz "Atualizado: 2026-07-02 (v0.51.0)", "CHANGELOG v0.1.0→v0.51.0", "ADR-1..20". Real: v0.67.0, ADR-1..29. O PR #89 adicionou as linhas 27-32 mas não re-carimbou o cabeçalho. |
| A2 | 🟡 média | `docs/index.md` (3 linhas de estado) | docs/19: "Bloco D (budget cap) **pendente**" → entregue v0.55.0/ADR-22. docs/21: "**pronto pra virar stories**" → entregue v0.56.0/ADR-23. docs/08: "medidor de custo **segue não entregue**" → entregue v0.54.0. O mapa afirma como faltando o que já existe. |
| A3 | 🟡 média | `docs/STATUS.md:48` | "Fontes canônicas: CHANGELOG (v0.1.0→**v0.55.0**) e ADR (**1..22**)" — 12 versões e 7 ADRs atrás; contradiz o topo do mesmo doc (v0.67.0). |
| A4 | 🟢 baixa | `docs/STATUS.md:185` | "554 testes (+19 skip)" — medido hoje: **605 coletados só no venv** (96 arquivos; os módulos gi nem entram nessa coleta) e ~16 marcadores reais de skip. Contador congelado de versão antiga. |
| A5 | 🟢 baixa | `docs/architecture.md` (nota do topo) | "ADRs canônicos e completos (ADR-1..**15**)" — contador congelado (29). |
| A6 | 🔵 processo | git tags | Última tag: **v0.46.0**. As 21 versões v0.47.0→v0.67.0 não têm tag (além de buracos antigos: 0.5-0.6, 0.13.0, 0.19-0.25, 0.26.0, 0.27-0.32, 0.37.0, 0.37.2). A política "tag SemVer só em release" nunca definiu o que conta como release → na prática o tagging parou. Decisão do usuário: retomar (e de onde), ou declarar formalmente que tag ficou opcional. |
| A7 | ⚪ registro | commits `#48`/`#49` | Mensagens carimbaram "v0.49.0" em trabalho que o CHANGELOG registra (corretamente) como 0.50.0/0.51.0. Histórico imutável — só registrar, nada a fazer. |
| A8 | 🟢 baixa | `CHANGELOG.md` (formato) | Cabeçalho promete "Keep a Changelog / Datas em 2026", mas nenhuma entrada carrega data. Ou datar as próximas, ou ajustar a promessa do cabeçalho. |
| A9 | ⚪ registro | `docs/STATUS.md` (precisão) | A lógica de `<ws>/pastes/` vive em `canvas.py` (`_pastes_dir`, ~5388), não em `paste.py` (que cuida de nome/quote/cap). Comportamento correto; só a localização difere do que o texto sugere. |
| A10 | 🟢 higiene | `.claude/worktrees/docs-paste-imagem/` | Worktree órfã da feature v0.67.0 já mergeada — remover (`git worktree remove`). |

### Confirmado OK (agregado)

- **CHANGELOG:** continuidade perfeita v0.1.0→v0.67.0 (67 minors + patches, ordem estrita),
  topo = pyproject, todo feat/fix mergeado tem entrada, nenhuma data impossível.
- **STATUS.md:** todos os 12 módulos citados existem com o papel citado; todos os 13 símbolos
  citados existem; comportamentos verificáveis (bwrap estrito, `--unshare-pid`, SIGKILL no
  unload, socket por agente, `CLAUDE_CONFIG_DIR`/`CODEX_HOME`, cap 8192px) conferem;
  SSH remoto de fato NÃO implementado (só placeholder "soon").
- **ADR-1..29:** zero violação. Spot-checks profundos passaram: sandbox fail-safe sem
  `--dangerously-*` default (ADR-6/19); socket pathname + nunca montar o pai das boxes
  (ADR-17); autoridade só por `_recruited_by`/`_own_recruit`, líder sem autoridade (ADR-18/21);
  `record_spend` monotônico + `budget_blocked` fora de `ABUSE_EVENTS` (ADR-22); SIGKILL +
  anti-race (ADR-23); dirty-flag + SIGTERM/SIGHUP→quit (ADR-25); `escalated_budget` + gate no
  LIVE (ADR-26); brief re-carimbado, sanitizado, nunca lido de volta (ADR-27); substituição de
  rw_paths + máscara tmpfs em todo spawn + resolvedor único nos 4 pontos de argv (ADR-28);
  nome hostil nunca toca o PTY + injeção sem `\r` (ADR-29).
- **prd.md / architecture.md:** notas de defasagem presentes e honestas (exceto A5).

### Fixes — estado

1. ✅ **Aplicado (2026-07-18, nesta branch):** `index.md` re-carimbado (cabeçalho v0.67.0,
   ADR-1..29, estados de docs/19/21/08 corrigidos pra "entregue").
2. ✅ **Aplicado:** `STATUS.md:48` (range → v0.67.0 / ADR-1..29) e `:185` (605+ testes medidos).
3. ✅ **Aplicado:** nota do `architecture.md` → ADR-1..29.
4. ✅ **Aplicado:** worktree órfã `.claude/worktrees/docs-paste-imagem` removida (limpa,
   conteúdo mergeado no PR #89) + branch local `docs/index-27-32` deletada.
5. ✅ **A6 decidido pelo usuário (2026-07-18): tagging retomado "daqui pra frente"** — tag
   anotada `v0.67.0` criada em `e74041b` (convenção antiga: tag no squash do PR de release)
   e publicada no origin. As 20 versões v0.47.0→v0.66.0 ficam sem tag retroativa (decisão:
   seguir dali, não backfill). Releases futuras voltam a taggear no merge.
6. ✅ **A8 decidido pelo usuário (2026-07-18): entradas novas do CHANGELOG são DATADAS**
   daqui pra frente (`## [X.Y.Z] — AAAA-MM-DD — resumo`, a partir da v0.68.0; sem retroagir
   nas ≤0.67.0). Convenção registrada no cabeçalho do CHANGELOG e na regra "Antes do PR"
   do `AGENTS.md`.

---

## Fase 2 — Código (correctness) — ✅ CONCLUÍDA 2026-07-18

**Método:** workflow multi-agente (23 agentes, ~37 min) — 7 caçadores Opus (um por área:
engine/orquestração, budget+contas, sandbox/socket, ciclo de vida do nó, persistência de UI,
paste/ask, interfaces secundárias) → cada achado bruto passou por **refutação adversarial
individual do Fable** (instrução: na dúvida, refutar). 16 brutos → **14 confirmados, 2
refutados** (1 por definição do protocolo ADR-7; 1 por medição em runtime GTK sob Xvfb).
Dedup: 2 pares de áreas acharam o mesmo bug → **12 bugs únicos**.

### Veredito da fase

O núcleo orquestrador/sandbox/budget saiu **limpo nos caminhos principais** (nenhum bug no
delegate/envelope/mutex/sandbox em si). Os bugs reais se concentram em **(a) reciclagem de id
de nó** (limpeza incompleta ao fechar), **(b) routines** (reentrância + lost update) e
**(c) guards que existem num caminho mas faltam no irmão** — o mesmo padrão-classe que os
ADR-18/21/26 já tinham fechado em outros pontos ("invariante em TODAS as entradas").

### Bugs confirmados (C1..C12)

| # | Sev | Onde | O que |
|---|-----|------|-------|
| C1 | 🔴 alta | `engine/routines.py:104` (+`canvas.py:7928`, achado 2×) | Routine cujo run dura > 30s (tick) é **re-disparada concorrentemente** — `last_run` só grava no fim e não há guarda "já rodando": prompt roda N×, `run_count` infla, custo multiplica. |
| C2 | 🔴 alta | `canvas.py:2639` (achado 2×) | **`_close_node` limpa só `session/unloaded/orphan`** — `account`, `maestro`, `autoapprove`, `role`, `command`, `cwd`, `env`, `birth_group` + nome/posição/tamanho ficam órfãos; como `_unique_nid` **recicla o id**, um nó novo **herda credencial de conta e permission-bypass** do nó fechado. |
| C3 | 🔴 alta | `canvas.py:4898` | **`_kill_all_agents` não aplica o guard anti-race do ADR-23** (zera `_respawn_state`/`_respawn_pending`, cancela `_respawn_force_src`) que o `_unload_node` aplica — respawn em voo **ressuscita nó após o kill-switch** (backstop do ADR-17 derrotado pela race). |
| C4 | 🟡 média | `engine/routines.py:106` | `run_routine_once` grava o objeto Routine INTEIRO com snapshot velho → **pause do usuário durante o run é revertido** (lost update de `enabled`). |
| C5 | 🟡 média | `engine/budget.py:51` | `record_spend` só detecta rotação de sessão quando `new < last`; sessão nova com 1º turno ≥ total da anterior cai no ramo "continuação" e **subconta** (brecha na garantia anti-laundering do ADR-22; `budget_last_*` nunca é limpo). |
| C6 | 🟡 média | `engine/ask_sock.py:217` | `Thread.start()` sem try em `_accept`: falha de criação de thread (pressão de RAM no CM4) **mata o accept-loop permanentemente** + vaza permit do semáforo e o fd. |
| C7 | 🟡 média | `canvas.py:8239` | `_acct_cfg_dir` chama `accounts.resolve` **sem o `base`** (único ponto divergente): contas homônimas em agentes diferentes → config-dir errado → **crash não marca o nó como órfão**. |
| C8 | 🟡 média | `canvas.py:5428` | Guard `MAX_DIM` (E4 anti imagem-bomba) roda **DEPOIS do decode completo** da textura — não previne a alocação que existe pra impedir. |
| C9 | 🟡 média | `engine/floors.py:89` | Floors **sem escopo por projeto** (tabela keyed só por `name`): run/merge de floor pode operar **no repo errado**. |
| C10 | 🟢 baixa | `engine/accounts.py:178` | `resolve()` de conta órfã re-sintetiza `slug=slugify(name)` ignorando sufixo de colisão congelado pelo `add_account` → pode apontar pro **config-dir de OUTRA conta**. |
| C11 | 🟢 baixa | `canvas.py:5420` | TOCTOU no paste: o callback async não re-checa `unloaded/_destroyed` → guard E2 derrotado, injeção em terminal morto. |
| C12 | 🟢 baixa | `engine/workspace_registry.py:87` | Workspace nomeado `..` passa no `_SAFE_NAME` e `db_path('..')` resolve pro **DB default** — isolamento de estado quebrado. |

**Refutados (registro):** envelope >4KB re-rodando agente (é o comportamento definido pelo
ADR-7 — falhar alto); nota "perde corpo se fechar sem blur" (refutado por **medição em
runtime**: `win.close()` emite o blur e persiste).

### Priorização proposta (fixes = branches próprias, fora desta)

- **P0 (bloqueia o selo "produção"):** C2 (herança de credencial/bypass por id reciclado),
  C3 (kill-switch derrotável por race), C1 (routine runaway = custo real multiplicado).
- **P1:** C4, C5, C6, C7, C8, C9.
- **P2 (oportunista):** C10, C11, C12.
- C2+C3+C7 são o mesmo tema (ciclo de vida/limpeza do nó) → candidatos a 1 branch `fix/`;
  C1+C4 idem (routines); C5+C10 idem (budget/contas).
## Fase 3 — Segurança — ✅ CONCLUÍDA 2026-07-18

**Método:** workflow multi-agente (17 agentes, ~30 min) — 6 lentes de ataque Opus (fuga de
sandbox, spoof de identidade/autoridade, injeção PTY/in-band, credencial entre contas,
FS/TOCTOU/recurso, exfil/rede) com o **modelo de ameaça correto injetado** (adversário = agente
sequestrado, NÃO o dono; riscos residuais aceitos no ADR-17/28/29 não contam) → cada achado
refutado individualmente pelo Fable. 11 brutos → **8 confirmados, 3 refutados**. Dedup: o
crítico foi achado por 2 lentes; 2 médios cruzam com a Fase 2 (C7/C8). **Net: 1 crítico +
3 alta + 1 média novos.**

### ⚠ Veredito da fase

**Achado 1 bug CRÍTICO que reabre o confused-deputy que os ADR-18/21 declararam fechado — e
foi PROVADO em runtime.** O Maestro mode **não está pronto pra produção** com esse buraco
aberto. Ressalva importante de contexto: o Maestro mode é **flag default-OFF** e o próprio
ADR-17 condiciona ligá-lo a "passar em red-team adversarial por etapa (forjar `frm`...)" —
este red-team **reprovou**, então a trava default-OFF é o que segura o risco hoje. O núcleo
sandbox em si (confinamento de escrita, fail-safe) continua sólido; o furo é no **transporte
de identidade**, não no isolamento de FS.

### Bugs de segurança confirmados (S1..S6)

| # | Sev | Onde | O que |
|---|-----|------|-------|
| **S1** | 🔴 **CRÍTICA** | `engine/sandbox.py:65` (2 lentes) | **`--ro-bind / /` reexpõe as boxes IRMÃS do ask-bus** (que vive sob `$HOME`, não mascarado). Um agente sequestrado faz `listdir(<bus>/box)` (enumera os nós vítimas), `connect(<bus>/box/<vítima>/sock)` — **conexão a socket pathname NÃO é bloqueada pelo mount read-only** — e o host carimba `frm=vítima` pelo listener que aceitou. Efeito: emite `dismiss`/`reassign`/`recruit`/`wire` **como a vítima**, usando a linhagem host-only dela. **Colapsa o invariante-mãe do ADR-17** ("a segurança vem da AUSÊNCIA do mount das boxes irmãs" — FALSO: o `--ro-bind / /` monta tudo). **Provado em runtime** com os flags reais (`connect OK, reply: HOST-STAMPED frm=victim`). Lê também o `audit.jsonl` (linhagem completa). **Fix é o padrão E5 já usado nas contas:** tmpfs-mascarar `<bus>/box` antes de bindar só a própria box por cima — aplicado às contas, esquecido no bus. |
| **S2** | 🔴 alta | `engine/briefs.py:78` | **Stamp de brief/role segue symlink plantado pelo agente** no workspace → o **host** escreve fora do sandbox (o workspace é rw pro agente; ele troca `CLAUDE.md` por symlink→`~/.bashrc` e o re-carimbo do host escreve no alvo). Reintroduz a **escrita arbitrária no host** que o ADR-17 eliminou ao trocar mailbox-de-arquivo por socket. |
| **S3** | 🔴 alta | `native/canvas.py:2088` | **Roles descobertos do cwd** (conteúdo controlado pelo agente) entram na biblioteca e são gravados no `CLAUDE.md`/`AGENTS.md` da vítima **SEM a sanitização de Unicode invisível** que o `briefs.py` aplica → **Rules File Backdoor cross-agent** (zero-width/bidi escondem instrução de LLM — a mesma classe que o ADR-27 fechou pro brief, aberta pro role descoberto). |
| **S4** | 🔴 alta | `web/server.py:195` | **Control-plane web sem token no bind localhost** (`/api/execute`, `/api/teams`, `/api/resume`): um agente co-local (netns compartilhado — os agentes têm rede) alcança o loopback e **forja autoridade fora do host**, contornando toda a cadeia socket/linhagem. Só vale com a Web UI opcional ligada. |
| **S5** | 🟡 média | `native/canvas.py:4417` | **Modo LIVE injeta o prompt do cabo (controlado pelo agente) no PTY do vizinho sem o filtro E1** de control chars — só paste/drop aplica `injectable()`. Um `\r` na resposta do cabo = auto-submit no terminal da vítima (a regra E1 do ADR-29 não foi aplicada a ESTE caminho de injeção). |
| **S6** | 🟡 média | `native/canvas.py:8239` / `:5428` | **Cross-confirma C7 e C8 da Fase 2** por ângulo de segurança: `_acct_cfg_dir` sem `base` (orphan lê config-dir errado) e cap de imagem-bomba checado após o decode (400MB já alocados). Dois achados, duas fases → prioridade reforçada. |

**Refutados (corretos, registro):** ler o `~/.claude` do **próprio dono** via `--ro-bind / /`
(baseline aceito do ADR-6 — sandbox confina escrita, não leitura; egress é risco aceito do
ADR-17); credencial **entre contas registradas** (esse isolamento É imposto — máscara tmpfs E5
cobre a raiz das contas); SSE `/api/events` cross-nó (o RunManager roda 1 equipe por vez e o
`output_bus` é canal de visualização do dono, não caminho de dados mediado). As 3 refutações
foram verificadas como consistentes com o S1: o que vaza é o **bus** (não mascarado = bug), não
os dirs de conta (mascarados = ok).

### Priorização

- **P0 absoluto:** **S1** — bloqueia qualquer uso do Maestro mode; fix é padrão conhecido
  (tmpfs no bus). Até corrigir, **manter Maestro mode OFF** (a trava default-OFF já segura).
- **P0:** S2 (escrita arbitrária no host via symlink) — vale mesmo SEM Maestro mode (brief/role
  é feature geral); S3 (backdoor de role cross-agent).
- **P1:** S4 (token no control-plane web), S5 (filtro E1 no cabo LIVE).
- Já mapeado na Fase 2: S6 = C7 + C8.
## Fase 4 — Testes (ponto cego dos skipados) — ✅ CONCLUÍDA 2026-07-18

**Método:** rodar TODAS as suítes nos dois ambientes reais (o CI só roda o venv gi-free) +
caçar a lacuna de cobertura que deixou o S1 passar.

### Resultados de execução

| Ambiente | Resultado |
|---|---|
| **venv** (gi-free, = o que o CI roda) | **599 passa, 26 skip** (625 coletados) em 60s |
| **python do sistema** (gi/GTK4 canvas — CI PULA via `importorskip`) | **193 passa** em 3.5s (sob Xvfb) |
| **`sandbox_live` drill** (bwrap real, `MAESTRO_LIVE=1`) | **1 passa** em 30s — confinamento real funciona |

**Veredito:** o ponto cego do CI (193 testes de canvas que rodam só no python do sistema) está
**VERDE** — nada podre escondido lá. A suíte é saudável. Total real ≈ **818 testes** (625 venv
+ 193 gi), bem acima do "554" que o STATUS dizia (corrigido na Fase 1).

### Achados

| # | Sev | O que |
|---|-----|------|
| T1 | 🔴 alta | **Lacuna de cobertura que deixou o S1 passar:** `test_ask_sock.py` testa que o host carimba a identidade pelo LISTENER (`test_identidade_vem_do_canal_nao_do_payload`) — mas **nenhum teste verifica o invariante-mãe do ADR-17**: que um agente NÃO alcança o socket de outro. Os testes montam sockets no mesmo fs, sem bwrap/`--ro-bind / /`, então a premissa "boxes isoladas pela ausência de mount" **nunca foi exercitada** — exatamente a premissa que o S1 falsificou. Todo fix do S1 DEVE vir com um teste de isolamento de box sob sandbox real. |
| T2 | 🟢 baixa | 26 skips no venv são **legítimos** (gi-gated + `*_live` opt-in), não testes quebrados — todos rodam e passam no ambiente certo. O "+19 skip" do STATUS estava defasado (real: 26). |
| T3 | ⚪ registro | Deprecation `GLib.unix_signal_add_full` (PyGI) e `NotAppKeyWarning` (aiohttp) — ruído, não falha; anotar pra limpeza futura. |

**Nota de honestidade:** os `*_live` de rede (`orchestrator_live`, `session_live`,
`realtask_live`) NÃO foram rodados (precisam de CLI de agente logado + rede) — ficam como
cobertura opt-in não exercitada neste review; o `sandbox_live` (o mais relevant p/ segurança)
foi rodado e passou.
## Fase 5 — Runtime no device — ✅ PARCIAL (subconjunto headless rodado por mim) 2026-07-20

**Método:** em vez de empurrar o roteiro inteiro pro usuário (lição "testar eu mesmo em runtime
antes de declarar pronto"), dirigi o **canvas GTK real sob Xvfb** (`canvas_harness` + `CanvasWindow`
real, python do sistema) para o subconjunto que é state-machine/persistência — em especial os
cenários que **reproduzem os bugs**. Cada teste asserta o comportamento CORRETO → falha = bug
reproduzido no runtime, não só na leitura. Harness em `scratchpad/fase5_repro.py`.

### 🔴 Os 2 P0 exercitados no runtime real (C2 provado inteiro; C3 = condição necessária)

> Rótulo do C3 corrigido pós-Fase 7 (o Fable cobrou honestidade): o harness prova a **condição
> necessária** da race, não a ressurreição em si. Ver Fase 7.

| Cenário | Método REAL rodado | Resultado |
|---|---|---|
| **B3 → C2** | `_close_node("claude-2")` com `account=cliente-secreta`, `autoapprove=1`, `role=hacker` | 🔴 **REPRODUZIDO INTEIRO:** `_unique_nid("claude")` devolve `claude-2` (id reciclado) E a config órfã **permanece no store** → nó novo herdaria a conta cliente + o bypass de permissão. Fable confirmou: sem over-mocking. |
| **B4 → C3** | `_kill_all_agents()` com nó em respawn (`_respawn_state="killing"`) | 🔴 **CONDIÇÃO NECESSÁRIA PROVADA:** pós-kill-switch o estado segue `killing`/`pending=True` (o guard do ADR-23 que o `_unload_node` tem, o kill-switch NÃO tem). A ressurreição em si (`_on_child_exited→_do_respawn`) é por leitura de código, não foi executada no harness — bug real, prova um passo aquém do rótulo original. |
| **Bloco A** (persistência) | node_cfg (theme/font/account/autoapprove/shortcut) + zoom via Store, reaberto num Store novo | ✅ **Tudo volta igual** — "abre igual fechou" confirmado na amostra. |
| **U8** (pan) | `get_ui("cam"/"camera")` após set | ✅ Confirmado vazio → **pan não persiste** (achado da Fase 6). |

C11 (E3) **não** foi provado por este harness — meu check só confirmou que o dado `unloaded`
existe, não a falha do callback async de paste; fica pro teste do fix ou pra Fase 5-device.

### ⏳ Pendente com o usuário (genuinamente sensorial / precisa de agente logado)
O roteiro `docs/34` cobre; NÃO dá pra rodar headless: B1/B2/B5 (unload/reattach de agente VIVO —
spawn real), C1/C2/C3 do bloco (tooltips/ícones — confirmação VISUAL), D1-D4 (orquestração +
custo — gasta tokens de conta logada), E1/E2 (paste visual). **Esses seguem no seu roteiro.** O
que dava pra provar sem device/dinheiro, provei — e reproduziu os 2 P0.
## Fase 6 — UX por estado — ✅ CONCLUÍDA 2026-07-20

**Método:** workflow multi-agente (16 agentes, ~17 min) — 5 auditores Opus por família de
controle (ciclo de vida, Maestro/budget/HUD, ícones de estado, persistência, diálogos/cápsulas)
contra as 2 regras do projeto: **(A) honestidade por estado** (rótulo/tooltip diz a verdade em
CADA estado — a lição do ⏏ órfão) e **(B) persistência "abre igual fechou"**. Cada achado
refutado pelo Fable. 11 brutos → **8 confirmados, 3 refutados.**

### Veredito da fase

A regra da honestidade por estado foi **bem aprendida no geral** — os tooltips de ciclo de vida,
o HUD de budget ("pausado por budget" nunca vira "falhou"), os ícones de estado e a maioria das
persistências passaram (refutados com prova). Mas sobrou um **cluster de ações destrutivas sem
confirmação** (4 controles) e **2 defeitos de honestidade em estados específicos** — sendo 1 que
toca segurança (o checkbox de permissão que mente com Maestro mode ligado).

### Achados (U1..U8)

| # | Sev | Onde | O que |
|---|-----|------|-------|
| U1 | 🔴 alta | `canvas.py:2296` | **No nó órfão, o 🗑 diz "Arquivar — o trabalho no disco fica"** mas roda o MESMO caminho do ✕: descarta a sessão retomável do crash. O menu contrasta ✧ ("descarta a sessão") com 🗑 ("arquiva") como se 🗑 preservasse — os dois apagam igual. O diálogo de confirmação até avisa a verdade, mas o tooltip/hint que leva até ele (e o `ORPHAN_HINT`, que aparece sem diálogo) mentem. É a **reincidência exata da lição do ⏏ órfão**, noutro botão. |
| U2 | 🟡 média | `canvas.py:1874` | **Checkbox "Permissão total" mostra DESMARCADO enquanto o nó com Maestro mode ligado JÁ roda sem prompts** — `_node_auto_approve` faz `OR(maestro, autoapprove)`, então o toggle diz "off / pede permissão" enquanto o efetivo é "sem prompts". Toca segurança: o usuário acha que está pedindo confirmação e não está. Precisa de acoplamento ou nota. |
| U3 | 🟡 média | `canvas.py:2419` | **Clicar no corpo do terminal do órfão retoma a sessão silenciosamente** (limpa a flag `orphan`, some o âmbar, respawna com `--resume`) — mas o `ORPHAN_HINT` nunca avisa isso, ao contrário do hint do descarregado. O usuário não consegue clicar pra ler/decidir sem já pré-decidir a recuperação. |
| U4 | 🟡 média | `canvas.py:7564` | **"Excluir" template de equipe apaga na hora, SEM confirmação** — diverge de excluir conta / apagar grupo / fechar nó (que confirmam). |
| U5 | 🟡 média | `canvas.py:6017` | **"Remover" floor destrói o worktree/branch isolado na hora, sem confirmação** — perda de trabalho potencial. |
| U6 | 🟡 média | `canvas.py:8022` | **"Remover" rotina/automação agendada apaga na hora, sem confirmação.** |
| U7 | 🟡 média | `canvas.py:1133` | **"Apagar nota" (🗑 da pílula) apaga conteúdo do usuário permanentemente, sem confirmação.** |
| U8 | 🟢 baixa | `canvas.py:618` | **Pan da câmera é só-em-memória** — `_cam` nunca vai pro `ui_state`; ao reabrir, `_fit_view` recentra no conteúdo. O zoom persiste (cuidado explícito), o pan não. Viola a regra (B) para "posição da vista". Atenuante: recenter é deliberado ("mostra tudo ao abrir") e a Web UI persiste viewport — divergência consciente, por isso baixa. |

**Padrão dominante (U4-U7):** quatro ações destrutivas sem o diálogo de confirmação que o resto
do app aplica — mesma classe "invariante aplicado numas entradas, esquecido noutras". Fix é
uniforme: passar as 4 pelo `_confirm_dialog` já existente.

**Refutados (corretos, registro):** dot de estado após processo sair sem envelope (o crash-flag/
órfão já cobre no próximo boot; não é mentira persistente); "⚠ N" contar `blocked` (blocked pode
sim precisar de você — decisão de design registrada); o próprio U1 numa 2ª instância que citou o
diálogo honesto (o Fable manteve a 1ª formulação, que aponta o tooltip/hint enganoso ANTES do
diálogo — a mais forte).
## Fase 7 — Veredito adversarial (Fable) — ✅ CONCLUÍDA 2026-07-20

Agente **Fable 5** independente auditou a CONDUTA do review + reconferiu os achados-âncora
contra o código (evidência `file:line` própria dele, não a nossa). **Veredito: conduta sólida
e honesta; "não pronto pra produção" é JUSTO; núcleo sólido é JUSTO.** Nenhum achado
materialmente inflado; S1 sustenta os 4 elos; C2 provado de verdade. **3 correções cobradas —
aplicadas abaixo.**

### O que o Fable confirmou (contra código real)
- **Metodologia genuína, não teatro:** provou amostrando que a refutação da Fase 3 discriminou
  certo (contas mascaradas por tmpfs E5 = seguras; o que vaza é o *bus*, árvore diferente não
  mascarada). **S1 sustenta os 4 elos** — reexposição do bus sob `$HOME` via `--ro-bind / /`,
  connect a socket `S_ISSOCK` não bloqueado por mount RO, boxes irmãs + `audit.jsonl` visíveis,
  `frm` carimbado pelo listener explorável. Não derrubou nenhum elo.
- **C2 = prova limpa:** `_scaffold_close` só stuba fronteiras reais (widget/controller); as
  chaves que vazam nem passam por método stubado → o bug não é artefato do harness.
- **Refutados = corretos:** nenhum refutado deveria ter sido confirmado.

### 3 correções cobradas (APLICADAS)
1. **DESINFLAR o rótulo do C3:** o harness prova a **condição necessária** (kill-switch deixa o
   respawn armado), não executa `_on_child_exited→_do_respawn` pra observar a ressurreição. →
   Corrigido de "provado em runtime" para "condição necessária provada; ressurreição por
   code-review" (ver Fase 5). O bug é real; só o rótulo estava um passo além.
2. **ELEVAR S2 a co-manchete com S1:** o S2 (symlink→escrita arbitrária no host) **NÃO é gated
   por Maestro mode** — brief/role é feature geral de equipe. Na prática é MAIS perigoso pro
   usuário default que o S1, porque não exige opt-in. O resumo "a trava default-OFF segura o S1"
   **não cobre o S2**. → Veredito de produção reescrito abaixo.
3. **RE-ENQUADRAR S4 como "P0-quando-Web-UI-ligada"** (não P1 solto): bind localhost pula o token
   e os agentes compartilham a netns → forjam autoridade por `/api/execute`. Mesma moldura do S1.

### Vetores NÃO cobertos por nenhuma fase (adicionados pelo Fable)
- **`flock` ausente:** a premissa "1 instância por vez" (`canvas.py:8219`) é documentada mas
  **não imposta** — 2 instâncias racejariam o sentinela de crash + o SQLite. Baixo, mas real.
- **Frescor/CVE de dependências** (supply-chain) — nenhuma fase tocou; "produção" costuma incluir.

### ⚖ VEREDITO DE PRODUÇÃO (reescrito pós-Fable)
**O app NÃO está pronto pra produção.** O núcleo é sólido (confinamento de escrita, fail-safe,
mutex/envelope/delegate limpos); os bugs são a classe recorrente **"invariante aplicado numa
entrada, esquecido na irmã"** — localizada e corrigível com padrão conhecido, não podridão
arquitetural. **Dois furos são exploráveis SEM opt-in nenhum e são co-bloqueadores:**
- 🔴 **S1** (spoof de socket) — segurado pela trava default-OFF do Maestro mode **enquanto ele
  ficar OFF**; corrigir antes de qualquer uso de Maestro mode.
- 🔴 **S2** (escrita arbitrária no host via symlink) — **NÃO tem trava**; vale com brief/role de
  equipe, que é uso normal. **Este é o mais urgente do ponto de vista do usuário default.**
- 🔴 **C2/C3** (ciclo de vida do nó) — C2 vaza credencial+bypass por id reciclado (uso normal);
  C3 derrota o kill-switch por race.
- 🟠 **S4** (bypass do control-plane web) — **P0-quando a Web UI estiver ligada**; manter off até
  o fix.

---

## ✅ RESOLUÇÃO DOS BLOQUEADORES (pós-review, 2026-07-20)

Todos os **4 bloqueadores P0/P0-condicional** foram corrigidos, mergeados na `main` e provados
em runtime. **Cada PR de fix passou por revisão adversarial (Fable) ANTES do merge** — e a
revisão achou furo em TODOS os 4: a v1 de cada fix corrigia só a entrada óbvia e recaía na mesma
classe que o próprio review identificou ("invariante em todas as entradas"). A correção
estrutural foi mover os invariantes de segurança pra dentro do `sandbox.wrap()` (camada
compartilhada → cobre interativo + headless/floor + qualquer caminho futuro).

| Achado | PR | Versão | O que a revisão do PR endureceu |
|---|---|---|---|
| **C2/C3/C7** ciclo de vida | #90 | v0.68.0 | C2 vazava a sessão da ENGINE + usage + budget (não só ui_state); C7 sem fallback `or nid` |
| **S2** symlink→host | #91 | v0.69.0 | 4 de 8 stampers não convertidos (write-no-host ainda); `realpath` check-then-open → **TOCTOU no pai** (reescrito com `dir_fd`+`O_NOFOLLOW`) |
| **S1** spoof de socket (CRÍTICO) | #92 | v0.70.0 | máscara só no spawn interativo → **headless/floor continuava spoofável** (movida pro `wrap()`) |
| **S4** control-plane web | #93 | v0.71.0 | token só escondido se já existisse no spawn + **headless não escondia** (movido pro `wrap()` + `ensure_token` eager no boot) |

**Provas:** cada furo virou teste de **mutação** (falha sem o fix); os de segurança têm prova sob
**bwrap real** (agente lê socket/token inacessível). Suíte final na `main` integrada: 626 venv +
gi de segurança/ciclo-de-vida + T1/sandbox live ✅, ruff limpo.

**Veredito atualizado:** os bloqueadores que sustentavam o "não pronto" estão **fechados**. O
Maestro mode e a Web UI deixam de depender das travas default-OFF pra segurança (embora sigam
opt-in por UX). **Fica pra depois (não-bloqueador):** os P1/P2 acima (S3, S5, C1/C4, C5/C10,
U1-U8, flock, CVE de deps) + o resíduo aceito do `audit.jsonl` (disclosure read-only) + a Fase 5
sensorial no device (`docs/34`).
