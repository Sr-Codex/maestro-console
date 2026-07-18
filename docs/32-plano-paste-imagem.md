# Plano — Paste/drag de imagem e arquivo pro nó

> Promovido da fila (`docs/15`, item "Paste/drag de imagem pro nó", dor em 5+ concorrentes;
> escolhido pelo usuário 2026-07-18 como "faixa B" da triagem do Fable — independe do bug
> upstream #78843). **Design v2 pós-revisão adversarial (Fable 5, 9 emendas — §9,
> com MEDIÇÕES no device). Status: aguardando validação do usuário (§10).** Nada vira
> código antes.

## 1. Objetivo

Colar um **screenshot do clipboard** no terminal de um nó → o app salva a imagem como
**arquivo estável no workspace do nó** e injeta o **caminho** no prompt (o usuário revisa e
dá Enter). **Arrastar arquivo(s)** do gerenciador pro card → injeta o(s) caminho(s) — com
cópia automática quando o arquivo está num lugar que o sandbox não enxerga (`/tmp`).
Fecha a dor "quero mostrar uma imagem/arquivo pro agente sem digitar caminho na mão".

## 2. O que já existe (REUSAR) — mapeado no código 2026-07-18

- **Interceptador pronto**: o Ctrl+Shift+V global (v0.66.0) em `_on_key`
  (`canvas.py:5385-5392`) → `_focused_term().paste_clipboard()`. É AQUI que entra o desvio
  "clipboard tem imagem?".
- **Injeção canônica de texto**: `_feed_child(term, text)` (`canvas.py:4392`) — bytes no
  stdin do PTY. Precedente do modo live (`_live_ask_start:4400`): **texto e Enter SEPARADOS**
  — a feature injeta o caminho SEM `\r` (o humano revisa e envia).
- **Workspace do nó**: `_node_ws(nid)` (`canvas.py:3775`) → `<home>/workspaces/<nid>/`;
  precedente de subdir: `notes/` (`canvas.py:4135`). Validação de nome de arquivo à la
  `artifacts.py:15` (`_SAFE_NAME`).
- **Sandbox**: workspace é **bind RW + cwd** do agente (`sandbox.py:51-66`) — arquivo salvo
  pelo app (fora do sandbox) aparece pro CLI por dentro, no MESMO caminho absoluto.
  **Armadilha mapeada**: `--tmpfs /tmp` → o `/tmp` do HOST é invisível pro nó; arquivo
  arrastado de lá precisa de CÓPIA pro workspace.
- **DnD: zero hoje** — nenhum `Gtk.DropTarget`/`DragSource` no app (o arrasto de nós é
  gesto de pan do plano, `_pan_begin:2859`, tags `_drag_nid` — outra coisa). O DropTarget
  de arquivo será o primeiro; anexar ao `term`/`frame` em `_add_node` (`canvas.py:~2394`,
  junto dos controllers existentes).
- **Clipboard**: só ESCRITA de texto hoje (`self.win.get_clipboard().set(path)`,
  `canvas.py:6376`). Leitura de imagem é código novo.

## 3. Pesquisa ao vivo (2026-07-18)

**Lado CLI (por que caminho-de-arquivo, não paste nativo):** no Linux, colar IMAGEM direto
no claude/CLI é não-confiável por design — Ctrl+V de imagem só é sólido no macOS; WSL
precisou de keybinding dedicado (v2.1.157); a recomendação cross-platform é **referenciar o
arquivo por caminho no prompt**, e drag&drop de arquivo funciona "dependendo do terminal"
(quem embute VTE precisa implementar). Formatos aceitos: JPEG/PNG/GIF/WebP, ~5 MB por
imagem. Fontes (2026-07-18): guia cross-platform harishgarg.com; felloai.com/claude-code-images;
blog.shukebeta.com (fix Linux via arquivo); issue anthropics/claude-code#58133; smartscope.blog.

**Lado GTK4:** `Gdk.Clipboard.read_texture_async()` lê a imagem do clipboard;
`clipboard.get_formats()` detecta ANTES se há imagem (decide o desvio sem consumir o
clipboard); `Gdk.Texture.save_to_png()` grava. Drop de arquivo: `Gtk.DropTarget` com
`Gdk.FileList`. Fontes (2026-07-18): tutorial oficial PyGObject GTK4 (clipboard);
docs.gtk.org/gdk4 (Clipboard/Texture); docs GTK4 DropTarget.

