# Índice de documentação — maestro console

> Mapa de TODOS os docs, com o estado de cada um. **Atualizado: 2026-07-01 (v0.46.0).**
> Regra: **research/auditoria são point-in-time** (legítimo serem antigos — registram a decisão
> da época); o que descreve "estado/roadmap" e ficou congelado no MVP recebeu **nota de defasagem**.

## 🟢 Canônicos (fontes de verdade — sempre atuais)
| Doc | O que é |
|---|---|
| [`../CHANGELOG.md`](../CHANGELOG.md) | Histórico real de versões (v0.1.0→v0.46.0). |
| [`ADR.md`](ADR.md) | Decisões arquiteturais (ADR-1..20), versionado, imutável. |
| [`STATUS.md`](STATUS.md) | Estado atual / o que foi entregue (resumo + ponteiros). |
| [`13-maestro-mode.md`](13-maestro-mode.md) | **Feature (atual):** Maestro mode seguro + auto-aprovação + cabo headless (ADR-16..20). |
| [`14-plano-orquestracao-equipe.md`](14-plano-orquestracao-equipe.md) | **Plano cirúrgico (a implementar):** orquestração de equipe (Team Templates + materializador reusando o Grupo do canvas). |
| [`uconsole.md`](uconsole.md) | Contexto do hardware (CM4) — atual. |
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
