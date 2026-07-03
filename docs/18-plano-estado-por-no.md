# Plano — Sistema de estado por nó / "precisa de você" (fechar o último quilômetro)

> Data: 2026-07-02 · PT-BR · Origem: `docs/17` (pesquisa de comunidade — **#1 no ranking dos DOIS
> modelos**). Puxado da fila pelo usuário em 2026-07-02. Segue o protocolo do `AGENTS.md`:
> **analisar → planejar → (pesquisar) → validar → codar**.
>
> ✅ **ENTREGUE — Blocos 1+2 em v0.52.0 (PR #56, 2026-07-03).** Além do plano original, o usuário
> pediu **migrar os estados pra ícones Lucide** (reusar o bundle do app) — feito: 6 ícones
> `maestro-state-*` pré-coloridos. Decisões de UX validadas: estado "aguardando" = **circle-pause
> âmbar**; **toggle de som** (OFF por padrão). **Falta o Bloco 3** (monitor padrão-ON nos
> nós-agente) — descobriu-se uma sutileza (distinguir nó-agente de shell bash pra não marcar
> "waiting" à toa) → adiado pra próxima rodada; hoje o monitor segue opt-in por nó. Detalhes de
> implementação/verificação no CHANGELOG v0.52.0 e no `docs/STATUS.md`.

## 1. Objetivo (a dor)
"Uma sessão fica esperando um comando o tempo todo sem você notar" — o pedido mais universal da
categoria (Claude Agent View, Crystal, Vibe Kanban, issue [claude-code#36885]; `docs/17` §3). Num
gestor visual, o valor é **saber quem precisa de você sem ter que caçar terminal** — ainda mais
numa tela 1280×720 com vários nós.

## 2. Descoberta-chave: ~85% JÁ EXISTE (por isso "último quilômetro")
A análise do `maestro/native/canvas.py` + `maestro/engine/attention.py` mostrou que a maior parte
da infraestrutura pedida pela comunidade **já está construída**:

| Peça | Já existe? | Onde |
|---|---|---|
| Estados de nó com **cor + FORMA + tooltip** (idle/busy/blocked/failed/done) | ✅ | `_STATE_GLYPH`, `_STATE_PT`, `set_node_state` (canvas.py) |
| Lista "precisa de você" (envelope mais recente BLOCKED/FAILED/NEEDS_INPUT) | ✅ | `attention_items` (attention.py) |
| Contador **"⚠ N"** na barra | ✅ | `_attn_label` (canvas.py ~910) |
| **Pular pro próximo nó que precisa de mim** | ✅ | `_focus_next_attention` (canvas.py 2381), ligado a atalho (4257, 6563) |
| Notificação de desktop + som ao precisar de atenção | ✅ | `notify` / `play_alert_sound` (attention.py) |
| **Monitorar atividade** por nó: quietude → estado `blocked` + notify + som | ✅ (opt-in) | `_set_node_monitor` / `_mon_quiet` (canvas.py 3430/3475) |

**Conclusão:** o experimento "precisa de você" já funciona hoje — mas com **arestas** que impedem
de entregar a experiência que a comunidade pede. O plano é fechar essas arestas, não reconstruir.

## 3. Os gaps REAIS (o que falta pra fechar a experiência)
1. **Monitorar atividade é OPT-IN por nó (toggle manual).** A dor é "não percebo que parou" — mas
   só recebe o dot/notificação quem **lembrou de ligar** o monitor naquele nó. → *tornar padrão
   (ou descoberto) para nós-AGENTE.*
2. **"Esperar meu input" ≠ "blocked/failed".** A quietude cai em `blocked` (glyph ▲), o mesmo de
   um envelope realmente bloqueado/erro. A comunidade quer distinguir a **pausa esperada** ("é sua
   vez") de um **problema**. → *estado de 1ª classe "aguardando" (glyph/cor próprios), alimentando
   o `NEEDS_INPUT` que o `attention_items` já lê mas nada no lado interativo emite.*
3. **O minimapa NÃO realça nós que precisam de atenção** (confirmado: `_draw_minimap` não pinta por
   estado). Opus/Codex pediram realce no minimapa explicitamente. → *pintar o ponto do nó em
   atenção com a cor/realce do estado.*
4. **O contador "⚠ N" não é clicável** (o jump é só atalho de teclado). → *clicar no ⚠ = pular pro
   próximo (reusa `_focus_next_attention`).*
5. **Sem rollup por GRUPO.** Os dois modelos pediram status por grupo ("em execução / aguardando /
   precisa revisão / concluído"). Hoje o estado é só por-nó. → *badge de rollup no header do grupo
   (opcional, fase 2 deste plano).*

## 4. Plano cirúrgico (incremental, testável)
**Bloco 1 — distinguir "aguardando" + realce (núcleo do valor):**
- Adicionar estado **`waiting`** a `_STATE_GLYPH`/`_STATE_PT`/`STATE_COLORS` (glyph próprio, ex.
  "◔" ou "⏳"; cor distinta de `blocked`). Acessibilidade mantida (forma+cor+tooltip — regra UI-1).
- `_mon_quiet` passa a setar `waiting` (não `blocked`) quando a quietude é "agente parou esperando"
  (heurística já existe no monitor; distinguir de erro/exit fica pro Bloco 3 se necessário).
- Incluir `waiting`/`WAITING` no conjunto acionável de `attention.py` (`ATTENTION_STATES`) para o
  nó aparecer no "⚠ N" e no `_focus_next_attention`.

**Bloco 2 — minimapa + contador clicável (barato):**
- `_draw_minimap`: pintar o ponto do nó com a cor do estado quando ele está em atenção.
- `_attn_label`: virar clicável (`GestureClick`) → `_focus_next_attention`.

**Bloco 3 — monitor padrão para nós-AGENTE (decisão de UX, ver §6):**
- Ligar `monitor` por padrão em nós-AGENTE novos (persistido em `node_cfg`, "abre igual fechou").
  Mantém o toggle no editor (§`_editor_monitor_section`).

**Bloco 4 — rollup por grupo (opcional):**
- Badge no header do grupo agregando o pior/mais-acionável estado dos membros.

## 5. Pontos no código (reuso — nada ad-hoc)
- `maestro/native/canvas.py`: `_STATE_GLYPH`/`_STATE_PT`/`STATE_COLORS` (~282), `set_node_state`
  (3079), `_mon_quiet` (3475), `_draw_minimap` (2817), `_attn_label` (910), `_focus_next_attention`
  (2381), `_editor_monitor_section` (1604).
- `maestro/engine/attention.py`: `ATTENTION_STATES`, `attention_items` (gi-free → testável).
- Persistência (Bloco 3): `node_cfg` (`monitor`), padrão de `ui_state` ("abre igual fechou").

## 6. Decisões abertas (VALIDAR com o usuário antes de codar)
1. **Glyph/cor do estado "aguardando"** — sugestão "⏳" + âmbar; ou prefere outro? (cardápio na hora)
2. **Monitor de atividade padrão-ON para nós-AGENTE?** Prós: fecha a dor de raiz (todo agente
   avisa). Contra: pode gerar dot/notify onde você não quer. Alternativa: padrão-ON mas **sem som**
   (só dot visual), som fica opt-in. — *decisão sua.*
3. **Escopo desta rodada:** Blocos 1+2 (núcleo barato) só? Ou já incluir 3 (padrão-ON) e/ou 4
   (rollup por grupo)? Recomendo **1+2 primeiro** (valor máximo, risco mínimo), 3 e 4 como
   incrementos.

## 7. Definition of done
- Testes: `attention.py` é gi-free → teste unitário do `waiting` no conjunto acionável + no
  `attention_items`; teste do `_mon_quiet` setando `waiting` (mockando só o widget, rodar a lógica
  real — regra "não mockar o método sob teste"). Runtime real no CM4 (canvas GTK): um agente
  parando vira "aguardando" (glyph próprio) + entra no "⚠ N" + realça no minimapa + Esc/atalho
  pula pra ele. `ruff` limpo. CHANGELOG + 1 bump. "Abre igual fechou" verificado (Bloco 3).
