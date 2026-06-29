# Editar Terminal — especificação (clone do diálogo "Edit Terminal" do Maestri)

> **Status:** ATUAL · criado 2026-06-29 · base da feature "Editar Terminal" do canvas nativo.
> Fonte da verdade da feature. Pesquisa: docs oficiais do **Maestri** (themaestri.app, acesso
> 2026-06-29) + auditoria do nosso código (`maestro/native/canvas.py`, `state.py`, `themes.py`,
> `agents.py`, `ask_capture.py`) + nossos docs de paridade (`docs/01/03/06/08`).

## Contexto

O app de referência é o **Maestri** (`themaestri.app`) — macOS/SwiftUI, *"orchestration canvas
for AI agents"*. Cada terminal é um nó num canvas infinito; agentes (Claude Code, Codex, OpenCode
ou shell) conversam por **orquestração de PTY** (sem API). O diálogo **Edit Terminal** abre por
*botão direito no terminal → Edit Terminal* e tem 3 abas: **Detalhes / Aparência / Agente**.

**Lacuna que esta doc fecha:** o diálogo "Editar Terminal" não estava descrito em nenhum doc
nosso. As capacidades apareciam soltas e, no caso do **Maestro mode**, com entendimento ERRADO
("pin preset manager") — corrigido abaixo.

## Decisão de arquitetura (ADR informal)

Maestri usa **diálogo modal com abas**; nosso app usa **cápsula contextual**. Reconciliação
**aprovada pelo usuário**: a cápsula do terminal tem um botão **⚙ Editar** que abre o diálogo
de abas. Cápsula = ações rápidas (renomear/centralizar/conectar/fechar); diálogo = config
completa. Fiel ao Maestri **e** à regra de cápsulas (`AGENTS.md`).

## Divergências deliberadas do Maestri (nosso modelo)

1. **Maestro mode → mediado pelo orquestrador.** Nossos ADR-2/10/11 abandonaram o modelo
   terminal-a-terminal por um mediado pela **ask-bus**. Os comandos `recruit/dismiss/wire/list`
   mapeiam pra **nossa skill roteada pelo host** (`install_ask_skill`), não pra um canal direto.
2. **Tema por-terminal = override do global.** No Maestri o tema é global (Settings → Terminal →
   Appearance); o print mostra por-terminal. Faremos **override por-nó** sobre o tema global.
3. **Roles via `role.json` sidecar.** Adotar o sidecar portátil `{name, color, prompt}` no cwd
   (`.maestri/`), além dos profiles TOML, pra casar com "Descobrir responsabilidades".

## Especificação por capacidade

Legenda do estado no nosso app: ✅ pronto · 🟡 parcial · ❌ ausente.

### Aba Detalhes

| Campo | Comportamento no Maestri (confiança) | Nosso estado | Implementação no clone |
|---|---|---|---|
| **Nome** | Identifica o terminal | ✅ `node_name`/`set_node_name` | Entry; já ligado (Fase 0) |
| **Comando** | Preset de agente ou "plain shell"; campo livre plausível mas não documentado (Média) | ❌ só `/bin/bash`/agente | argv `["/bin/bash","-lc", f"{cmd}; exec bash -i"]`; respawn ao mudar |
| **Monitorar atividade** | **Quiescência de output** (terminal parou = agente terminou/espera), **só não-focados** → ponto de atenção + notify macOS + resumo Ombro (Alta no mecanismo) | 🟡 quiescência do maestro-ask + `⚠N` + notify-send | toggle por-nó; `contents-changed` + timer de quiescência quando não-focado |
| **Maestro** | Promove a **manager**: `recruit` (cria terminal-filho conectado abaixo + agente/role), reassign role/editar prompt, `wire` (liga notas a recrutas), `dismiss`; `maestri list` mostra nome+role+conexões (Alta) | 🟡 base: ask-bus, `_new_agent_terminal`, cabos | toggle por-nó; expandir skill com `recruit/dismiss/wire/list` roteados pelo host |
| **Atalho** | Foco rápido (Auto ou tecla) | 🟡 Ctrl+Shift+1..9 por ordem | seletor Auto/tecla por-nó |
| **Diretório de Trabalho** | cwd por-terminal; **alimenta o Discover Roles** (varre cwd por `role.json`) (Alta) | ❌ spawn cwd=None | cwd no `spawn_async`; "Procurar" = FileChooser de pasta |
| **SSH Remoto** | Host/User/Port + chaves `~/.ssh`; instala **shim `maestri`** no remoto + **túnel reverso** (bind localhost) (Alta) | ❌ (só Web UI) | config por-nó; comando via `ssh`; shim + túnel pro callback da ask-bus |

### Aba Aparência

