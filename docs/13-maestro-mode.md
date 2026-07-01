# Maestro mode — sub-orquestração SEGURA (feature consolidada)

> Doc de feature. Consolida o que foi entregue em **v0.45.0** (Maestro mode + hardening) e
> **v0.46.0** (auto-aprovação + cabo headless). **Fontes canônicas:** `CHANGELOG.md` (histórico)
> e `ADR.md` (decisões **ADR-16..20**). Código: `maestro/native/canvas.py`,
> `maestro/engine/ask_sock.py|ask_bus.py|maestro_audit.py|maestro_guard.py`, `adapters/*.toml`.
> Data: 2026-07-01 · PT-BR.

## 1. O que é (visão do usuário)

Um terminal de **agente** pode virar **manager** e montar/coordenar uma equipe no próprio canvas,
sem sair do shell. Você liga o **Maestro mode** num nó de agente; ele passa a poder:

| Comando (`maestri …`) | O que faz |
|---|---|
| `recruit <agente> [papel]` | cria um terminal de agente real, **conectado por cabo ABAIXO**, com o papel |
| `list` | lista os recrutas conectados |
| `reassign <nó> <papel>` | troca o papel de um recruta seu (reinicia p/ reler) |
| `wire <a> [b]` | liga um cabo entre você e um recruta seu |
| `dismiss <nó>` | dispensa (fecha) um recruta seu |

Os agentes conversam por **cabos** (`maestro-ask <nó> "<pergunta>"`) — ex.: o manager delega
"corrija este texto" a um recruta-corretor e recebe a resposta.

**Divergência consciente do Maestri (ADR-16):** o app-alvo (Maestri de macOS) é orquestração
**só-humana** — lá o humano cria e conecta os nós; o agente **não** recruta agentes. O "Maestro
mode" é uma **extensão original** deste projeto, adotada deliberadamente.

## 2. Princípio de segurança (o que rege tudo)

> **Toda autoridade — spawn, wire, profundidade, budget — é imposta pelo HOST a partir de estado
> que SÓ o host controla; nunca derivada de campos que o agente preenche** (ADR-17).

Segurança multi-agente **não é composicional**: assuma que qualquer agente pode ser sequestrado por
conteúdo (prompt injection / *confused deputy*). Por isso o host é o *trust anchor*.

## 3. Como funciona (arquitetura)

```
agente (bwrap)  --shim maestri/maestro-ask-->  SOCKET Unix por agente (<bus>/box/<nó>/sock)
                                                        │  identidade = QUAL socket aceitou
                                                        ▼
                              host (canvas): _on_sock_request  →  frm = canal (ignora payload)
                                   ├─ cmd  → _maestro_handle → idle_add → _maestro_dispatch (main)
                                   └─ cabo → _ask_router → _ask_delegate → HEADLESS (run_in_session)
```

- **Identidade por canal (ADR-17):** cada agente só enxerga a **própria** caixa (bind-mount RW
  isolado); o host deriva o remetente de **qual socket** aceitou a conexão e **ignora** o `frm` do
  payload → spoofing impossível por construção. Shims em `<bus>/bin` (RO), chamados por `$MAESTRO_BIN`.
- **Cabo (ADR-11/13/20):** a resposta vem por **headless** (mediado, completa+limpa) por padrão, com
  contexto contínuo por agente (`run_in_session` usa `--resume`); o modo `live` (raspar a TUI viva) é
  **opt-in** só para visibilidade (`MAESTRO_ASK_MODE=live`), pois raspar TUI full-screen trunca ~70%.

## 4. Controles de segurança (Etapas 1–4 + Blocos 1–3)

| Controle | O que é | ADR/Etapa |
|---|---|---|
| **Identidade por canal** | socket pathname por agente; frm do canal, não do payload | ADR-17 · Etapa 1 |
| **Kill-switch global** | "⛔ Parar tudo" → SIGKILL via pidfd; cada agente é bwrap `--unshare-pid` → **colapsa a subárvore** | Etapa 2 |
| **Tetos por linhagem** | global (12) + profundidade da árvore (2) + per-manager (6) + rate-limit (token-bucket) | Etapa 3 |
| **Recruta nasce sem recrutar** | promover exige toggle humano → mata fork-bomb por design | Etapa 3 |
| **HITL soft-cap** | recrutar acima de 8 pausa e pergunta ao humano | Etapa 3 |
| **Observabilidade ativa** | HUD do fleet + auditoria append-only + anomalia→kill-switch automático + ciclo | Etapa 4 |
| **Autoridade por linhagem** | `dismiss`/`reassign`/`wire` autorizam por `_recruited_by` (host), NÃO pelos cabos (que o agente cria) — fecha confused-deputy | ADR-18 · Bloco 1 |
| **Concorrência do socket** | só a thread do `serve` toca o selector (fila de ops) | Bloco 1 |
| **Anti-DoS do socket** | teto de conexões (semáforo) + deadline absoluto de leitura (anti slowloris) | Bloco 2 |
| **Rate-limit universal** | token-bucket por-manager cobre recruit/dismiss/wire/reassign | Bloco 2 |
| **Sandbox** | bwrap por agente + `--cap-drop ALL` (fecha remount-rw) | ADR-6/17 |

