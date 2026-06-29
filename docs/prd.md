# PRD — maestro console

> 📌 **Cópia VERSIONADA do PRD do MVP** (espelha `_bmad-output/planning-artifacts/prd.md`, que é
> gitignored). É o planejamento **do MVP**: canvas/WYSIWYG aparecem como "fora de escopo", mas o
> **canvas virou o carro-chefe** (v0.13→v0.37). **Estado atual:** [`STATUS.md`](STATUS.md) ·
> **histórico:** `../CHANGELOG.md` · **decisões:** [`ADR.md`](ADR.md). Mantido aqui p/ ter
> histórico git e sobreviver a `rm -rf _bmad-output`.

> Produto: **maestro console** 🎼 · Repositório: `maestri-console`
> Artefato BMad · Tipo: PRD · Data: 2026-06-21 · Idioma: PT-BR
> Status: **APROVADO (v3)** — aprovado pelo usuário em 2026-06-21. Fase de validação encerrada. Não reabrir sem contradição impeditiva.
> Base: `product-brief.md`, `spike-fase0-resultados.md`, `spike-fase0.1-resultados.md`, `spike-fase0.2-resultados.md`, `docs/01-*`, `docs/02-*`

---

## 1. Objetivos

- Orquestrar **múltiplos agentes de IA em terminal** num handheld Linux ARM (uConsole/CM4), *terminal-first* e leve.
- **Nota de honestidade:** a **engine de orquestração roda localmente/offline**, mas os **agentes (Claude Code, Codex) dependem de API, autenticação e rede**. O produto **não** é "offline" como um todo.
- Permitir **delegação automática orquestrador-mediada**: o orquestrador chama o agente A, **extrai** a resposta e a **encaminha** ao agente B (fluxo `orquestrador → A → orquestrador → B`). **Não** é comunicação direta agente↔agente estilo Maestri — é o padrão orchestrator-worker (mais robusto; cf. pesquisa 02).
- **Detectar de forma confiável** quando cada agente termina (≥ 95%), usando **exit code do processo headless** como sinal principal (estado-da-TUI só no caminho de visibilidade interativa).
- Ser **agnóstico de CLI** via camada de adapter (Claude Code + Codex no MVP).
- Manter **engine desacoplada da UI**, abrindo caminho para Web UI futura sem reescrita.

## 2. Contexto

O Maestri (macOS, fechado, canvas gráfico) provou o valor da orquestração de agentes, mas é inviável em handhelds Linux ARM. As Fases 0/0.1/0.2 comprovaram o conceito central no CM4: handoff orquestrador-mediado **via modo headless** dos CLIs (cadeia A→B→A 100%/30), continuidade de sessão e trabalho em arquivos funcionando, RAM/CPU folgados com 4 agentes ativos. O modo **tmux** entra como **visibilidade humana** opcional. O maestro console captura **a essência** (orquestração) sem o peso do visual.

## 3. Requisitos Funcionais (FR)

