# Plano — UX dos diálogos/cards do canvas nativo

> Data: 2026-07-05 · PT-BR · Origem: usuário reclamou que o card **"Limites"** (💰, gasto/RAM)
> abre "quase tela cheia"; pediu melhorar a UX de **todos** os diálogos/cards abertos. Protocolo
> `AGENTS.md`: analisar → planejar → **pesquisar (revisão adversarial do Fable)** → validar → codar.
> Estado: **NÍVEL 1 ENTREGUE (v0.58.0)** · **NÍVEL 2 ENTREGUE (v0.62.0, itens 4+5+6)** —
> branch `feat/ux-dialogos-completo`, validado por teste visual no device. Plano CONCLUÍDO.
> (Revisado pelo Fable 2026-07-05; validado contra a `main` v0.57.2.)

## 1. Objetivo (a dor)
- Alvo: **handheld uConsole CM4, 1280×720**, toque + trackball; strings PT-BR longas (incham labels).
- Sintoma relatado: o card "Limites" abria quase em tela cheia. **Causa-raiz é geral, não daquele
  card:** um `Gtk.Label(wrap=True)` **sem `max_width_chars`** reporta a largura natural do texto
  inteiro numa linha → a `Gtk.Window` cresce pra caber. No GTK4 **não existe** `set_max_size`/
  geometry-hint na janela, então `set_default_size` é só tamanho inicial — a cura real é
  `max_width_chars` no label.
- O card Limites **já foi tapado inline** (v0.56.0: `set_default_size(380,-1)` + `max_width_chars=44`).
  O que **continua latente** são os outros diálogos com o mesmo padrão.

## 2. O que existe hoje (lido no código — `maestro/native/canvas.py`, main v0.57.2)
- **21 diálogos**: **20 usam o helper compartilhado `_dialog(title)`** (`canvas.py:5167`) — cria
  `Gtk.Window` modal, `transient_for(self.win)`, `set_default_size(420,-1)`, box vertical
  (margens 8px, spacing 6px), **Esc fecha**; retorna `(win, box)`. **1 outlier: `_budget_dialog`
  ("Limites", `canvas.py:4242`)** monta a própria `Gtk.Window` (sem Esc/transient; margens 14px).
- **Bug latente confirmado (15 labels):** `grep "wrap=True|set_wrap(True)"` sem `max_width_chars`
  bate em ~15 pontos; os mais expostos são as **mensagens dos `_confirm_*`** (descarregar 3630,
  parar-tudo 4373, equipe 4480/4569) e os avisos "out" de floors/routines. (Editar Terminal já
  embrulha o corpo num `ScrolledWindow`, então rola por dentro.)
- **Já EXISTE scroll em alguns:** Editar Terminal (`ScrolledWindow` NEVER/AUTOMATIC + `max_content_height`),
  a **paleta Ctrl-P** (lista + scroller). → **scroll NÃO pode virar default no helper** (senão vira
  barra-dentro-de-barra / scroll aninhado).
- **Sem helper de rodapé:** ~30 botões (`Cancelar`/`Salvar`/`OK`/`Fechar` + `suggested-action`/
  `destructive-action`) espalhados; cada diálogo remonta a barra, ordem/estilo ad-hoc.
- **`Enter → primário`** hoje é `connect("activate")` espalhado (rename, name-entry, paleta) — não há
  padrão único.
- **Sem razão técnica** pro `_budget_dialog` ser custom (é só box + rows + footer) — migrar é seguro.
- **Teste:** existe `tests/canvas_harness.py` (`win()`/`term()`/`patch_agents()`) — monta
  `CanvasWindow` sem `__init__`; os testes de canvas são gi-gated (rodam no python do sistema, o CI
  gi-free os PULA).

## 3. Veredito da revisão adversarial (Fable, 2026-07-05)
Correções que o Fable fez no rascunho inicial (verificadas no código):
1. **Contagem:** são **21 diálogos (20 via helper + 1 outlier)**, não "19/20".
2. **Alvo já-morto:** o card Limites que o usuário viu **já está corrigido**; os latentes VIVOS são
   os `_confirm_*` e os avisos de floors/routines.
3. **DERRUBADO "clamp de janela ao viewport":** não existe API no GTK4 — a cura é `max_width_chars`.
4. **DERRUBADO "scroll automático no `_dialog`":** Editar Terminal e paleta já rolam → double-scroll.
   Scroll deve ser **opt-in por diálogo**, não default no helper.
5. **REBAIXADO `_form_row`/`SizeGroup` (YAGNI):** metade das "linhas" reais é multi-widget
   (routines/floors são HBox com combo+prompt+intervalo+botão) → ganho cosmético, risco de quebrar
   layout. Fora da v1.
6. **Dois padrões, não um:** os `_confirm_*` são quase idênticos (título + mensagem + [cancelar,
   primário]) → pedem um helper de **alto nível `_confirm_dialog`** (colapsa 5 cópias E mata o bug).
   Os form-heavy precisam de rodapé + scroll opt-in, **não** de mensagem-hint.
7. **`Enter → primário` pela API canônica:** `win.set_default_widget(primary)` +
   `entry.set_activates_default(True)`, **não** um controller manual de tecla (colidiria com os
   `connect("activate")` e o Esc-controller já existentes).

## 4. Plano cirúrgico (blocos → stories, ranqueado)

