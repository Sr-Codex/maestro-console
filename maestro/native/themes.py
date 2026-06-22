"""Temas de terminal (paletas VTE) — V11-S4, gi-free e testável.

Cada tema = foreground, background e 16 cores ANSI (hex). Aplicado aos VTE via
set_colors; a escolha persiste em ui_state. `default` é o fallback.
"""

from __future__ import annotations

THEMES: dict[str, dict] = {
    "default": {
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


def theme_names() -> list[str]:
    return list(THEMES)


def get_theme(name: str) -> dict:
    """Tema por nome; fallback p/ default se desconhecido."""
    return THEMES.get(name, THEMES[DEFAULT_THEME])
