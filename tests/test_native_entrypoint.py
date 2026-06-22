"""Testes do entrypoint do canvas nativo (V6-S1).

O app GTK+VTE precisa do PyGObject do sistema (não está no venv de teste), então
aqui validamos só o entrypoint e a mensagem amigável quando o gi falta. A
validação real do GTK+VTE foi feita no spike (na tela do uConsole).
"""

import importlib.util


def test_help_menciona_canvas(capsys):
    from maestro.__main__ import main

    assert main([]) == 0
    assert "maestro canvas" in capsys.readouterr().out


def test_canvas_sem_gi_da_mensagem_amigavel(capsys):
    """No venv (sem python3-gi) o subcomando explica, sem estourar."""
    from maestro.__main__ import main

    if importlib.util.find_spec("gi") is not None:
        return  # ambiente tem gi (sistema) — não dá p/ exercitar o caminho de erro
    assert main(["canvas"]) == 1
    out = capsys.readouterr().out
    assert "Canvas nativo requer" in out and "python3-gi" in out
