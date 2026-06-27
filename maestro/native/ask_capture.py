"""Captura da resposta de um terminal VIVO (modo 'live' do cabo — variante b, estilo Maestri).

Puro e testável (sem GTK/VTE): recebe o texto da tela ANTES e DEPOIS de injetar o prompt
no terminal do agente e devolve a resposta dele, removendo o eco do prompt e o "chrome"
da TUI (molduras, indicador de ocupado, linhas que já estavam na tela). A parte GTK
(`feed_child` + sinais de quiescência) fica no canvas; aqui mora só a lógica de texto, pra
poder testar a heurística sem precisar de um terminal real.
"""

from __future__ import annotations

# Tempos (ms/s) do ciclo de captura no terminal vivo.
LIVE_SUBMIT_MS = 300  # respiro entre digitar o texto e mandar o ENTER (separado) — TUIs
# tratam texto+Enter na mesma rajada como PASTE (Enter vira newline), não como envio. O Enter
# é C-m (\r) numa transmissão SEPARADA, após ~0.3s (padrão confirmado em automações tmux+claude).
LIVE_QUIET_MS = 1200  # silêncio sem novo output p/ considerar "parou de escrever"
LIVE_CAP_MS = 120_000  # teto duro: além disso desiste -> fallback headless
LIVE_WAIT_S = 130.0  # espera do worker bloqueado (> teto), antes de cair no fallback

# Marcadores de "ocupado" das TUIs (claude/codex mostram enquanto trabalham). A pesquisa
# (spike Fase 0) mostrou que estado-da-TUI ≈100% vs quiescência pura 83-93% -> combinar.
_BUSY_MARKERS = (
    "esc to interrupt",
    "esc to cancel",
    "press esc",
    "interrupt)",
    "thinking…",
    "working…",
)

# Caracteres de moldura/chrome que NÃO fazem parte da resposta do agente.
_CHROME_CHARS = set("─│┌┐└┘├┤┬┴┼╮╭╯╰═║╔╗╚╝▌▐▕▏•◐●◯> ")


def tui_busy(text: str) -> bool:
    """True se a TUI aparenta estar trabalhando (mostra indicador de interromper)."""
    t = text.lower()
    return any(m in t for m in _BUSY_MARKERS)


def _is_chrome(line: str) -> bool:
    s = line.strip()
    return not s or all(c in _CHROME_CHARS for c in s)


def clean_capture(before: str, after: str, prompt: str) -> str:
    """Resposta do agente = linhas NOVAS na tela depois da injeção, sem eco do prompt nem
    chrome da TUI nem o que já estava visível antes. Heurística best-effort (a captura de
    TUI full-screen é frágil — por isso há fallback headless no canvas)."""
    seen = {ln.strip() for ln in before.splitlines()}
    pl = prompt.strip()
    out: list[str] = []
    for ln in after.splitlines():
        s = ln.strip()
        if not s or s in seen:
            continue  # vazio ou já estava na tela antes da pergunta
        if pl and pl in s:
            continue  # linha que ECOA o prompt digitado (contém o prompt)
        if tui_busy(s) or _is_chrome(ln):
            continue  # indicador de ocupado / moldura
        out.append(s)
    return "\n".join(out).strip()
