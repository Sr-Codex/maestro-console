"""Fase 4 (docs/26) — GUARDA de regressão do bug "diálogo abre em tela cheia".

Um `Gtk.Label` com quebra de linha (`wrap=True`/`set_wrap(True)`) SEM `max_width_chars`
reporta a largura natural do texto inteiro numa linha e ESTICA a `Gtk.Window` (no GTK4
não há clamp de janela). Esta guarda varre o FONTE de `canvas.py` via AST e falha se
algum label de quebra ficar sem largura máxima.

Roda no `.venv` (só `ast` + leitura de arquivo — NÃO precisa de `gi`/display), então é o
único teste do bug **coberto pelo CI** (os testes gi de canvas são pulados no venv).

Regra: todo `X.set_wrap(True)` deve, na MESMA função, ter um `X.set_max_width_chars(...)`,
OU carregar um marcador `# wrap-exempt: <motivo>` na própria linha (casos legítimos: label
dentro de `ScrolledWindow`, ou que não é de diálogo). E todo `Gtk.Label(..., wrap=True)`
deve trazer `max_width_chars=...` na mesma chamada (ex.: o helper `_hint_label`).
Heurística honesta (tripwire), não prova formal — mas trava a volta do bug sem display.
"""

import ast
from pathlib import Path

CANVAS = Path(__file__).resolve().parents[1] / "maestro" / "native" / "canvas.py"


def _src_and_tree():
    src = CANVAS.read_text(encoding="utf-8")
    return src, src.splitlines(), ast.parse(src)


def _funcs(tree):
    """(lineno, end_lineno, node) de cada função, da menor p/ a maior (p/ achar a enclosing)."""
    fs = [(n.lineno, n.end_lineno, n) for n in ast.walk(tree)
          if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return sorted(fs, key=lambda t: t[1] - t[0])


def _enclosing(fs, lineno):
    for lo, hi, node in fs:  # menor range primeiro → a função mais interna que contém a linha
        if lo <= lineno <= hi:
            return node
    return None


def _is_true(arg):
    return isinstance(arg, ast.Constant) and arg.value is True


def _receiver(src, call):
    """Texto do receptor de `X.metodo(...)` (ex.: 'out', 'self.x')."""
    return ast.get_source_segment(src, call.func.value)


def test_todo_label_de_quebra_em_canvas_limita_largura():
    src, lines, tree = _src_and_tree()
    fs = _funcs(tree)

    # 1) set_max_width_chars(...) por função: (id_da_função, receptor)
    constrained = set()
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "set_max_width_chars"):
            fn = _enclosing(fs, n.lineno)
            constrained.add((id(fn), _receiver(src, n)))

    violations = []

    # 2) todo X.set_wrap(True) precisa de X.set_max_width_chars na mesma função OU marcador
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "set_wrap" and n.args and _is_true(n.args[0])):
            line = lines[n.lineno - 1]
            if "wrap-exempt" in line:
                continue
            fn = _enclosing(fs, n.lineno)
            if (id(fn), _receiver(src, n)) not in constrained:
                violations.append(f"L{n.lineno}: {line.strip()}")

    # 3) todo Gtk.Label(..., wrap=True) precisa de max_width_chars=... na MESMA chamada
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call)
                and ast.get_source_segment(src, n.func) in ("Gtk.Label", "Label")):
            continue
        kw = {k.arg for k in n.keywords if k.arg}
        wrap_true = any(k.arg == "wrap" and _is_true(k.value) for k in n.keywords)
        exempt = "wrap-exempt" in lines[n.lineno - 1]
        if wrap_true and "max_width_chars" not in kw and not exempt:
            violations.append(f"L{n.lineno}: Gtk.Label(wrap=True) sem max_width_chars")

    assert not violations, (
        "Label de diálogo com quebra SEM max_width_chars (bug de tela cheia — docs/26). "
        "Use self._hint_label(...) ou set_max_width_chars(...), ou marque # wrap-exempt: motivo.\n"
        + "\n".join(violations))


def test_hint_label_existe_como_fabrica_sancionada():
    """O helper que sanciona o padrão certo precisa continuar existindo (o plano depende dele)."""
    src, _lines, tree = _src_and_tree()
    names = {n.name for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "_hint_label" in names
    assert "_confirm_dialog" in names