**Risco residual aceito (ADR-17):** proveniência/tainting de conteúdo, validação semântica plena e
egress allow-list de rede — com controles compensatórios (caps + kill-switch + HITL + auditoria).

## 5. Auto-aprovação de comandos (ADR-19, v0.46.0)

O CLI interativo pode rodar comandos **sem os prompts de permissão**, quando o nó pede. Seguro:
o **ADR-6** já cravou que as flags de permissão do CLI "só evitam prompts, NÃO confinam — o limite é
o bwrap". Duas formas:
- **Fase 1 — Maestro mode ligado:** o manager roda `maestri …` sem interrupção.
- **Fase 2 — toggle "Permissão total" por nó** (aba Detalhes): qualquer agente, on-demand.

Flags declarativas no `[interactive].auto_approve` de cada `adapters/*.toml` (verificadas nos binários
2026-07-01): claude → `--permission-mode bypassPermissions`; codex →
`--dangerously-bypass-approvals-and-sandbox` (desliga a sandbox interna dele, que aninhada no bwrap
quebra). Provado em runtime (bwrap real): ambos rodaram um comando sem prompt.

## 6. Persistência (regra do projeto)

Tudo que o usuário liga persiste via `node_cfg` (tabela `ui_state`): `maestro`, `autoapprove`, `role`.
Reabrir = igual fechou. O `main()` restaura o auto-aprovar e o Maestro mode persistidos.

---

## Épico & Stories (BMad — retrospectivo, tudo DONE)

> Convenção `E<épico>-S<story>` com Critérios de Aceite (CA) testáveis. Este épico foi entregue como
> **Fase 6 + Etapas 1–4 + Blocos 1–3 + Auto-approve + Cabo headless** (ver `CHANGELOG` v0.45–0.46).

### Épico M — Maestro mode seguro
*Objetivo: um agente pode recrutar/coordenar uma equipe no canvas, com toda a autoridade imposta pelo
host, testado adversarialmente.* (ADR-16..20)

**EM-S1 — Sub-orquestração base (Fase 6)** ✅
- CA: shim `maestri` (recruit/list/reassign/wire/dismiss); recruit cria agente real conectado ABAIXO.
- CA: comando vira `AskRequest` (cmd/args) validado; gate exige o toggle Maestro ligado.

**EM-S2 — Identidade por canal (Etapa 1, ADR-17)** ✅
- CA: socket Unix *pathname* por agente; host deriva o remetente do canal e ignora o `frm` do payload.
- CA: anti-spoofing provado no canvas + probe bwrap real (`tests/test_maestro_live.py`).

**EM-S3 — Kill-switch que ceifa a subárvore (Etapa 2)** ✅
- CA: "⛔ Parar tudo" mata todo o fleet via pidfd; **drill** prova 0 sobreviventes (bwrap `--unshare-pid`).
- CA: hard-cap global + auditoria append-only desde o 1º evento.

**EM-S4 — Tetos por linhagem + HITL (Etapa 3)** ✅
- CA: profundidade derivada da árvore (host), rate-limit token-bucket, recruta nasce sem recrutar.
- CA: recrutar acima do soft-cap pausa e pede confirmação humana.

**EM-S5 — Observabilidade que age (Etapa 4)** ✅
- CA: HUD do fleet (nº/profundidade/ciclo); rajada de bloqueios dispara o kill-switch automaticamente.

**EM-S6 — Autoridade por linhagem, não cabos (Bloco 1, ADR-18)** ✅
- CA: `dismiss`/`reassign`/`wire` autorizam por `_recruited_by`; exploit `wire→dismiss` de vítima é recusado.
- CA: `SockServer` sem race no selector (só a thread do serve o toca).

**EM-S7 — Anti-DoS + rate-limit universal (Bloco 2)** ✅
- CA: teto de conexões + deadline de leitura (anti slowloris); rate-limit cobre os 4 comandos mutadores.

**EM-S8 — Provas de runtime como regressão (Bloco 3)** ✅
- CA: probe socket-em-bwrap + drill do kill-switch viram `tests/*_live.py` (rodam com bwrap, sem tokens).
- CA: `_make_win` deixa de mockar o método de domínio `_node_role`.

**EM-S9 — Auto-aprovação (ADR-19)** ✅
- CA: Maestro mode e o toggle "Permissão total" lançam o CLI com as flags de auto-aprovação (por TOML).
- CA: provado em runtime que claude/codex rodam sem prompt no bwrap.

**EM-S10 — Cabo confiável por headless (ADR-20)** ✅
- CA: a resposta do cabo vem por headless (completa) por padrão, com contexto via `run_in_session`.
- CA: `live` (raspar TUI) é opt-in de visibilidade.

**EM-S11 — Robustez de ciclo de vida** ✅
- CA: `_unique_nid` não colide com o registro do controller/roster; `remove_agent_instance` libera o id ao dispensar.
