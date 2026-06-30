"""Temas de terminal (paletas VTE) — gi-free e testável.

Cada tema = foreground, background, 16 cores ANSI (hex) e flag `dark`. Aplicado aos
VTE via set_colors; a escolha persiste em ui_state (global) e por terminal (node_cfg).
Base hardcoded (4) + ~66 esquemas bundlados (iTerm2-Color-Schemes, formato ghostty, MIT,
em term_themes/schemes.json) + temas do USUÁRIO (arquivos ghostty em USER_THEMES_DIR).
"""

from __future__ import annotations

import json
from pathlib import Path

THEMES: dict[str, dict] = {
    "default": {
        "dark": True,
        "fg": "#d0d0d0",
        "bg": "#1e1e1e",
        "palette": [
            "#000000",
            "#cd0000",
            "#00cd00",
            "#cdcd00",
            "#0000ee",
            "#cd00cd",
            "#00cdcd",
            "#e5e5e5",
            "#7f7f7f",
            "#ff0000",
            "#00ff00",
            "#ffff00",
            "#5c5cff",
            "#ff00ff",
            "#00ffff",
            "#ffffff",
        ],
    },
    "dracula": {
        "dark": True,
        "fg": "#f8f8f2",
        "bg": "#282a36",
        "palette": [
            "#21222c",
            "#ff5555",
            "#50fa7b",
            "#f1fa8c",
            "#bd93f9",
            "#ff79c6",
            "#8be9fd",
            "#f8f8f2",
            "#6272a4",
            "#ff6e6e",
            "#69ff94",
            "#ffffa5",
            "#d6acff",
            "#ff92df",
            "#a4ffff",
            "#ffffff",
        ],
    },
    "catppuccin": {
        "dark": True,
        "fg": "#cdd6f4",
        "bg": "#1e1e2e",
        "palette": [
            "#45475a",
            "#f38ba8",
            "#a6e3a1",
            "#f9e2af",
            "#89b4fa",
            "#f5c2e7",
            "#94e2d5",
            "#bac2de",
            "#585b70",
            "#f38ba8",
            "#a6e3a1",
            "#f9e2af",
            "#89b4fa",
            "#f5c2e7",
            "#94e2d5",
            "#a6adc8",
        ],
    },
    "gruvbox": {
        "dark": True,
        "fg": "#ebdbb2",
        "bg": "#282828",
        "palette": [
            "#282828",
            "#cc241d",
            "#98971a",
            "#d79921",
            "#458588",
            "#b16286",
            "#689d6a",
            "#a89984",
            "#928374",
            "#fb4934",
            "#b8bb26",
            "#fabd2f",
            "#83a598",
            "#d3869b",
            "#8ec07c",
            "#ebdbb2",
        ],
    },
}

DEFAULT_THEME = "default"
DEFAULT_DARK = "catppuccin"  # tema escuro do modo "Sistema/Escuro"
DEFAULT_LIGHT = "iTerm2 Solarized Light"  # tema claro do modo "Sistema/Claro" (vem do bundle)

_BUNDLED = Path(__file__).resolve().parent / "term_themes" / "schemes.json"
# temas do usuário: arquivos no formato ghostty soltos aqui (igual ao ~/.maestri/terminal/themes)
USER_THEMES_DIR = Path.home() / ".config" / "maestro-console" / "terminal-themes"


def _norm(v: str) -> str:
    v = v.strip()
    return v if v.startswith("#") else "#" + v


def _lum(hexc: str) -> float:
    h = hexc.lstrip("#")
    return (0.299 * int(h[0:2], 16) + 0.587 * int(h[2:4], 16) + 0.114 * int(h[4:6], 16)) / 255


def parse_ghostty(text: str) -> dict | None:
    """Parser do formato ghostty → {fg, bg, palette[16], dark}. None se incompleto.
    Linhas: `palette = N=#hex`, `background = #hex`, `foreground = #hex`."""
    fg = bg = None
    pal: list[str | None] = [None] * 16
    for line in text.splitlines():
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k == "palette":
            idx, _, hexv = v.partition("=")
            try:
                i = int(idx.strip(), 0)
            except ValueError:
                continue
            if 0 <= i < 16:
                pal[i] = _norm(hexv)
        elif k == "background":
            bg = _norm(v)
        elif k == "foreground":
            fg = _norm(v)
    if fg and bg and all(pal):
        return {"dark": _lum(bg) < 0.5, "fg": fg, "bg": bg, "palette": pal}
    return None


def _load_bundled() -> None:
    try:
        data = json.loads(_BUNDLED.read_text(encoding="utf-8"))
    except OSError:
        return
    for name, scheme in data.items():
        THEMES.setdefault(name, scheme)  # não sobrescreve os 4 base


def _load_user() -> None:
    """Importa temas do usuário (arquivos ghostty em USER_THEMES_DIR). Sobrepõem bundlados."""
    try:
        entries = sorted(USER_THEMES_DIR.iterdir()) if USER_THEMES_DIR.is_dir() else []
    except OSError:
        return
    for f in entries:
        try:
            if f.is_file():
                t = parse_ghostty(f.read_text(encoding="utf-8", errors="ignore"))
                if t:
                    THEMES[f.stem] = t
        except OSError:
            continue


_load_bundled()
_load_user()


def theme_names() -> list[str]:
    return list(THEMES)


def get_theme(name: str) -> dict:
    """Tema por nome; fallback p/ default se desconhecido."""
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def theme_is_dark(name: str) -> bool:
    t = THEMES.get(name)
    return bool(t.get("dark", True)) if t else True
