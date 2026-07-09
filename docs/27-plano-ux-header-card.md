# Plano — UX do header do card do nó (Fase B da rodada de UI)

> Continuação da rodada de UI do canvas (auditoria Fable). **Fase A** (tofu, ✕ destrutivo, FAB,
> enquadrar) mergeada na `main` (v0.59.0, PR #70). Esta é a **Fase B — legibilidade do header**.
> Design validado por mockup HTML iterado com o usuário + **revisão adversarial do Fable**.
> Branch: `feat/ux-canvas-header` (a partir da `main`).

## Problema (auditoria Fable, screenshots do device)
O header do card hoje é uma linha só de widgets GTK todos no mesmo peso/cor:
`nº · dot · [badge de papel] · nome · status · custo · RAM · ✕`, com:
1. **Contraste < WCAG AA:** status/custo/RAM em cinza `#9399b2` 10px sobre `#313244` (~4.2:1).
2. **Hierarquia zero:** identidade, estado e telemetria competem no mesmo tom.
3. **`waiting` ≡ `blocked`:** mesma cor âmbar `#f59e0b` (só a forma do ícone difere).

## Design final (decidido com o usuário)
Header em **UMA LINHA** (o usuário rejeitou 2 linhas), com 3 zonas:
```
[nº] [●dot] [ nome-do-terminal … ] [ agente ]        [$custo] [tok] [mem]  [✕]
 └── identidade (esquerda) ──────────────┘  └─ telemetria (direita, junto à borda) ─┘
```
- **nome-do-terminal:** o `node_name` (título renomeável). Ganha `ellipsize=END` — nome longo
  trunca com `…` e não esmaga o resto (armadilha Fable).
- **agente:** o **nome do papel/role** (`_node_role(nid).name`) numa **cápsula de COR FIXA**
  (`#45475a`, não muda por papel nem por estado — pedido do usuário). **Escondida quando o nó
  não tem role** (nós shell) — a role é opcional. Atualiza quando o role muda.
- **estado:** fica **só no dot colorido** (ícone Lucide pré-colorido) + tooltip. O usuário optou
  por não exibir o texto de status ("é sua vez"/"bloqueado") nesta versão de 1 linha. O label
  `head._status` é preservado (setado por `set_node_state`) mas fica **fora do header** (compat).
- **telemetria (chips com fundo escuro, boa visibilidade — `.node-metric`):** custo `$` **e**
  tokens viram **chips separados** (no mockup aprovado, nós Claude mostram os dois; Codex sem
  preço mostra só tokens). Cada chip **some quando vazio** (`set_visible(False)` — evita o
  "losango fantasma" que o Fable apontou). RAM anômala continua vermelha (`.node-ram-high`).

### Emendas do Fable incorporadas
- `set_ellipsize(END)` no título (nome longo × largura de 420px).
- Chip vazio → `set_visible(False)` (custo zero / RAM não medida).
- `remove_css_class` ao trocar classe de estado (não deixar preso na cor velha) — vale p/ o
  `.node-ram-high` (já feito no `_set_ram_label`).
- Auditar aparência nos **8 estados** (idle/busy/waiting/blocked/failed/done/unloaded/órfão) —
  aqui simplificado: o dot já cobre todos via `set_node_state`; a cápsula do agente é ortogonal
  ao estado (cor fixa), então não multiplica casos.
- **Armadilha `insert_child_after(w, head._dot)` (`canvas.py:3329`): NÃO se aplica** — o header
  segue **Box horizontal** (1 linha), então `head._dot` continua filho direto do head.
- Re-rodar os testes `gi` no **python do sistema** (o CI os pula — venv sem `gi`).

## Cor do `blocked` = **PR SEPARADO** (decisão do usuário + Fable)
Dar cor própria ao `blocked` (proposta Fable: **Mocha red `#f38ba8` com texto escuro**, 7.1:1,
sobrevive a daltonismo — em vez de `#e64553`, que falha AA e colide com `failed #ef4444`) **NÃO
entra nesta fatia**. Motivo decisivo achado pelo Fable: a Web UI **não tem estado `waiting`**
(`canvas.js:10` mapeia `NEEDS_INPUT → blocked` âmbar) — um sync mecânico do vermelho inverteria a
semântica na web. É um **alinhamento semântico** (agents.py `STATE_COLORS` + canvas.js `COLORS` +
style.css + recolorir `maestro-state-blocked.svg` + minimapa `_mm_items`), unidade coerente
própria. **Ordem:** este PR (layout) cria o LUGAR; a cor vem depois, em PR 2.

## Fatiamento
- **PR 1 (este):** layout do header em 1 linha — cápsula do agente (cor fixa), chips de
  custo/token/mem, ellipsize, esconder chip vazio. Valida-se visualmente com a paleta atual.
- **PR 2 (depois):** cor própria do `blocked` (`#f38ba8`) nas 3 paletas + SVG + minimapa + Web UI.

## Verificação
- `pytest` (python do SISTEMA p/ os testes `gi` de canvas) + `ruff` limpos.
- App sobe; header renderiza em 1 linha; nome longo trunca; cápsula do agente aparece só com role;
  chips somem quando vazios. **Teste sensorial no device (usuário)** — é mudança visual.
- CHANGELOG + bump de versão (0.59.0 → 0.60.0).