### Nível 1 — quick-win (alto valor, baixo risco) — ✅ **ENTREGUE (v0.58.0, branch `feat/ux-dialogos`)**
Fases: 1 helpers (`_hint_label`+`_confirm_dialog`) · 2 migrar `_confirm_unload`/`_confirm_kill_all` ·
3 matar o bug nos demais labels (async + outputs) · 4 guarda de regressão no fonte (CI) · 5 fechamento.
Falta só o **teste vivo visual no device** (largura ≤ ~600px, Esc, Enter→primário) — confirmação do usuário.
1. **`_hint_label(text, chars=44)`** — fábrica de label de mensagem que já nasce
   `wrap=True + max_width_chars`. Aplicar nos `_confirm_*` e nos avisos "out" de floors/routines.
   **Mata o bug fullscreen onde ele ainda vive.** Menor superfície, maior retorno.
2. **`_confirm_dialog(title, msg, *, primary, on_primary, destructive=False, extra=None, cancel=True)`**
   — helper de alto nível que colapsa os ~5 `_confirm_*` quase-idênticos e já embute (1). Trata o
   caso "só OK, sem cancelar" (`cancel=False` — ver `_confirm_kill_all` branch `n==0`).
3. **Guarda de regressão no FONTE** (roda no `.venv` → **coberta pelo CI**, ao contrário dos gi):
   teste AST/grep garantindo que nenhum `Gtk.Label(wrap=True)` de corpo de diálogo fica sem
   `max_width_chars` (ou passa pelo `_hint_label`). Trava o bug pra sempre sem precisar de display.

### Nível 2 — polimento — ✅ **ENTREGUE (v0.62.0, branch `feat/ux-dialogos-completo`)**
Itens 4+5+6 abaixo entregues; `_hitl_*` e a barra por-linha da lista de templates ficaram FORA
(não são rodapés `[Cancelar,Salvar]` — ver CHANGELOG v0.62.0). Validado por teste visual no device.
4. **Migrar `_budget_dialog` (Limites) pro helper** — remove o outlier; ganha Esc/transient/
   consistência. (O fullscreen já está resolvido; isto é higiene.)
5. **`_dialog_footer(win, box, *, primary, on_primary, destructive=False, extra=None, cancel=True)`**
   + `set_default_widget`/`set_activates_default` — padroniza a barra de botões nos form-heavy
   (editar terminal, novo terminal, routines, team, floors, workspaces). Callback controla o
   `destroy` (diálogos que reabrem a si mesmos — workspaces/team — não podem ter o footer fechando
   sozinho antes do `on_primary`).
6. **Scroll opt-in** `_dialog(..., scroll=True, max_h=…)` — só onde faltar altura (routines/team
   edit se estourarem 720px). **Nunca** por cima de quem já rola (Editar Terminal/paleta).

### Cortado (YAGNI / sem base técnica)
- **`_form_row` + `SizeGroup`** — cosmético, risco de quebrar HBox multi-widget.
- **"clamp de janela ao viewport"** — não existe no GTK4.
- **"scroll automático no `_dialog`"** — causa double-scroll.
- **Paleta Ctrl-P** fica **fora** da migração de rodapé/scroll: é busca (Enter = executar seleção,
  não "salvar"), já tem entry+listbox+scroller próprios.

## 5. Estratégia de teste (o "instanciar-sem-crashar" NÃO basta)
- **Por que não basta** (Fable): construir widget exige GTK/display → só roda no device (CI gi-free
  PULA); `CanvasWindow.__new__` mocka meia classe; e **sem render não há largura medida → não pega o
  bug**. "Instanciar sem crashar" prova só "não tem AttributeError".
- **O que dá confiança:**
  1. **Unit dos helpers puros** (via `canvas_harness`): `_hint_label("…")` retorna `Gtk.Label` com
     `get_wrap() is True` e `get_max_width_chars() > 0`; `_confirm_dialog`/`_dialog_footer` montam um
     box cujos filhos são os botões esperados, na ordem certa, com as CSS classes certas.
  2. **Guarda de regressão no fonte** (Nível 1 item 3) — o único que **pega o bug de largura** e roda
     no CI.
  3. **Teste vivo no device (obrigatório — é UI):** abrir os 21, nenhum passa de ~600px de largura
     nem estoura 720 de altura; Esc fecha; Enter aciona o primário; rodapé alcançável. Sem isto não
     está "feito" (regra do projeto + "prova, não afirmação").
- **Não** prometer "os testes instanciam os 21 sem crashar = coberto" — é meia-verdade.

## 6. Escopo / entrega
- **Tema próprio ≠ unload/reattach** → branch `feat/ux-dialogos` a partir da `main` (v0.57.2).
  **Fatiar em commits** (Nível 1 primeiro; migração/adoção depois) pra o teste vivo isolar regressão.
- **1 bump de versão por PR**; CHANGELOG; `docs/STATUS.md`; atualizar este doc pra ENTREGUE ao fechar.

## 7. Furos/edge-cases a lembrar na hora de codar (Fable)
- Largura **mínima** também importa em PT-BR: a barra de botões dita o piso (não forçar
  `width_request` pequeno). 44 chars é ponto de partida — validar em px na fonte real do device.
- `_confirm_kill_all` tem branch `n==0` (só "OK", sem hint) → `_confirm_dialog(cancel=False)`.
- Diálogos que **fecham e reabrem a si mesmos** (workspaces, team) → o footer deixa o callback
  controlar o `destroy`.
- Tab-order sai de graça pela ordem de `append` (rodapé por último — já é o padrão).
