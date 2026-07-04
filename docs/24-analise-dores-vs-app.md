# Análise: dores do mercado × estado do maestro-console

**Data:** 2026-07-03 · **Insumos:** `docs/22-pesquisa-dores-maestri.md` (29 dores do Maestri) + `docs/23-pesquisa-dores-concorrentes.md` (41 capítulos, 13 padrões P1-P13) · **Base de estado:** `docs/STATUS.md` v0.55.0 + `docs/15-ideias-backlog.md` + branch atual `feat/unload-a-session-capture`.

Classificação: ✅ **já coberto** (vira argumento de posicionamento) · 🔨 **em desenvolvimento** · 🎯 **lacuna implementável** (candidata) · 🛡️ **anti-padrão a evitar** (guarda de projeto, não feature).

---

## 1. O que o app JÁ COBRE (✅) — dores dos concorrentes que são nossos argumentos

| Padrão do mercado | Evidência da dor lá fora | Cobertura aqui |
|---|---|---|
| **P1 — bypass de permissões default** | superset e dmux com `--dangerously-skip-permissions` hardcoded; cmux forçou bypass silencioso; Cline desligou subagents | bwrap SEM bypass; auto-aprovação é opt-in explícito por nó (ADR-19); autoridade sempre no host (ADR-16..18) |
| **P4 — delegação não-verificável** | Maestri ~70%, Windsurf ~40%, Dorothy não despacha, Cursor sem coordenação | Orquestrador-mediado com envelope JSON estrito validado + retry + ledger + auditoria + HITL; cabo headless por padrão devolve resposta completa (ADR-20) |
| **P5 — macOS-only / Linux reprimido** | Issue de Linux com 194 reações no cmux; pedido em 8+ produtos | Linux/ARM nativo — único do levantamento |
| **P6 — PATH/ambiente do shell quebrado** | mux, Aizen, herdr, Crystal (dor fundacional), supacode, Jean | VTE roda o shell REAL do usuário — a classe de bug não existe por construção |
| **P9 — isolamento vazando** | Warp Oz (confused deputy entre sessões!), Crystal (commit na main), ai-maestro (broadcast entre projetos), Codex (estado compartilhado) | bwrap por nó + socket por agente (anti-spoofing) + autoridade por linhagem + escopo por cabo (ADR-16..18, v0.51.1 corrigiu fiação≠autoridade) |
| **P11 — status de agente mentiroso** | Maestro OSS morreu nisso; RunMaestro stall silencioso; Clave sem indicador | Estado por nó (v0.52: NEEDS_INPUT + monitor de quietude, "aguardando" distinto) + monitor padrão-ON (v0.53) + contador ⚠ clicável + minimapa |
| **P3 — custo sem guardrail** (núcleo) | Cursor US$600/sessão; mux drenou quota em 2 min; Verdent Trustpilot 1★; Cowork queima Max 20x | Medidor de custo/tokens por nó (v0.54) + budget cap soft/hard com contador monotônico host-side (v0.55, ADR-22) |
| **P8 — fidelidade de TTY** (base) | herdr paga a cauda de reimplementar VT; Emdash/superset/parallel-code com render corrompido | VTE maduro do GTK — não reimplementamos emulação |
| **"Perde o feel do CLI"** (Conductor) | "There's a 'feel'… this is lost with conductor" | Terminal VTE real, TUI nativa preservada |

**Uso recomendado:** este bloco é material pronto de posicionamento/README ("o que ninguém entrega junto: canvas + Linux + open source + custo transparente + delegação verificável").

## 2. Em desenvolvimento AGORA (🔨) — e os relatórios elevam a aposta