| Campo | Comportamento no Maestri (confiança) | Nosso estado | Implementação no clone |
|---|---|---|---|
| **Ícone** | Por-terminal, no cabeçalho (Alta) | ❌ (temos badges de role) | grid com nosso set symbolic (infra de ícones bundlados) |
| **Cor** | accent = **badge do role** (Média) | ❌ no terminal (a nota tem) | picker de cor da nota → tint do cabeçalho |
| **Fonte** | No print (SF Mono 13pt); **não documentada** (Baixa em doc, mas existe no app) | ❌ no terminal (a nota tem) | `term.set_font(Pango.FontDescription)`; picker da nota |
| **Tema** | **Sistema/Escuro/Claro/Custom**; Custom = 30+ esquemas iTerm2 (Dracula, Catppuccin, Tokyo Night, Nord, One Dark, Solarized, Nord, Everforest…); user themes em formato **Ghostty** em `~/.maestri/terminal/themes/` (Alta global / Média por-terminal) | 🟡 4 temas **globais** (`themes.py`) | override por-nó; importador de esquemas iTerm2/Ghostty |

### Aba Agente

| Campo | Comportamento no Maestri (confiança) | Nosso estado | Implementação no clone |
|---|---|---|---|
| **Responsabilidade (role)** | role = `{name, color, prompt}` num **`role.json`** sidecar no projeto (`.maestri/`), **injetado quando o agente inicia**; gerido em Settings → Agents (Alta) | 🟡 profiles TOML + AGENTS.md no workspace | cards de role (teams/profiles + sidecars); injeta o prompt no start |
| **Buscar role** | busca na lista | ❌ | campo de busca sobre os cards |
| **Descobrir responsabilidades** | = **Discover Roles**: varre o **cwd** por `role.json` e importa (Alta) | ❌ | varrer cwd por `role.json` |
| **Remover responsabilidade** | desatribui o role (Alta) | ❌ | botão remover |

## Plano em fases (cada fase = 1 PR, persiste por-nó, testada)

| Fase | Entrega | Reusa | Esforço |
|---|---|---|---|
| **0 — Fundação** | Diálogo com abas (pela cápsula ⚙); scaffold `node_cfg`/`set_node_cfg`; **Nome** ligado; esta doc | `_dialog`, `set_node_name` | P |
| **1 — Aparência: Fonte+Cor+Ícone** | fonte (`set_font`), cor accent, ícone no cabeçalho | picker fonte/cor da nota, ícones bundlados | M |
| **2 — Aparência: Tema** | override por-nó: Sistema/Escuro/Claro + 4 nossos + **Custom** (importar iTerm2/Ghostty) | `themes.py`, `_apply_theme` | M-G |
| **3 — Detalhes: Comando+cwd+Atalho** | comando custom, diretório (Procurar), atalho | `make_terminal`/spawn, roster | M |
| **4 — Detalhes: Monitorar atividade** | toggle por-nó: quiescência (não-focado) → atenção + notify | quiescência, `_refresh_attention`, `notify` | M |
| **5 — Agente: responsabilidades** | atribuir/buscar role, editar instruções, **Descobrir**, Remover; `role.json` injetado | controller/teams, `install_ask_skill`, Workspace | M-G |
| **6 — Maestro mode** | `recruit/dismiss/wire/list` via skill roteada (cria terminais conectados + atribui role) | ask-bus, `_new_agent_terminal`, cabos | G |
| **7 — SSH Remoto** | config por-nó (Host/User/Port, `~/.ssh`), comando via ssh, shim + túnel reverso | ask-bus | G (avançado) |

## Persistência (ui_state)

Genérico por-terminal: **`nodecfg_{nid}_{key}`** via `CanvasModel.node_cfg/set_node_cfg`
(`state.py`). Chaves por fase: `command`, `cwd`, `monitor`, `maestro`, `shortcut`, `icon`,
`color`, `theme`, `font`, `role`, `ssh`. Nome continua em `nodename_{nid}`. Tudo segue a regra
"abre igual fechou" (`AGENTS.md`).

## Fontes (acesso 2026-06-29)

- Maestri — Docs: [Intro](https://www.themaestri.app/en/docs/intro) ·
  [Terminals & Agents](https://www.themaestri.app/en/docs/terminals) ·
  [Maestro Mode](https://www.themaestri.app/en/docs/maestro) ·
  [Remote SSH](https://www.themaestri.app/en/docs/ssh) ·
  [Ombro](https://www.themaestri.app/en/docs/ombro) ·
  [Connections](https://www.themaestri.app/en/docs/connections)
- Nossos docs de paridade: `docs/01-pesquisa-maestri.md`, `docs/06-maestri-comportamento-auditoria.md`
  (DEFASADO ~v0.6), `docs/03-roadmap-melhorias.md`, `docs/08-pesquisa-diferenciais-melhoria.md`.
- **Atenção (honestidade):** o rótulo exato "Monitorar atividade" como checkbox e o tema/cor/fonte
  **por-terminal** são inferidos do print + comportamento documentado (não verbatim nos docs); a
  sintaxe de `recruit/dismiss` não é publicada (só `maestri list` é verbatim).
