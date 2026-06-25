# Pesquisa: desenvolver com maestria usando IA — escolhas de stack duráveis

> Data: 2026-06-25 (UTC) · PT-BR
> Origem: deep-research multi-fonte com verificação adversarial (106 agentes · 24 fontes · 103 claims extraídos → 25 verificados → 13 confirmados, 5 derrubados).
> Motivador: o app *maestro console* nasceu em GTK3 (2026) e teve que migrar para GTK4 na mesma leva de desenvolvimento. Esta pesquisa investiga como evitar esse tipo de erro e virou **regra global** em `/home/kali/AGENTS.md` (seção "Escolha de tecnologia/stack durável").

---

## Resumo executivo

Para desenvolver com maestria usando IA como ferramenta principal ("vibe coding" profissional), a prática central é **tratar a escolha de tecnologia como decisão de DADOS verificáveis, não de achismo do modelo**: o conhecimento da IA tem data de corte e, mesmo nos melhores modelos sem dados em tempo real, parte das recomendações de dependência é fabricada ou aponta para versões/APIs já desatualizadas do corpus de treino.

A regra de ouro para stacks duráveis: **casar a longevidade da tecnologia com a vida esperada do projeto e adotar a versão major atual e ativamente mantida — nunca uma já em modo manutenção.** A pressão para migrar quase nunca vem de "falta feature"; vem de risco de segurança/compliance quando o upstream para de lançar patches (EOL). Por isso o status de EOL/manutenção deve ser avaliado **antes** de adotar.

---

## Tema 1 — Por que a IA recomenda stacks que envelhecem