- **P2 — sessão que não persiste** (a dor mais universal: Clave #19, cmux admitido, **Cowork "limitação atual" admitida pela Anthropic**, Nimbalyst, RunMaestro "não sobrevive a restart", Codex, Aizen, Maestri A1): o **unload de nó por captura de sessão** (branch atual, docs/21, story A′ pronta) ataca exatamente isso. Os relatórios confirmam: é a aposta certa, e nem os labs resolvem.
- **P7 — RAM sob paralelismo** (Maestri 20 GB, cmux/Codex 70 GB, Nimbalyst CPU 100%): o mesmo unload + medidor = posicionamento "rode N agentes em 4 GB". Decisivo no CM4.

## 3. Lacunas implementáveis (🎯) — ranqueadas por (dor validada × esforço × aderência ao que existe)

### Nível 1 — extensões curtas de features existentes (quick wins)
1. **Budget cap: pausa graciosa + notificação + retomada** — hoje o hard cap barra via envelope; a dor validada (RunMaestro #235: 4h parado SILENCIOSAMENTE num run de 24h; #338) pede: ao esgotar, notificar visivelmente (attention/estado do nó), pausar limpo e oferecer retomada 1-clique após reset. Extensão do Bloco D (docs/20 §4 já previa). *Dores: P3, RunMaestro 1-2, Cursor 3.*
2. **Nerd Fonts no terminal** — já no backlog (menores); dor literal do Maestri (F6, Setapp). Expor no `terminal_theme`.
3. **Teste de runtime de teclado internacional (dead keys/acentos PT-BR + CJK)** — supacode #495, dmux #64, cmux #1653, Aizen #23. O VTE provavelmente já cobre — PROVAR com teste vivo e registrar; se falhar em algo, corrigir. Barato e direto pro nosso público.
4. **Paste/drag de imagem pro nó** — dor em 5+ produtos (supacode 3 issues, AoE, Maestro OSS #33, Clave #16 com caminho temp deletado, Emdash). Verificar o comportamento atual do VTE (drag de arquivo → colar caminho ESTÁVEL; screenshot do clipboard → salvar em arquivo do workspace e colar o caminho). Item NOVO pro backlog.

### Nível 2 — itens do backlog que os relatórios promovem (dor agora comprovada)
5. **Reattach/arquivar nós órfãos pós-crash** (backlog 🧊 → candidato a puxar junto com o unload: mesma área de ciclo de vida) — completa o P2: crash do app ≠ perder trabalho (Clave #19, Cowork, Emdash zumbis, superset worktrees órfãs).
6. **Fila FIFO de follow-ups por nó** (backlog 🧊) — dor de interrupção agressiva (Nimbalyst #337 "hard abort") + steering da Fase 4 (endossada pelo Fable). "Enfileirar sem perder mensagem".
7. **Briefing persistente por grupo** (backlog 🧊) — responde P4/C4 do Maestri (memória compartilhada = sticky manual) e Conductor 8 (sem memória entre sessões): contexto injetado automático em cada agente novo do grupo.
8. **Modo compacto pro canvas lotado** (backlog 🧊) — responde F2 do Maestri (canvas = passo extra) e herdr 6 (observabilidade rasa com N agentes) na nossa 1280×720.
9. **Perfis de agente (presets)** (backlog 🧊) — ampliar com a dor do Clave #22: **diretório de config isolado por perfil** (conta de trabalho × pessoal simultâneas) — ninguém entrega.

### Nível 3 — maiores, avaliar quando puxar
10. **UX de review por nó (P12)** — "review humano é o gargalo" (Conductor, Willison/Codex, Cursor): diff desde o último feedback (backlog menor) + aproveitar merge preview dos Floors no fluxo do nó. É a Fase 4 do docs/10 (steering+timeline) com novo argumento.
11. **Egress allow-list de rede** (risco residual aceito do ADR-17) — a thread "Cowork exfiltrates files" (870 pts no HN) mostra que é preocupação de compra real; viraria diferencial de segurança auditável. Esforço médio-alto.
12. **Higiene de worktree (P10)** — se worktree-por-nó avançar (Fase 7-A4/Floors): bootstrap de untracked (.env), limpeza garantida no delete (superset/Polyscope órfãos), e **funcionar 100% sem remote** (dor 3× no nicho: Emdash #451, Constellagent #9, Conductor GitHub-only). Já parcialmente coberto pelos Floors — auditar contra essas 3 dores.

## 4. Anti-padrões a NÃO implementar (🛡️)

> **Formalizado [2026-07-04]:** revisão adversarial do Fable separou estas guardas por durabilidade.
> As duas de **fronteira com o runtime/dependências** (auto-atualizar CLI + dependência externa
> cosmética) viraram **ADR-24** (imutável). As outras três (kanban, N-scale, theater) ficaram como
> notas datadas no `docs/10` — priorização/lema/escopo de UI **podem evoluir**, então não viram ADR.

- **Kanban de sessões (Fase 5-A2 do docs/10)** — já flagrado como cargo-cult pelo Fable; o Windsurf agora confirma: "Kanban de agentes = jeito mais bonito de assistir falhas" + fricção pra dev solo. Manter cortado. → **docs/10 Fase 5-A2 marcado CUT.**
- **"Orchestration theater"** — qualquer painel novo só entra se apoiado em delegação verificável (que já temos); nunca UI antes de confiabilidade. → **docs/10 Fase 5, princípio de design.**
- **Escalar N agentes antes de resolver review** — P12: além de ~3-5 agentes o gargalo é o humano; "mais nós" sem UX de review é regressão disfarçada de feature. → **docs/10 Fase 6-A3, nota de sequenciamento.**
- **Auto-atualizar/embutir o CLI do agente** (Jean #460, superset baixando o próprio OpenCode) — sempre usar o CLI do usuário; no máximo reportar versão em diagnóstico. → **ADR-24 (a).**
- **Dependência externa embutida pra features cosméticas** (dmux/OpenRouter) — gera revolta e forks. → **ADR-24 (b).**
- **Cadência (P13):** o nicho pune abandono em semanas (Crystal, claude-squad, Maestro OSS) — releases pequenos e regulares valem mais que features grandes espaçadas; e validar padrões de concorrente antes de copiar (pode estar morto).

## 5. Recomendação de sequência (proposta, decisão é do usuário)

1. **Fechar o unload/captura de sessão** (em curso) — ataca P2+P7, as dores nº 1 e nº 7 do mercado.
2. **Na sequência natural (mesma área):** reattach/arquivar órfãos (item 5) — fecha o ciclo de vida.
3. **Rodada de quick wins TTY** (itens 2-4: nerd fonts + teste dead keys + paste de imagem) — 1 branch de polimento, dores baratas e visíveis.
4. **Budget graceful-pause** (item 1) — extensão curta do que acabou de ser entregue.
5. Depois, escolher entre Nível 2 (6-9) conforme o uso real no CM4 apontar.
