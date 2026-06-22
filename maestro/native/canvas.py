"""Canvas nativo GTK3 + VTE (V6-S1 spike).

Janela com área rolável (Gtk.Layout = base do canvas infinito) contendo nós com
terminais reais (Vte.Terminal). Aqui (spike) abre um shell; V6-S3 abre agentes
em bwrap. Headless/engine não muda — VTE é a camada visual/interativa.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import GLib, Gtk, Vte  # noqa: E402


def make_terminal(argv: list[str]) -> Vte.Terminal:
    """Cria um Vte.Terminal real rodando ``argv`` num PTY."""
    term = Vte.Terminal()
    term.set_size(80, 24)
    term.spawn_async(
        Vte.PtyFlags.DEFAULT,
        None,  # cwd
        argv,
        None,  # env
        GLib.SpawnFlags.DEFAULT,
        None,
        None,  # child setup
        -1,  # timeout
        None,  # cancellable
        None,
        None,  # callback
    )
    return term


def make_node(title: str, argv: list[str]) -> Gtk.Widget:
    """Um 'nó' do canvas: moldura com título + terminal real."""
    frame = Gtk.Frame(label=title)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.pack_start(make_terminal(argv), True, True, 0)
    frame.add(box)
    frame.set_size_request(420, 220)
    return frame


def build_window() -> Gtk.Window:
    win = Gtk.Window(title="maestro console 🎼 — canvas (nativo)")
    win.set_default_size(1000, 600)
    layout = Gtk.Layout()  # base pannável do canvas (V6-S2 add pan/zoom)
    layout.set_size(4000, 3000)  # área grande ("infinita")
    scrolled = Gtk.ScrolledWindow()
    scrolled.add(layout)
    win.add(scrolled)
    # spike: um nó com shell para provar VTE real na tela do uConsole
    layout.put(make_node("shell", ["/bin/bash"]), 60, 60)
    win.connect("destroy", Gtk.main_quit)
    return win


def run() -> None:  # pragma: no cover - loop GTK interativo
    build_window().show_all()
    Gtk.main()