- **FR1** — A engine cria e gerencia agentes em **dois modos de execução**: (a) **headless** (processo `claude -p` / `codex exec`) = padrão para dados; (b) **pane tmux** (adapter fino, sem PTY próprio) = modo de visibilidade humana.
- **FR2** — Enviar prompt ao agente conforme o modo: **headless** (argumento/stdin do processo) ou **tmux** (`send-keys`/buffer). Suportar texto comum, **multiline e caracteres especiais** *(Fase 0.1: 100% em multiline/special headless)*.
- **FR3** — Obter a resposta de um agente por **dois caminhos**: (a) **headless** (`claude -p`, `codex exec`) = caminho de DADOS do handoff (saída limpa, fim por exit code) — **padrão**; (b) **leitura da região de resposta** de um pane interativo, para o modo de visibilidade humana.
- **FR4** — **Detector de término**: (a) headless = **fim do processo + verificação do `returncode`** (0 = sucesso; ≠0 = falha/erro a tratar); (b) interativo (TUI) = estado-da-TUI working→idle → sentinel → quiescência → timeout. *(returncode validado na Fase 0.2.)*
- **FR5** — **Handoff A→B→A**: o orquestrador delega ao agente A, **extrai** a resposta, **encaminha** ao agente B, e assim por diante. *(Validado na Fase 0.1: 100% em 30 execuções via headless.)*
- **FR6** — **Adapter por agente** (perfil declarativo): comando de launch, fluxo de onboarding (ex.: trust do Codex), tokens de busy/idle, ready prompt, modo de input.
- **FR7** — **Agent Registry**: registrar/listar agentes ativos, seu estado (ocioso/ocupado/erro) e tipo (CLI).
- **FR8** — **Message Bus**: rotear mensagens entre agentes/orquestrador de forma desacoplada.
- **FR9** — **Task Queue**: enfileirar tarefas de delegação e entregá-las quando o agente-alvo estiver ocioso.
- **FR10** — **Orquestrador**: decompor uma intenção em subtarefas e delegar aos agentes apropriados (MVP: roteamento simples/explícito; orquestração avançada é pós-MVP).
- **FR11** — **TUI**: listar agentes/painéis, ver estado, disparar delegação e acompanhar respostas pelo teclado físico.
- **FR12** — **Logs**: registrar histórico de mensagens/handoffs (estado externo persistente p/ depuração e continuidade).
- **FR13** — **Continuidade de sessão (estado do agente)**: manter contexto de um agente entre chamadas via sessão persistente (`claude --session-id/--resume`, `codex exec resume`), para trabalho iterativo multi-turno. *(Validado na Fase 0.2.)*
- **FR14** — **Trabalho em arquivos / artefatos por caminho**: agentes criam/editam arquivos reais; o handoff de artefatos grandes é por **referência de caminho**, não conteúdo inline (um agente escreve, outro lê). *(Validado na Fase 0.2.)*
- **FR15** — **Protocolo de mensagem compacto entre agentes** (envelope estruturado): cada mensagem agente↔orquestrador usa formato curto e parseável, com:
  - **estado** explícito: `DONE | BLOCKED | FAILED | NEEDS_INPUT`
  - **linguagem técnica e direta**, sem explicações desnecessárias
  - **limite de tokens/bytes** por mensagem
  - **artefatos grandes referenciados por caminho** (não inline)
  - exemplo: `state: DONE` / `result: <linha curta>` / `artifacts: ./path/arquivo`. *(Parsing validado na Fase 0.2.)*

## 4. Requisitos Não-Funcionais (NFR)

- **NFR1 (Confiabilidade)** — Mecânica de handoff/cadeia bem-sucedida **≥ 95%**, medida sobre **≥ 30 execuções**, incluindo execução **concorrente** (não só sequencial). *(Fase 0.1: 100%/30 sequencial; Fase 0.2: confiabilidade sob concorrência.)* No caminho interativo, falsos "pronto" ≤ 5%. **Ressalva honesta:** isto mede a **confiabilidade do mecanismo** (encanamento), **não** a qualidade da resposta em **tarefas reais** — esta depende do agente/modelo e será avaliada por NFR próprio nas stories de tarefas reais (não por aritmética trivial).
- **NFR2 (Recursos)** — Operação com **3 agentes ativos** deixando **≥ 500 MB de RAM livres**. *(Fase 0.1: 4 agentes ativos → ≥ 1699 MB livres.)* Sobre swap: na carga medida **o swap não cresceu** (488 MB já estavam em uso por outros processos no baseline); a afirmação forte de **independência total de swap** exige um teste futuro com **swap desligado** — fica como verificação aberta.
- **NFR3 (Desempenho)** — Tolerar agentes lentos (Codex/gpt-5.5 leva >10 s) via timeout generoso; latência da cadeia A→B→A na faixa observada (~19 s mediano em 3 hops) é aceitável.
- **NFR4 (Dependências/Portabilidade)** — Rodar em Linux aarch64 (Kali/CM4). Dependências: **tmux 3.2+**, **Python 3.13** (engine sem binários nativos no MVP) **e os CLIs dos agentes instalados e autenticados** (claude, codex) **+ rede/API** para os agentes.
- **NFR5 (Extensibilidade)** — Novo agente = novo arquivo de adapter, sem mexer no core.
- **NFR6 (Desacoplamento)** — Engine sem dependência da TUI; interface plugável (TUI agora, Web depois).
- **NFR7 (Robustez)** — Tolerar onboarding/estados variados dos CLIs e ruído ANSI; nunca travar o orquestrador por um agente preso (timeouts + estado de erro).
- **NFR8 (Licença/Distribuição)** — MIT, pronto para publicação no Git/comunidade (README, instalação simples).

## 5. Interface (TUI) — metas de UX

- *Terminal-first*, otimizada para **1280×720** e **teclado físico** (atalhos, navegação por teclas).
- Visão de **painéis/agentes** com estado (ocioso/ocupado/erro) em texto.
- Disparo de delegação e leitura de respostas sem sair do terminal.
- Baixo "peso visual" (sem animações pesadas); foco em clareza e latência.
- Conexões/delegações representadas como **lista/setas** (o canvas com nós/cabos fica para a Web UI futura).
  - **Obs. pós-MVP [2026-06-29]:** o **canvas nativo GTK** com nós/cabos foi entregue (não só lista/setas) — ver ADR-12/13/14 e CHANGELOG (v0.13.0→v0.34.0). O cabo evoluiu para **ímã de 8 pontos + bolinha + fluxo direcional + física (Verlet/catenária/mola, Ctrl+Shift+P)**. Este PRD é o documento **do MVP**; a realidade atual vive no CHANGELOG/ADRs.

