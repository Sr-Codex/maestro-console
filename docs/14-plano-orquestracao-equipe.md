# Plano cirúrgico — Orquestração de Equipe (Team Templates + materializador)

> **Plano de implementação** para retomar em SESSÃO NOVA (a sessão de origem ficou grande).
> Autossuficiente: um agente com acesso ao repo + memória consegue executar daqui.
> Data: 2026-07-01 (atualizado no mesmo dia com 2ª rodada de pesquisa, §2.1) · PT-BR · Precede o
> código (protocolo: analisar→pesquisar→**validar/plano**→codar).
> Feature aprovada pelo usuário; **fasear: Fase A primeiro** (determinística), depois Fase B (NL).

## 0. Como retomar (faça primeiro)
1. Confirmar que o **PR #44** (auto-approve + fixes) foi mergeado; senão, alinhar com o usuário.
2. Branch nova off `main`: `feat/team-orchestration`.
3. Ler este doc + `docs/13-maestro-mode.md` (feature) + ADR-16..20. Rodar `.venv/bin/pytest -q`.
4. Regras do projeto valem: PR-por-feature, testes 100%, runtime real, persistência ("abre igual
   fechou"), cápsulas de UI, 1 bump de versão por PR, ruff limpo no que tocar.

## 1. Objetivo (a dor do usuário)
Mandar UMA instrução e o maestro montar uma **organização inteira** — terminais + **grupos do canvas**
— de uma vez. Exemplo real (fluxo n8n):
```
T1 = você (maestro principal)
├─ 📁 Grupo "Equipe n8n"       → n8n-arquiteto · n8n-dev · qe-teste
├─ 📁 Grupo "Domínio externo"  → supabase-especialista · api-X · api-Y
└─ 📁 Grupo "Documentação"     → docs-escritor (CLAUDE.md, PRDs)
```
"crie a equipe n8n" → cria o **Grupo do canvas** rotulado + recruta os agentes DENTRO dele, com papéis,
conectados. Suporte a **templates reusáveis** E **linguagem natural**.

## 2. Veredito da pesquisa (2026-07-01) — o modelo profissional
Fontes completas nas transcrições da sessão; resumo do consenso (CrewAI, AutoGen Studio, LangGraph,
Claude Code Agent Teams, Anthropic, A2A):
- **Team = objeto declarativo de 1ª classe** (CrewAI `agents.yaml`; AutoGen "team spec" JSON na Gallery)
  — texto versionável/reusável com placeholders. **NÃO** só "layout salvo" (limite do Maestri).
- **Híbrido é o padrão certo:** *NL DESENHA um rascunho de spec → humano CONFIRMA → materialização
  DETERMINÍSTICA executa.* Puro-agêntico falha muito (62% dos projetos falhos deviam ter usado
  determinístico; 79% das falhas são de especificação/coordenação).
- **Papel = tripé** role + goal/mandato + backstory/instruções (nosso `Role` já cobre via `instruction`).
- **Grupo = caixa-preta** com líder; "delegate mode" (líder coordena, não compete por arquivo) a partir de 3.
- **Guard-rails duros:** **2–5 agentes por grupo** (avisar acima de ~8); **máx 2 níveis** de hierarquia;
  papel precisa de objetivo + formato de saída + fronteira; **não forçar multi-agente** (1 resolve a maioria).
- **Diferencial nosso vs Maestri:** o Maestri NÃO tem grupo visual rotulado nem team-template de 1ª
  classe — **nós já temos o Grupo do canvas**. É a nossa vantagem.

### 2.1 Aprofundamento — repos em crescimento rápido + players (2ª rodada, 2026-07-01)
Pesquisa adicional pedida pelo usuário (comunidade + repos crescendo rápido + como grandes players
fazem), comparada linha a linha com nosso design real (`teams.py`/`roles.py`/`groups.py`):
- **Confirma a arquitetura, não muda nada estrutural.** Google ADK (hierarquia em árvore), OpenAI
  Agents SDK (Manager pattern = orquestrador central chamando subagentes), Claude Agent SDK (lead
  agent + subagents com contexto isolado, report-by-artifact) e o próprio n8n (canvas visual +
  sub-workflows reusáveis) validam: manager humano/central, contexto isolado por agente, JSON
  interno, Fase A determinística → Fase B NL com confirmação humana.
- **Dado empírico novo (não estava na 1ª rodada):** dois papers de 2026 (arXiv:2506.18348,
  arXiv:2506.00066) medem *sweet spot* de **3–4 agentes por grupo**, com degradação visível de
  5→10. Afina (não substitui) os guard-rails do §8.
- **CrewAI** (`agents.yaml`, Crews vs Flows, placeholders `{topic}` via `str.format`) segue sendo a
  referência mais próxima do nosso `TeamTemplate`.
- **Risco de dependência descartado:** Microsoft AutoGen fragmentou em 3 forks em 2026 (Agent
  Framework oficial, AutoGen v0.7.x pesquisa, AG2 comunitário) — reforça manter vocabulário PRÓPRIO
  (`Role`/`Team`/`Group`), nunca copiar API de terceiro 1:1.
- **"OpenClaw"** (crescimento mais rápido da história do GitHub em 2026) não é um team-template —
  é agente autônomo solo; múltiplos papers de segurança 2026 (arXiv:2603.27517, arXiv:2604.03131)
  reforçam (não mudam) nossa postura ADR-16..20.
- Decisões concretas que isso resolve: ver §3 (`leader` no schema, placeholders promovidos p/ Fase A)
  e §7/§8 (defaults de UI).

## 3. Design aprovado
Entidades (espelham CrewAI/LangGraph):
- **`AgentSpec`** = reusa `Role` (`engine/teams.py`): `{ name (papel), agent (claude/codex), instruction, color }`.
  (opcional futuro: `goal`, `skills[]` p/ descoberta A2A — NÃO no v1.)
  - **Placeholders** (`{projeto}` etc.) via `str.format` em `name`/`instruction`/`description` —
    promovido de "v2" para **Fase A** (baixo custo, alto valor; padrão CrewAI `agents.yaml`,
    2026-07-01 — ver §2.1). Campos sem placeholder passam por `str.format` inofensivamente.
- **`GroupSpec`** = `{ name, color?, members: [AgentSpec], leader?: str }`. `leader` (nome do papel
  líder do grupo) é **só schema no v1** — sem comportamento de delegate-mode ainda; adicionado agora
  pra evitar migration de dado depois (Magentic-One/OpenAI Manager pattern confirmam que liderança de
  grupo é o padrão a partir de 3 membros — 2026-07-01, ver §2.1).
- **`TeamTemplate`** = `{ name, description?, groups: [GroupSpec], manager? }`.

Fluxo híbrido:
- **Fase A (determinística):** humano escolhe um TeamTemplate no FAB → `_materialize_team(spec)` cria
  os Grupos + recruta os membros DENTRO de cada grupo + papéis/badges + cabos + layout.
- **Fase B (NL):** o manager recebe NL → gera o mesmo `TeamTemplate` (JSON) → host mostra p/ CONFIRMAR
  → materializa (reusa Fase A).

## 4. Mapeamento no código atual (reuso — arquivos/funções REAIS)
| Peça do design | Já existe | Onde |
|---|---|---|
| `Role` (papel) | ✅ | `engine/teams.py:31` `Role{name,agent,instruction,color}` + `to_dict/from_dict` |
| `Team`/builtins | ✅ (flat) | `engine/teams.py:61` `Team{name,roles[]}`; `BUILTIN_TEAMS` (coder-reviewer) |
| Biblioteca de roles persistida | ✅ | `engine/roles.py` `save_role_library`/`load_role_library` (JSON atômico) — **espelhar p/ templates** |
| **Grupo do canvas** | ✅ | `engine/groups.py` `Groups.create(title,color,x,y,w,h)` + `Group`; canvas `_create_group:5254`, `_load_group`, `_group_members:5381`, `_autofit_group` |
| Recrutar 1 agente c/ papel | ✅ | `canvas._maestro_dispatch` recruit (`:3866`) + `_new_agent_terminal` (`+_add_node`, `_place_below`) |
| Papel → workspace | ✅ | `_apply_node_role` (bloco marcado no AGENTS.md do ws isolado) |
| Auto-approve por nó | ✅ | `_node_auto_approve`, `_rebuild_agent_argv` |
| Tetos de segurança | ✅ | `MAESTRO_FLEET_CAP=12`, `MAESTRO_MAX_DEPTH=2`, `MAESTRO_MAX_RECRUITS=6`, rate-limit; `MUTATING_CMDS` |
| FAB (cápsula principal) | ✅ | `_build_fab` + `_action_spec`/`cbmap`; padrão `_open_*_dialog` |
| HUD do fleet | ✅ | `_build_fleet_hud`/`_fleet_hud_text` |

**⚠️ Insight crítico (grupo é GEOMÉTRICO):** a pertinência a um grupo é por **sobreposição** (`_group_members`
conta item que sobrepõe ≥25% do retângulo). **Não há "add_member".** Logo, "recrutar no grupo X" =
**criar o nó do agente POSICIONADO DENTRO do retângulo do grupo**. O `_autofit_group` faz o grupo abraçar
os membros. O materializador precisa **calcular posições** (grid) dentro do retângulo do grupo.

## 5. Plano cirúrgico — FASE A (determinística)

### 5.A1 — Modelo `TeamTemplate` (engine, testável, gi-free)
- Novo `engine/team_templates.py` (ou estender `teams.py`): dataclasses `AgentSpec`(=Role ou wrapper),
  `GroupSpec{name,color,members,leader=None}`, `TeamTemplate{name,description,groups,manager}` +
  `to_dict/from_dict`.
- **Interpolação de placeholders:** função `render(template, **kwargs)` (ou método `TeamTemplate.render`)
  que aplica `str.format(**kwargs)` nos campos texto (`name`/`instruction`/`description`); chaves
  ausentes não devem quebrar — usar um dict tolerante (`defaultdict` ou `.format_map` com fallback) em
  vez de `str.format` cru, que levanta `KeyError` em placeholder não fornecido.
- Persistência: `load_team_templates()/save_team_templates()` — JSON atômico (temp+os.replace) em
  `~/.config/maestro-console/team_templates.json`, **espelhando `roles.py:save_role_library`**.
- 2–3 **templates built-in** (ex.: `dev-trio` = coder+reviewer+qe; e um exemplo tipo o n8n como amostra,
  com placeholder `{projeto}` na instrução pra demonstrar reuso).
- **Testes:** roundtrip to_dict/from_dict (incl. `leader`); save/load atômico; built-ins válidos;
  interpolação de placeholder (com e sem kwargs fornecidos, chave faltante não quebra). (rodam no `.venv`).

### 5.A2 — Materializador `_materialize_team(spec, *, manager=None)` (canvas)
Ordem (tudo na main thread; é ação do HUMANO via FAB → NÃO passa pelo rate-limit de agente):
1. **Guard-rails ANTES de criar nada:** validar total de membros ≤ `MAESTRO_FLEET_CAP - _fleet_count()`;
   avisar (dialog) se algum grupo > 5 (bloquear/confirmar acima de ~8); recusar se estoura o fleet.
2. Layout dos grupos: dispor os retângulos lado a lado (ex.: colunas), sem sobrepor, a partir de
   `_next_node_default()`/uma origem; cada grupo com largura p/ N membros (grid interno).
3. Para cada `GroupSpec`:
   a. `gid = self.groups.create(title=group.name, color=group.color, x, y, w, h)`; `self._load_group(...)`.
   b. Para cada `member` (AgentSpec), calcular posição `(px,py)` **dentro** do retângulo do grupo (grid).
      `nid = self._new_agent_terminal(member.agent, default=(px,py))`; setar `node_cfg(nid,'role',member.name)`;
      `_apply_node_role(nid)`; opcional `node_cfg(nid,'autoapprove','1')` + `_rebuild_agent_argv`; `_respawn_node`.
   c. Cabos: `self.edges.add(manager or <líder>, nid)` e registrar linhagem `_recruited_by[nid]=manager` se houver
      manager; senão top-level (humano é T1). **Decidir na implementação:** manager-agente vs humano-T1 (ver §7).
4. `_autofit_group(gid)` p/ o grupo abraçar; `_resize_plane()`; `plane.queue_draw()`; `_refresh_fleet_hud()`;
   auditar `self._audit('team_materialize', template=spec.name, groups=n, agents=m)`.
- **Reaproveitar** `_new_agent_terminal` (que já cria workspace, socket, roster, add_agent_instance) — NÃO
  duplicar. Cuidar do `_unique_nid` (já ciente do controller/roster após o fix desta sessão).

### 5.A3 — Entrada no FAB "🧩 Montar equipe"
- Adicionar ação no `_action_spec`/`cbmap` + botão no `_build_fab` (padrão `add(icon,emoji,tip,key)`), só quando
  `self._sock_server`/controller presentes.
- `_open_team_dialog()`: lista os TeamTemplates (built-in + salvos) com preview (grupos/papéis); botão
  **"Montar"** → `_materialize_team(spec)`. Botões p/ **criar/editar/salvar** template (espelhar o
  `_role_edit_dialog`). Persistência obrigatória.
- Se o template tiver placeholders, pedir os valores num campo simples antes de montar (`render(spec, **valores)`).
- **UI sugere 3–4 membros por grupo como default recomendado** (dado empírico: arXiv:2506.18348,
  arXiv:2506.00066 — sweet spot 3–4, degradação 5→10; ver §2.1) — isto é sugestão de UI/copy, os
  limites DUROS continuam os do §8 (aviso >5, trava ~8).

### 5.A4 — Testes Fase A
- Unit (engine): modelo + persistência (§5.A1).
- Unit (canvas, mockando widget como em `tests/test_maestro_mode.py` `_make_win`): `_materialize_team`
  cria N grupos e M agentes nas posições certas, seta papéis, liga cabos, respeita o guard-rail de fleet-cap
  (recusa quando estoura). Mockar `groups.create`, `_new_agent_terminal`, `_apply_node_role`.
- Runtime: boot smoke + materializar um template pequeno ao vivo (você) e ver os grupos+agentes.

## 6. Plano cirúrgico — FASE B (linguagem natural)
- **Skill do manager** (estender `maestro_skill_text` em `ask_bus.py`): ensina o schema do `TeamTemplate`
  (JSON) e o comando `maestri team --spec '<json>'` (ou `maestri team "<descrição>"` → o host pede ao
  próprio manager gerar o JSON).
- **Comando `team`** no `_maestro_dispatch`: recebe o spec JSON do agente → **NÃO materializa direto** →
  `GLib.idle_add` abre um **dialog de confirmação** mostrando o spec (grupos/papéis) → no OK do HUMANO →
  `_materialize_team(spec, manager=frm)`. (NL desenha, humano confirma, determinístico executa.)
- Como é iniciado por agente, o `team` é comando MUTADOR: entra em `MUTATING_CMDS` (rate-limit) e nos gates;
  mas a materialização em si roda após confirmação humana (trusted).
- **Guard-rails no schema:** o skill instrui 2–5 por grupo, máx profundidade 2, papéis com objetivo+saída.
- **Testes:** parse do spec NL→JSON (mock), rota `team`→confirm→materialize, rejeição de spec inválido/grande.

## 7. Decisões abertas (resolver no início da implementação)
1. **Manager-agente vs humano-T1:** no FAB (humano) os agentes conectam a quê? Opções: (a) top-level
   (humano é o maestro, agentes só agrupados) — mais simples; (b) exige um nó-manager selecionado como pai.
   *Recomendação:* v1 = top-level no FAB; no NL o `frm` (manager que chamou) é o pai. Confirmar com o usuário.
2. **Líder de grupo (delegate mode):** ~~a pesquisa sugere um coordenador por grupo (3+). v1 pode ser
   SEM líder~~ **RESOLVIDO (2ª rodada, §2.1):** campo `GroupSpec.leader` entra no schema da Fase A
   AGORA (custo zero, evita migration futura), mas **sem comportamento** de delegate-mode ainda — o
   manager global continua coordenando na Fase A. Comportamento de líder-por-grupo fica pra depois.
3. **Formato do template:** JSON (mais simples de persistir/validar) vs YAML (mais legível, à la CrewAI).
   *Recomendação:* JSON interno + talvez export YAML depois. **Confirmado pela 2ª rodada** — sem mudança;
   considerar só EXIBIR o template como YAML no dialog de confirmação (Fase B) por legibilidade.
4. **Placeholders** (`{projeto}`): ~~v1 pode omitir~~ **RESOLVIDO (2ª rodada, §2.1):** promovido para a
   Fase A — baixo custo (`str.format`/`.format_map` nos campos texto), alto valor (é exatamente o pedido
   original do usuário de reuso de template entre projetos).

## 8. Guard-rails & tetos (não regredir a segurança dos ADR-17/18)
- Total de agentes do template ≤ `MAESTRO_FLEET_CAP` (12); recusar/avisar se estoura.
- Avisar > 5 por grupo; bloquear/confirmar > ~8 (anti "agentes demais").
- Profundidade ≤ 2 (grupos v1 são flat → depth 1).
- Materialização por humano (FAB/confirm) é trusted → ok bypassar o rate-limit de agente; materialização
  **iniciada por agente sem confirmação humana = PROIBIDA** (mantém "autoridade no host", ADR-17).
- Auditar `team_materialize`. HUD do fleet reflete o novo total.

## 9. Riscos
- **Custo/latência** (cada agente = terminal + chamadas LLM; caro no CM4): por isso os guard-rails de tamanho.
- **Layout** dentro do grupo (posições/grid) — testar visualmente; `_autofit_group` ajuda.
- **Contenção**: materializar N agentes cria N spawns bwrap ~simultâneos; observar o respawn state-machine.

## 10. Definition of done (Fase A)
Template persistido (com `leader` no schema + interpolação de placeholder) + `_materialize_team` + FAB
"Montar equipe" (sugerindo 3–4 membros/grupo) + built-ins + guard-rails, testado (unit + runtime ao
vivo), ruff limpo, CHANGELOG + bump + PR. Depois Fase B (NL→confirma→materializa).
</content>