## 4. Design

### 4.1 Paste (Ctrl+Shift+V fica "esperto")
- No branch do Ctrl+Shift+V: detectar imagem por **`contain_gtype(Gdk.Texture) OR
  contain_mime_type(image/*)`** (E5 — medido no device: caminho feliz tem os dois; TARGETS
  do X11 é assíncrono → formats VAZIO cai no paste de texto, nunca perder o gesto).
  **Tem imagem** → `read_texture_async` → **cap anti-bomba (E4): recusar textura
  > 8192px de lado** (clipboard é escrevível por qualquer processo X11 — inclusive o
  agente; PNG craftado de 10000² alocaria ~400MB e derrubaria o app no CM4; hint de 1
  linha via `term.feed`, nunca `feed_child`) → salvar em
  `<ws>/pastes/paste-YYYYmmdd-HHMMSS-<únicо>.png` (sufixo de unicidade — E6: timestamp puro
  colide no mesmo segundo) → `_feed_child(term, caminho_quoted + " ")` **sem `\r`**.
  **Imagem+texto juntos** (Firefox "copiar imagem" põe a URL como texto): **imagem vence**
  (D7, documentado). **Só texto/indetectável** → `paste_clipboard()` como hoje.
- `pastes/` criado on-demand; **nunca apagado pelo app** ("estável" é o requisito — a dor
  da Clave era caminho temp deletado). Limpeza é do usuário.
- **Nó descarregado → no-op ANTES de salvar/copiar (E2)**: o guard atual
  (`_focused_term`) NÃO cobre — nó descarregado tem term VIVO sem filho (`_dead_terminal`);
  sem o check `_node_unloaded(nid)` explícito nas DUAS rotas, o paste salvaria PNG órfão e
  o drop copiaria arquivo pra ninguém.

### 4.2 Drop de arquivo(s) no card
- `Gtk.DropTarget(Gdk.FileList)` anexado ao card em `_add_node`. **Medido no device
  (E9, 2026-07-18, vte 0.84.0-2 gtk4/X11): o Vte.Terminal NÃO tem DropTarget embutido**
  (controllers nativos: gestos/scroll/focus/key) → sem conflito, fase padrão serve; o
  GestureClick CAPTURE do reload não dispara em DnD. Drop de N arquivos → injeta os
  caminhos (quoted, separados por espaço), SEM `\r`.
- **Nome hostil (E1 — BLOQUEANTE, modelo ADR-17)**: `shlex.quote` preserva `\r`/`\n`/ESC
  LITERAIS dentro das aspas e o `feed_child` injeta bytes crus → arquivo criado pelo
  AGENTE com `\r`+comando no nome viraria auto-submit quando o dono o arrastasse. Regra:
  caminho com QUALQUER byte < 0x20 (ou não-imprimível) NUNCA é injetado — o arquivo é
  COPIADO pra `pastes/` com nome seguro GERADO (padrão `_SAFE_NAME` do artifacts.py) e a
  cópia é injetada. Teste gi-free obrigatório com `\r`, `\n` e ESC no nome.
- **Regra do /tmp (sandbox)**: caminho sob `/tmp` (ou qualquer prefixo invisível no nó) →
  **copia** pro `<ws>/pastes/` e injeta o caminho da cópia; resto → injeta o caminho
  ORIGINAL (sem cópia — arquivo grande não é duplicado à toa; `--ro-bind /` já o torna
  legível por dentro).
- Convive com o pan: DropTarget só reage a DnD externo; o arrasto de nós é gesto do
  plano (já MEDIDO — E9; resta o drop real desde o Thunar no DoD).
- Nó shell/comando custom rodam SEM sandbox e enxergam o /tmp real — a cópia é inofensiva
  e mantém a regra UNA (E7: decisão documentada, não condicionar por tipo de nó).

