# Índice de documentação — maestro console

> Mapa de TODOS os docs, com o estado de cada um. **Atualizado: 2026-07-02 (v0.51.0).**
> Regra: **research/auditoria são point-in-time** (legítimo serem antigos — registram a decisão
> da época); o que descreve "estado/roadmap" e ficou congelado no MVP recebeu **nota de defasagem**.

## 🟢 Canônicos (fontes de verdade — sempre atuais)
| Doc | O que é |
|---|---|
| [`../CHANGELOG.md`](../CHANGELOG.md) | Histórico real de versões (v0.1.0→v0.51.0). |
| [`ADR.md`](ADR.md) | Decisões arquiteturais (ADR-1..20), versionado, imutável. |
| [`STATUS.md`](STATUS.md) | Estado atual / o que foi entregue (resumo + ponteiros). |
| [`13-maestro-mode.md`](13-maestro-mode.md) | **Feature (atual):** Maestro mode seguro + auto-aprovação + cabo headless (ADR-16..20). |
| [`14-plano-orquestracao-equipe.md`](14-plano-orquestracao-equipe.md) | **Plano cirúrgico:** orquestração de equipe — **Fases A+B+C+D entregues** (v0.47.0→v0.51.0): Team Templates + materializador (FAB), `maestri team` por linguagem natural (confirmação humana obrigatória), editor visual de templates e comportamento de líder de grupo. "Montar equipe" segue clique-pra-posicionar (v0.49.0, §13). |
| [`uconsole.md`](uconsole.md) | Contexto do hardware (CM4) — atual. |
| [`15-ideias-backlog.md`](15-ideias-backlog.md) | **Doc vivo:** fila de ideias capturadas durante outras tarefas — não implementadas até serem puxadas explicitamente. |
| [`../AGENTS.md`](../AGENTS.md) · [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | Regras de processo (atemporais). |

## 📐 Planejamento (versionado em docs/ — espelha o `_bmad-output/` do MVP)
| Doc | Estado |
|---|---|
| [`prd.md`](prd.md) | PRD do **MVP** — canvas/WYSIWYG eram "fora de escopo" mas foram entregues; ver nota no topo e `STATUS.md`. |
| [`architecture.md`](architecture.md) | Arquitetura — **fundação fiel ao código**; partes "futuro pós-MVP" já entregues (ver nota). |

## 📚 Research / auditoria (HISTÓRICO — point-in-time, ok serem antigos)
| Doc | Estado |
|---|---|
| [`01-pesquisa-maestri.md`](01-pesquisa-maestri.md) | Research inicial (2026-06-21). Recomendações "evitar canvas" foram superadas. |
| [`02-pesquisa-equipes-autonomas.md`](02-pesquisa-equipes-autonomas.md) | Research; princípios atemporais. |
| [`04-pesquisa-stack-duravel.md`](04-pesquisa-stack-duravel.md) | Base da regra global de stack durável; vigente. |
| [`05-pesquisa-cabos-interativos.md`](05-pesquisa-cabos-interativos.md) | Research pré-cabos (ADR-11/13). |
| [`11-pesquisa-canvas-infinito-gpu.md`](11-pesquisa-canvas-infinito-gpu.md) | Já **auto-corrigido** (nota no topo): resolvido no CM4 (v0.24). |
| [`12-pesquisa-cabo-fisica.md`](12-pesquisa-cabo-fisica.md) | **Atual** — casa com v0.34/ADR-14. |
| [`16-pesquisa-diferenciais-n8n-frameworks-agente.md`](16-pesquisa-diferenciais-n8n-frameworks-agente.md) | Research (2026-07-02): n8n + BMAD/GSD/Beast Mode/Claude Code Agent Teams/gstack/CrewAI — diferenciais pro painel visual estilo n8n. |
| [`17-pesquisa-comunidade-melhorias.md`](17-pesquisa-comunidade-melhorias.md) | Research (2026-07-02): mineração de comunidade (Opus 4.8 + Codex) — dicas de usuários (Maestri + Vibe Kanban/Claude Squad) p/ um gestor visual de agentes. Tema: *less babysitting*. |
| [`18-plano-estado-por-no.md`](18-plano-estado-por-no.md) | **Plano cirúrgico ENTREGUE:** sistema de estado por nó / "precisa de você" (#1 da pesquisa) — Blocos 1+2 (v0.52.0) + Bloco 3 (v0.53.0): estado "aguardando" + ícones Lucide + atenção-união + minimapa + monitor padrão-ON nos nós-agente. |
| [`19-plano-medidor-custo.md`](19-plano-medidor-custo.md) | **Plano cirúrgico:** F1 medidor de custo/tokens — **Blocos A+B+C ENTREGUES em v0.54.0** (preço vendorizado + custo + display por nó, absorve PR #9). Bloco D (budget cap) pendente. |
| [`21-plano-unload-no-ram.md`](21-plano-unload-no-ram.md) | **Plano cirúrgico:** "unload" de nó (item #3, backlog) — descarregar/retomar p/ liberar RAM no CM4 via **kill-and-resume por CAPTURA de sessão** (`--resume`; Congelar/CRIU descartados). Fundação provada (investigação + medição de RAM + spike runtime + revisão adversarial Fable). Sequência A′→B→C→D — pronto pra virar stories. |
| [`25-plano-reattach-orfaos.md`](25-plano-reattach-orfaos.md) | **Plano cirúrgico ENTREGUE (v0.57.0, R1+R2+R3):** reattach de nós órfãos pós-crash (dor P2, `docs/24`). Dirty-flag + handler de sinal (R1) → detecção no boot + flag `orphan` própria (R2) → âmbar "recuperável" + Reanexar/Novo/Arquivar (R3). Revisado adversarialmente pelo Fable (§10; 4 correções, núcleo mais simples). R4 (worktree órfão) adiado. |
| [`22-pesquisa-dores-maestri.md`](22-pesquisa-dores-maestri.md) | Research (2026-07-03, BMad market-research + 4 agentes por canal): **29 dores dos usuários do Maestri** (só feedback negativo; citação+URL+data+autor+confiança) + perfil de quem reclama + dores→oportunidades + Anexo C (panorama de similares). |
| [`23-pesquisa-dores-concorrentes.md`](23-pesquisa-dores-concorrentes.md) | Research (2026-07-03, prompt-template do Fable + 13 lotes/3 ondas): **dores de 29 concorrentes** (41 capítulos — canvas, orquestradores, CLI/tmux, gigantes com recorte multi-agente) + **13 padrões transversais do nicho (P1-P13)**. Limitação declarada: Reddit ficou cego (crawler bloqueado). |
| [`24-analise-dores-vs-app.md`](24-analise-dores-vs-app.md) | **Análise cruzada (2026-07-03):** dores dos docs 22+23 × estado v0.55.0 — 9 padrões já cobertos (posicionamento), 2 em desenvolvimento (unload/RAM), **12 lacunas implementáveis ranqueadas em 3 níveis** + anti-padrões a evitar. Alimentou a fila do `15-ideias-backlog.md`. |

## ⚠️ Roadmaps & auditorias com DEFASAGEM (ler com a nota datada no topo)
| Doc | Cuidado |
|---|---|
| [`03-roadmap-melhorias.md`](03-roadmap-melhorias.md) | Gap analysis "vs v0.6.0": muito do ❌/🟡 **já foi entregue** (Fases 1-5). |
| [`10-roadmap-fases.md`](10-roadmap-fases.md) | Fases 1-3 **entregues** (apresentadas como futuras); Fases 4-7 ainda válidas. |
| [`06-maestri-comportamento-auditoria.md`](06-maestri-comportamento-auditoria.md) | Anterior a v0.34-37. |
| [`07-maestri-ui-ux-auditoria.md`](07-maestri-ui-ux-auditoria.md) | Baseline de UI já superado (minimapa/grid/física/estado já existem). |
| [`08-pesquisa-diferenciais-melhoria.md`](08-pesquisa-diferenciais-melhoria.md) | Backlog válido; o medidor de custo/tokens segue **não entregue**. |
| [`09-ideias-apps-similares.md`](09-ideias-apps-similares.md) | Catálogo de ideias; várias já saíram (minimapa/grupos/grid/notas). |

## 📦 `_bmad-output/` (GITIGNORED — planejamento do MVP, histórico)
Não versionado no git. PRD/architecture têm cópia em `docs/`. `sprint-status.md` e `roadmap.md`
**param na v0.1.0** (recebem nota de defasagem); spikes e `vX.Y.Z-plan.md` são point-in-time.
