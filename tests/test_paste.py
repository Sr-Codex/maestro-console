"""Paste/drag de imagem — lógica pura (docs/32/ADR-29). Gi-free.

Cobre as emendas de LÓGICA do Fable: E1 (nome hostil nunca injetável), E3 (needs_copy
por prefixos derivados do sandbox — inclui a máscara de contas), E6 (unicidade no mesmo
segundo, paste e cópia de drop).
"""

from datetime import datetime

from maestro.engine.sandbox import invisible_prefixes
from maestro.native import paste

NOW = datetime(2026, 7, 18, 15, 4, 5)


# --- E1: injeção segura ------------------------------------------------------


def test_injectable_bloqueia_control_chars():
    assert paste.injectable("/home/kali/foto.png")
    assert paste.injectable("/home/kali/com espaço e 'aspas'.png")
    assert not paste.injectable("/ws/a\rrm -rf x")  # \r = auto-submit no PTY
    assert not paste.injectable("/ws/a\nb")
    assert not paste.injectable("/ws/a\x1b[2Jb")  # ESC = sequência de terminal
    assert not paste.injectable("/ws/a\x7fb")  # DEL


def test_quote_path_espaco_e_aspas():
    q = paste.quote_path("/tmp/o meu 'arquivo'.png")
    assert " " not in q.strip("'") or q.startswith("'")  # veio quoted
    assert q != "/tmp/o meu 'arquivo'.png"


# --- E6: unicidade -----------------------------------------------------------


def test_paste_filename_unico_no_mesmo_segundo():
    a = paste.paste_filename(NOW)
    assert a == "paste-20260718-150405.png"
    b = paste.paste_filename(NOW, taken={a})
    c = paste.paste_filename(NOW, taken={a, b})
    assert len({a, b, c}) == 3  # nunca colide nem sobrescreve


def test_copy_name_unico_e_seguro():
    a = paste.copy_name("relatório final.pdf", NOW)
    assert a.startswith("drop-20260718-150405-") and a.endswith(".pdf")
    assert paste.injectable(a) and " " not in a
    b = paste.copy_name("relatório final.pdf", NOW, taken={a})
    assert b != a
    hostil = paste.copy_name("a\rrm -rf x", NOW)
    assert paste.injectable(hostil)  # nome GERADO é sempre injetável


def test_safe_name_nunca_vazio_nem_dotfile():
    assert paste.safe_name("...") == "arquivo"
    assert not paste.safe_name(".bashrc").startswith(".")


# --- E3: needs_copy por prefixos do sandbox ----------------------------------


def test_needs_copy_prefixos():
    prefs = ["/tmp", "/home/kali/.maestro-accounts"]
    assert paste.needs_copy("/tmp/shot.png", prefs)
    assert paste.needs_copy("/tmp", prefs)
    assert paste.needs_copy("/home/kali/.maestro-accounts/claude/x/a.png", prefs)
    assert not paste.needs_copy("/tmpfoo/shot.png", prefs)  # prefixo é por componente
    assert not paste.needs_copy("/home/kali/Desktop/shot.png", prefs)


def test_invisible_prefixes_cobre_os_mounts_do_sandbox():
    prefs = invisible_prefixes()
    assert "/tmp" in prefs and "/dev" in prefs and "/proc" in prefs
    assert any(p.endswith(".maestro-accounts") for p in prefs)  # máscara ADR-28
    assert any(p.startswith("/run/user/") for p in prefs)