### 4.3 Caminho injetado: ABSOLUTO
- Sempre absoluto (quoted): o cwd pode variar (shell pós-`/exit`, `node_cfg cwd` custom,
  nó-shell) e o sandbox espelha o mesmo caminho por dentro. Relativo economizaria chars mas
  quebraria nesses casos.

### 4.4 Lógica pura separada (testável gi-free)
- Novo `maestro/native/paste.py` (gi-free): `paste_filename(now)` (timestamp + sufixo de
  unicidade — E6: duas chamadas com o MESMO now não colidem; cópia de drop idem, sem
  sobrescrever homônimo), `needs_copy(path)` e `quote_paths(paths)` (com a regra E1 de
  control chars). **E3: os prefixos invisíveis NÃO são lista fixa** — derivados de uma
  função única ao lado do sandbox (`invisible_prefixes()`): `/tmp`, `accounts_root()`
  (máscara tmpfs da v0.66.0!), `/dev`, `/proc`, `/run/user/<uid>` — mudança futura de
  mounts atualiza o `needs_copy` de graça. O canvas só orquestra (clipboard/texture/feed
  são fronteira gi).

## 5. Riscos e invariantes

1. **Sem `\r` SEMPRE** — o humano envia; injetar Enter automático viraria execução não
   revisada (mesmo princípio do live-ask em 2 tempos).
2. **Clipboard pode mudar entre o check e a leitura** (async) — se `read_texture` falhar,
   cair no `paste_clipboard()` de texto (degradação suave, nunca perder o gesto).
3. **Imagem grande**: PNG de screenshot no CM4 é pequeno (~centenas de KB); sem limite
   próprio (o cap de 5 MB é do CLI; impor outro seria YAGNI). `save_to_png` roda no main
   loop — screenshot típico ok; se travar no device, mover pra thread (decidir no teste).
4. **Nome de arquivo**: rota de imagem usa nome GERADO (sem injeção por construção); rota
   de drop aplica a regra E1 (control char no nome → cópia com nome seguro; `shlex.quote`
   só cobre espaço/aspas — NÃO control chars).
5. **Nó-shell**: workspace pode não existir → `mkdir` on-demand resolve; caminho absoluto
   funciona igual (sem sandbox no shell puro).
6. **Falha de salvar/copiar nunca é silenciosa (E8)**: try/except → hint de 1 linha na
   TELA via `term.feed` (padrão `UNLOADED_HINT`) — jamais `feed_child` (não tocar o stdin
   do agente com mensagem de erro).
7. **Limite pré-existente do X11 (registrado, não regressão)**: qualquer processo X pode
   escrever no clipboard (inclusive o agente sandboxado, via socket do X) — afeta o paste
   de TEXTO atual igualmente; o cap E4 e o "sem \r" mitigam o pior caso.

## 6. Pontos no código

| Necessidade | Local |
|---|---|
| Desvio do paste | `canvas.py:5385-5392` (branch Ctrl+Shift+V) |
| Ler formatos/imagem | novo, via `self.win.get_clipboard()` (padrão `canvas.py:6376`) |
| Salvar PNG | novo `_save_paste_image(nid, texture)` → `_node_ws(nid)/pastes/` |
| Injetar caminho | `_feed_child` (`canvas.py:4392`), sem `\r` |
| DropTarget | `_add_node` (`canvas.py:~2394`, junto dos controllers do term) |
| Lógica pura | novo `maestro/native/paste.py` (gi-free) |
| Testes | `test_paste.py` (gi-free) + `test_paste_ui.py` (gi) |

## 7. O que NÃO muda

- Paste de TEXTO: comportamento atual intacto (o desvio só ativa com imagem no clipboard).
- Nenhuma UI nova (sem botão/cápsula — é interação pura; regras de cápsula não se aplicam).
- Nenhum estado/config novo → nada a persistir (regra "abre igual fechou" não é acionada).
- Sandbox/política de mounts intactos.

## 8. Definition of done (rascunho)

- gi-free (`test_paste.py`): `paste_filename` (formato + unicidade com o MESMO now — E6),
  `needs_copy` (/tmp e accounts_root sim; home não — E3), `quote_paths` (espaço/aspas) e a
  regra E1 (nome com `\r`/`\n`/ESC → cópia com nome seguro, NUNCA injeção do original).
