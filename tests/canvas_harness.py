"""Scaffold compartilhado dos testes de canvas (roda no python do SISTEMA — precisa de `gi`).

Extrai os helpers antes DUPLICADOS em `test_unload_*`/`test_reattach` (SonarCloud acusava
duplicação de código novo). NÃO é um módulo de teste (sem prefixo `test_`) — é importado pelos
testes SÓ depois do `pytest.importorskip("gi")`, então nunca é carregado no `.venv` gi-free.

Métodos REAIS ficam sob teste; aqui só se monta a fronteira (widget GTK fake + `CanvasWindow`
sem `__init__`).
"""

from types import SimpleNamespace

from maestro.engine.adapters.base import load_profiles
from maestro.native.canvas import CanvasWindow
from maestro.native.state import CanvasModel


def term(pid=None, state="idle", pending=False):
    """Terminal fake (SimpleNamespace) — superset que cobre unload (state/pending) e reload
    (connect/disconnect do monitor)."""
    return SimpleNamespace(
        _child_pid=pid, _pidfd=None, _respawn_state=state, _respawn_pending=pending,
        _respawn_force_src=None, _destroyed=False,
        reset=lambda *_a: None, feed=lambda *_a: None,
        connect=lambda *_a, **_k: 1, disconnect=lambda *_a: None,
    )


def win(store, tmp_path, nid, term_=None, *, kind="agent", base="claude",
        roster=True, mon=None, mon_alerted=None):
    """`CanvasWindow` sem `__init__` (não cria GTK); só os atributos que os métodos sob teste leem.

    `roster`/`mon`/`mon_alerted` cobrem as variações dos arquivos (reload/reattach setam o roster
    e `_mon` vazio; o unload-node não seta roster e liga o monitor)."""
    w = CanvasWindow.__new__(CanvasWindow)
    w.model = CanvasModel(store)
    w._store = store  # produção seta no __init__; contas por nó (docs/31) resolve por ele
    if roster:
        w.model.set_node_roster([{"nid": nid, "kind": kind, "base": base}])
    w._ask_bus_dir = str(tmp_path / "askbus")  # _node_ws → tmp/workspaces/<nid>
    (tmp_path / "askbus").mkdir(exist_ok=True)
    if term_ is not None:
        w.frames = {nid: SimpleNamespace(_term=term_, _base_argv=["/bin/bash"])}
    else:
        w.frames = {}
    w._mon = mon if mon is not None else {}
    w._mon_alerted = mon_alerted if mon_alerted is not None else set()
    w._ram_alerted = set()  # Bloco D
    w._node_state = {}
    w._focused_nid = None
    w.heads = {}
    w.plane = SimpleNamespace(queue_draw=lambda: None)
    return w


def patch_agents(monkeypatch, *bases):
    """installed_agents() do canvas → perfis REAIS do TOML, sem exigir binário no PATH."""
    profs = load_profiles()
    monkeypatch.setattr("maestro.native.canvas.installed_agents",
                        lambda: {b: profs[b] for b in bases})
