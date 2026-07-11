# Plano — Cápsula contextual de Grupo

> Data: 2026-07-11 · PT-BR · Origem: backlog `docs/15` (2026-07-08, auditoria de UI do Fable) —
> conformidade com a regra do `AGENTS.md` ("todo elemento com config tem cápsula contextual ao
> selecionar"). Grupo hoje só configura por duplo-clique → `_group_dialog`, e o apagar é SEM
> confirmação. **Revisado adversarialmente pelo Fable (2026-07-11): APROVA COM EMENDAS** —
> 9 achados (3 ALTA) incorporados abaixo. Decisões do usuário: pílula ENXUTA
> (`[⚙→diálogo] [● cor] [🗑 confirmado]`, sem ✏ dedicado) e clique no CORPO do grupo segue
> sendo fundo (pan/desseleciona) — só a faixa de título seleciona.

## Descobertas (medidas no código, validadas pelo Fable)
- **Pílulas são overlays FIXOS** topo-centro (`halign=CENTER/valign=START/margin_top=66`,
  uma visível por vez) — não seguem o elemento → posição p/ grupo é trivial.
- `_select` (2640) usa `_frame_of` + CSS `.selected`; grupo é **cairo sem frame** →
  `_frame_of(("group",gid))` = None e o CSS é skipado de graça. MAS **`_select` nunca
  redesenha o plane** (seleção de nó/nota é CSS de widget; GTK invalida sozinho).
- `_pan_begin` (2677) já tem os hit-tests de grupo (`_group_corner_hit` 2725,
  `_group_title_band_hit` 2730) DEPOIS do `_select(_elem_at(picked))` da 2701 (que p/ área
  de grupo dá `_select(None)`).
- `_group_dialog` (7049) tem nome/cor/apagar; `_close_group` (7103) não toca `_selected`.
- Multi-workspace NÃO é problema: `_switch_workspace` faz `os.execv` (processo renasce).

## Emendas do Fable (obrigatórias)
1. **ALTA — `queue_draw` DENTRO do `_select`** quando a seleção antiga OU nova é grupo.
   Sem isso o outline cairo não aparece no clique parado (só no release, por acidente do
   `_pan_end`) e fica STALE ao trocar pra um nó (caminho `_on_frame_press` não redesenha).
   No `_select` (1 ponto), não nos call-sites (são muitos; esqueceríamos um).
2. **ALTA — apagar confirmado nos DOIS caminhos**: pílula E `_group_dialog` convergem num
   único `_confirm_close_group(gid)` (via `_confirm_dialog`, destructive). Confirmar só na
   pílula deixaria vivo o caminho destrutivo original.
3. **ALTA — `_select(None)` DENTRO do `_close_group`** (se o grupo apagado é o selecionado)
   — senão a pílula fica órfã apontando pra gid morto. Espelha `_confirm_close_node`.
4. MÉDIA — guarda **`_sel_gid()`**: None se a seleção não é grupo OU o gid não existe mais
   em `_group_base` (espelha `_sel_nid`; popover aberto enquanto o grupo morre → no-op).
5. MÉDIA — **o popover de cor da NOTA é inreutilizável** (paleta hex livre vs cores
   NOMEADAS do grupo persistidas como string). Extrair o loop de swatches do
   `_group_dialog` num helper `_group_swatches(on_pick)` usado pelo diálogo E pelo popover.
6. MÉDIA — testes gi declarados (CI pula → rodar no python do SISTEMA): ver §Testes.
7. BAIXA (decisão do usuário) — clique no corpo do grupo segue desselecionando (fundo).
8. BAIXA — guard anti-"grupo ressuscitado": nos branches de grupo do `_pan_update`, se o
   gid sumiu de `_group_base` no meio do gesto, abortar o drag/resize (1 linha cada).
9. BAIXA (decisão do usuário) — pílula ENXUTA: ⚙ abre o `_group_dialog` (renomear fica lá).

## Peças (fatiado)
1. `_build_group_ctx()` — bar overlay fixo `[⚙ editar] [● cor popover] [🗑 apagar]`,
   registrado no overlay junto das outras pílulas; handlers usam `_sel_gid()` guardado.
2. `_update_ctx()` — mostra o bar quando `_selected[0]=="group"`.
3. `_select()` — aceita `("group",gid)` + **queue_draw** (emenda 1).
4. `_draw_groups_cr()` — outline de seleção (azul tracejado, paridade com `.selected`).
5. `_pan_begin()` — `_select(("group",gid))` nos 2 branches de grupo existentes (corner +
   title band), SEM tocar a lógica de drag/resize.
6. `_confirm_close_group(gid)` + `_close_group` limpa seleção + `_group_dialog` usa o
   caminho confirmado + `_group_swatches` extraído + guards do `_pan_update`.

## Testes (gi → python do SISTEMA; CI pula)
- `_select(("group",gid))`: não explode; `queue_draw` chamado; bar do grupo visível e as
  outras pílulas escondidas; re-selecionar nó esconde a do grupo (e redesenha de novo).
- `_close_group(gid)` com o grupo selecionado → `_selected` vira None (pílula não órfã).
- `_sel_gid()`: None p/ seleção não-grupo e p/ gid morto.
- Apagar (pílula e diálogo) passa pelo `_confirm_dialog` (não apaga direto).
- Guard do drag: gid removido no meio do gesto não ressuscita.
- **Device (obrigatório, é UI):** selecionar grupo pela faixa → pílula + outline; ⚙ abre o
  diálogo; ● troca a cor ao vivo; 🗑 pede confirmação; clique no fundo/nó limpa; drag/resize
  de grupo continuam funcionando.

## Entrega
Branch `feat/capsula-grupo` (da main v0.62.0) · 1 bump (→0.63.0) · CHANGELOG · STATUS ·
backlog `docs/15` → ✅ · este doc → ENTREGUE ao fechar.