- gi (`test_paste_ui.py`): clipboard com imagem → salva + `_feed_child` quoted SEM `\r`;
  só texto/formats vazio/`read_texture` FALHA → `paste_clipboard()` (fallback §5.2 — E5);
  imagem+texto → imagem vence (D7); textura > cap → recusa com hint (E4); drop → path
  quoted; drop de /tmp e de nome hostil → cópia (E1/E3); nó descarregado → no-op ANTES de
  salvar (E2).
- **Prova no device**: screenshot real (Print → xfce4-screenshooter, que TEM opção
  clipboard) → Ctrl+Shift+V no nó → caminho no prompt → Enter → claude LÊ a imagem —
  inclusive DEPOIS de fechar o app do screenshot (X11 perde clipboard com o dono; testar o
  fluxo real); arrastar arquivo do Thunar → caminho no prompt; arrastar de /tmp → cópia;
  caso Firefox imagem+URL; pan/drag de nó segue normal.
- CHANGELOG + bump (1 por PR) + entrada docs/15 → ✅.

## 9. Revisão adversarial (Fable 5, 2026-07-18) — v1 → v2

**Veredito: APROVADO COM EMENDAS (9), com MEDIÇÕES no device** (X11/Xorg confirmado; VTE
0.84.0-2 gtk4 SEM DropTarget embutido → sem conflito; probe GDK4 com PNG real via xclip:
formats/read_texture/save_to_png ok; Print ligado ao xfce4-screenshooter com opção
clipboard). **E1 (CRÍTICA, bloqueante)**: `shlex.quote` preserva control chars → nome de
arquivo hostil (criado pelo agente, arrastado pelo dono) viraria auto-submit via `\r` no
`feed_child` — quebrava o invariante D4 no exato modelo ADR-17 → caminho com byte < 0x20
nunca é injetado (cópia com nome seguro). **E2**: o "guard do descarregado" prometido não
existia (`_dead_terminal` tem term vivo sem filho) → check `_node_unloaded` explícito
antes de salvar/copiar. **E3**: `needs_copy` fixo em `/tmp` já nascia dessincronizado — a
máscara tmpfs de `~/.maestro-accounts` (v0.66.0), `/dev`, `/proc`, `/run/user/<uid>`
também são invisíveis → prefixos DERIVADOS de função única. **E4**: imagem-bomba no
clipboard (escrevível por qualquer processo X, inclusive o agente) → cap de dimensão
antes do save (CM4/earlyoom). **E5**: detecção por gtype ∪ mime; formats vazio (TARGETS
assíncrono do X11) e falha do read → fallback pro paste de texto; imagem+texto → D7.
**E6**: timestamp puro colide no mesmo segundo → sufixo de unicidade. **E7**: nó
shell/custom (sem sandbox) enxerga /tmp — cópia mantida por regra una (documentado).
**E8**: falha de salvar → hint via `term.feed`, nunca stdin. **E9**: medições registradas
pra não re-investigar. Acertos sem emenda: interceptador/feed sem `\r`, caminho absoluto,
`pastes/` estável, nome gerado, conta/1-PR.

## 10. DECISÕES — pendentes de validação do usuário

| # | Decisão | Recomendação |
|---|---|---|
| D1 | Caminho injetado: absoluto vs relativo | **absoluto** (cwd varia; sandbox espelha o path) |
| D2 | Destino: `<ws>/pastes/` | **sim** (padrão `notes/`; estável, nunca apagado pelo app) |
| D3 | Drop de arquivo em `/tmp` → copiar pro workspace | **sim** (invisível no sandbox); demais SEM cópia |
| D4 | Nunca injetar `\r` (usuário revisa e envia) | **sim** (princípio do live-ask) |
| D5 | Salvar sempre PNG | **sim** (aceito pelo CLI; `save_to_png` nativo) |
| D6 | Escopo: paste + drop no MESMO PR | **sim** (1 unidade coerente) |
| D7 | Clipboard com imagem E texto (caso Firefox): imagem vence | **sim** (E5, documentado; texto continua acessível colando de novo após limpar a imagem) |