| Achado | Confiança | Fonte |
|---|---|---|
| Escolha de stack/dependência é problema de **dados**, não de raciocínio; recomendações de versão da IA devem ser verificadas externamente, nunca tratadas como atuais. | alta (3-0) | [Sonatype](https://www.sonatype.com/press-releases/sonatype-research-on-ai-coding-safety) · [OpenSSF](https://best.openssf.org/Security-Focused-Guide-for-AI-Code-Assistant-Instructions.html) |
| Mesmo os melhores modelos sem dados em tempo real **fabricam ~1 em 16 (≥6%)** das recomendações de dependência (estudo mar/2026, ~258 mil recomendações, 7 modelos de fronteira; GPT-5 chegou a 27,8%). | alta (3-0) | [Sonatype](https://www.sonatype.com/press-releases/sonatype-research-on-ai-coding-safety) |
| LLMs produzem código com **APIs depreciadas** sistematicamente (DUR até 37%; 70-90% sob prompts antigos). Causa: a API depreciada estava no treino sem conhecimento posterior da depreciação. | alta (3-0) | [arXiv 2406.09834 (ICSE'25)](https://arxiv.org/abs/2406.09834) |

## Tema 2 — Como escolher stack durável

| Achado | Confiança | Fonte |
|---|---|---|
| Adotar a versão **major atual e ativamente mantida**; nunca uma já em modo manutenção. | alta (3-0) | (caso GTK abaixo) |
| **Casar longevidade com a vida do projeto** — projeto de vida longa pede tecnologia estável/estabelecida ("boring technology"; "o maior custo da tecnologia é a manutenção"). | média (3-0) | [Medium/curiousraj](https://medium.com/@curiousraj/balancing-innovation-and-longevity-a-practical-guide-to-software-stack-selection-10cdf41f4daa) |
| A pressão para migrar vem de **risco de segurança no EOL**, não de falta de feature → avaliar EOL/manutenção **antes** de adotar. | média (3-0) | [HeroDevs](https://www.herodevs.com/blog-posts/why-enterprises-are-choosing-long-term-support-over-forced-migrations) |
| Migração forçada custa de **meses a anos** e pode introduzir mais risco do que remove. | média (3-0) | [HeroDevs](https://www.herodevs.com/blog-posts/why-enterprises-are-choosing-long-term-support-over-forced-migrations) |
| **Versão de número maior ≠ mais longeva** — releases "rolling" podem ter EOL antes de um LTS de número menor. Recência não é prova de durabilidade. | alta (3-0) | [endoflife.date](https://endoflife.date/mariadb) |

## Tema 3 — Guardrails de processo

| Achado | Confiança | Fonte |
|---|---|---|
| Instruir a IA a **preferir o último release estável E verificar tudo externamente**. | alta (3-0) | [OpenSSF](https://best.openssf.org/Security-Focused-Guide-for-AI-Code-Assistant-Instructions.html) |
| **ADRs atômicos e imutáveis** (um por decisão; nunca editado depois, só "Superseded by X"). | alta (3-0) | AWS Prescriptive Guidance · Azure Well-Architected · M. Nygard |
| **Isolar a parte volátil** (toolkit de UI, SDKs) atrás de uma **Camada Anticorrupção** para baratear trocas futuras. | alta (3-0) | [Microsoft Learn (DDD)](https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer) |
| **Reprodutibilidade com pinning exato** — lockfiles, imagens por digest SHA256 (não `latest`), GitHub Actions por SHA (houve ataque de supply-chain por tag mutável, mar/2025). | alta (3-0) | [OpenSSF](https://best.openssf.org/Security-Focused-Guide-for-AI-Code-Assistant-Instructions.html) |

---

## Caso concreto: GTK3 → GTK4 (erro evitável, confirmado)

- **GTK4 é o major atual desde 16/dez/2020.** — [blog GTK](https://blog.gtk.org/2020/12/16/gtk-4-0/) *(fonte primária)*
- **GTK3 está congelado:** a partir de 3.24.52 (mar/2026) caiu para **1 release/ano**, só correções de bug/crash, próximo só em **mar/2027** — desaceleração deliberada para empurrar a migração. — [NEWS GTK](https://gitlab.gnome.org/GNOME/gtk/-/raw/gtk-3-24/NEWS) · [Phoronix](https://www.phoronix.com/news/GTK3-Annual-Release-Cadence) *(primária/secundária)*

Linha do tempo da UI do *maestro console* (via git):

| Fase | Versão | Stack | Commit |
|---|---|---|---|
| TUI (terminal) | v0.2.0 | terminal | `4d44396` |
| Web UI + canvas SVG | v0.4.0 | web/SVG | `485c46c` |
| App nativo | v0.5/0.6 | **GTK3** | `3543e30` (spike) |
| Migração | v0.13.0 | **GTK4** | `b0d08a2` |

→ O spike `3543e30` escolheu **GTK3 para um app novo em ~jun/2026**, quando o GTK4 já era o major maduro há 5+ anos. A tecnologia "nasceu velha" e exigiu migração na mesma leva. A regra global (itens 1 e 2) teria barrado isso no spike.

---

## Ressalvas (honestidade intelectual)

- **Sensibilidade temporal:** os fatos são de jun/2026; a própria regra exige re-verificar ao vivo (o conhecimento da IA tem data de corte).
- **Incentivo de fornecedor:** Sonatype e HeroDevs vendem soluções relacionadas; as claims com esse viés foram rebaixadas mas têm corroboração independente.
- **Derrubados na verificação (NÃO usar):** números exatos de janelas LTS/STS (3 anos / 18 meses), os valores específicos do MariaDB, e o caso ".NET Core 3.1" — a *direção* sobrevive, os números específicos não.

## Perguntas em aberto

1. Melhor forma de dar "grounding" em tempo real a Claude Code + Codex num ambiente Linux/ARM offline-first (MCP local de pacotes/CVE? hook que consulta endoflife.date/PyPI antes de fixar versão?).
2. Fronteira concreta de Camada Anticorrupção que melhor isole a UI volátil (GTK4 vs Qt6/Toga/web-view) com menor custo de troca.
3. Existe um "min-release-age" recomendado (idade mínima de um release antes de adotar) para o ecossistema Python/PyPI?

## Fontes primárias/autoritativas

- OpenSSF — Security-Focused Guide for AI Code Assistant Instructions (Linux Foundation)
- arXiv 2406.09834 — *Deprecated APIs in LLM-generated code* (ICSE'25, DOI 10.1109/ICSE55347.2025.00245)
- Microsoft Learn — Anti-Corruption Layer pattern (DDD / Eric Evans)
- Blog/NEWS oficiais do GTK + Phoronix (status GTK3/GTK4)
- Sonatype — research on AI coding safety (mar/2026)