## 6. Premissas técnicas

- **tmux** como substrato de PTY (decisão travada pelo spike) — usado no modo de visibilidade interativa.
- **Caminho de dados = headless** (`claude -p` / `codex exec`): saída limpa, fim por exit code — padrão do orquestrador (Fase 0.1: 100%).
- **Caminho de visibilidade = TUI em pane tmux** (opcional, estilo Maestri) com detecção por estado-da-TUI; o humano pode `tmux attach`.
- **Engine em Python** primeiro; core reescrito em Go/Rust só se o consumo exigir.
- **LLM via API remota** (uso local = CPU no streaming, não RAM). *(Fase 0.1: 4 agentes ativos sem saturar CPU/RAM nem crescer swap.)*

## 7. Fora de escopo (MVP)

Web UI/canvas · grafos complexos de tarefas · memória compartilhada avançada · auditoria de produção · **instalador empacotado/distribuível** (pacote `.deb`, binário único, publicação em índices) · suporte amplo a "todos os CLIs" (além de Claude/Codex) · skills entre agentes no formato final.

> Distinção (resolve contradição apontada na auditoria): o **MVP inclui** apenas **README + licença MIT + instruções de instalação manual** (`git clone` + `pip`/venv) e smoke tests — Épico 5. **Fica para depois** o empacotamento distribuível (`.deb`/binário/publicação).

## 8. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| CPU satura com 3-4 agentes ativos juntos | **Story inicial**: benchmark de carga ativa + teto de agentes ativos configurável |
| Heterogeneidade de CLIs (onboarding/estado/input) | Camada de **adapter** declarativa (RR2 do spike) |
| Extrair texto da resposta com ruído ANSI | Capturar com `-e`, normalizar ANSI, delimitar região (RR3) |
| Agente preso/lento trava o fluxo | Timeouts + estado de erro + nunca bloquear o orquestrador |

## 9. Visão de épicos (alto nível)

> Detalhamento em epics/stories é o próximo artefato. Estrutura proposta:

- **Épico 1 — Fundação da Engine + runner headless**: scaffolding, **runner headless** (`claude -p`/`codex exec`) com verificação de `returncode`, agent registry, message bus mínimo. (FR1, FR3, FR4, FR7, FR8)
- **Épico 2 — Adapters + continuidade de sessão + arquivos**: adapter declarativo por agente (onboarding/launch), **continuidade de sessão** (`--resume`), **trabalho em arquivos / artefatos por caminho**, extração robusta. (FR6, FR13, FR14)
- **Épico 3 — Handoff, Orquestração & Protocolo compacto**: delegação A→B→A com extração+encaminhamento, **envelope estruturado** (`DONE/BLOCKED/FAILED/NEEDS_INPUT`, limite de tokens, artefatos por path), task queue, orquestrador de roteamento simples. (FR5, FR9, FR10, FR15)
- **Épico 4 — Visibilidade tmux + TUI**: modo de visibilidade em pane tmux (estado-da-TUI), TUI para ver agentes/estado, disparar delegação, acompanhar respostas; logs. (FR11, FR12, caminho interativo de FR1-FR4)
- **Épico 5 — Release open-source mínima (MVP)**: README, licença MIT, **instalação manual** (`git clone` + venv/pip), smoke tests. *(NÃO inclui empacotamento `.deb`/binário — pós-MVP.)*

## 10. Critérios de aceite do MVP

Mensuráveis (com N, carga e medição definidos):
- **Handoff A→B→A** com 2 agentes reais (Claude + Codex): **≥ 95% de sucesso em ≥ 30 execuções** no uConsole. *(Fase 0.1 já atingiu 100%/30.)*
- **Multiline + caracteres especiais**: **≥ 90% em ≥ 10 execuções**. *(Fase 0.1: 100%/10.)*
- **Carga ativa de 3 agentes**: RAM livre **≥ 500 MB** e **crescimento de swap = 0 MB**, amostrado a cada 1 s durante o processamento. *(Fase 0.1: ≥ 1699 MB livres, swap 0.)*
- **Extensibilidade**: adicionar um 3º agente apenas criando um arquivo de adapter, **sem alterar o core** (verificado por revisão de diff).
- **TUI** utilizável no teclado físico do uConsole (1280×720): listar agentes/estado e disparar uma delegação sem mouse.
