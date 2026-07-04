"""Unload — Bloco C: retomar (reload resume-aware) + startup sem spawn + toggle ⏏.

Mesmo padrão dos Blocos A′/B: métodos REAIS sob teste; só as fronteiras são
substituídas (spawn de PTY `_spawn_into`, catálogo `installed_agents`, widget VTE).
Perfis dos adapters são os REAIS (TOML) — nada de profile sintético.
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("gi")  # canvas usa PyGObject; o .venv é gi-free → python do sistema
from maestro.engine.adapters.base import load_profiles  # noqa: E402
from maestro.engine.sandbox import bwrap_available  # noqa: E402
from maestro.engine.state.store import Store  # noqa: E402
from maestro.native.canvas import CanvasWindow  # noqa: E402
from maestro.native.state import CanvasModel  # noqa: E402

pytestmark = pytest.mark.skipif(not bwrap_available(), reason="bwrap ausente")


def _term(pid=None):
    return SimpleNamespace(
        _child_pid=pid, _pidfd=None, _respawn_state="idle", _respawn_pending=False,
        _respawn_force_src=None, _destroyed=False,
        reset=lambda *_a: None, feed=lambda *_a: None,
        connect=lambda *_a, **_k: 1,  # _set_node_monitor religa o contents-changed
        disconnect=lambda *_a: None,
    )


def _win(store, tmp_path, nid, term, *, kind="agent", base="claude"):
    w = CanvasWindow.__new__(CanvasWindow)  # sem __init__ → não cria GTK
    w.model = CanvasModel(store)
    w.model.set_node_roster([{"nid": nid, "kind": kind, "base": base}])
    w._ask_bus_dir = str(tmp_path / "askbus")  # _node_ws → tmp/workspaces/<nid>
    (tmp_path / "askbus").mkdir(exist_ok=True)
    w.frames = {nid: SimpleNamespace(_term=term, _base_argv=["/bin/bash"])}
    w._mon = {}
    w._mon_alerted = set()
    w._ram_alerted = set()  # Bloco D
    w._node_state = {}
    w._focused_nid = None
    w.heads = {}
    w.plane = SimpleNamespace(queue_draw=lambda: None)
    return w


def _patch_agents(monkeypatch, *bases):
    """installed_agents() do canvas → perfis REAIS do TOML, sem exigir binário no PATH."""
    profs = load_profiles()
    monkeypatch.setattr("maestro.native.canvas.installed_agents",
                        lambda: {b: profs[b] for b in bases})


def test_reload_retoma_claude_com_resume_oneshot(tmp_path, monkeypatch):
    """Fluxo inteiro: nó descarregado + sessão capturada → spawn com `--resume <id>`,
    flag limpa, monitor religado e `_base_argv` INTACTO (a semântica decidida:
    Retomar = resume one-shot; Reiniciar continua = começar do zero)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    nid = "term1"
    spawned = []
    with Store(tmp_path / "m.db") as store:
        term = _term()
        w = _win(store, tmp_path, nid, term)
        _patch_agents(monkeypatch, "claude")
        monkeypatch.setattr("maestro.native.canvas._spawn_into",
                            lambda *a, **k: spawned.append(a))
        w.model.set_node_cfg(nid, "unloaded", "1")
        w.model.set_node_cfg(nid, "session", "sid-42")  # capturada pelo A′

        w._reload_node(nid)

        assert len(spawned) == 1
        inner = spawned[0][1][-1]  # string do bash -c dentro do bwrap
        assert "claude --resume sid-42" in inner
        assert w._node_unloaded(nid) is False  # flag limpa
        assert w.frames[nid]._base_argv == ["/bin/bash"]  # NUNCA mutado (one-shot)
        assert nid in w._mon  # monitor religado (preferência default-ON de agente)
        assert w._mon[nid].get("skip") is True  # banner do spawn não vira falso "parou"


def test_reload_sem_sessao_volta_do_zero(tmp_path, monkeypatch):
    """claude sem sessão capturada: não há o que retomar → spawn com o argv natural."""
    monkeypatch.setenv("HOME", str(tmp_path))
    nid = "term1"
    spawned = []
    with Store(tmp_path / "m.db") as store:
        w = _win(store, tmp_path, nid, _term())
        _patch_agents(monkeypatch, "claude")
        monkeypatch.setattr("maestro.native.canvas._spawn_into",
                            lambda *a, **k: spawned.append(a))
        w.model.set_node_cfg(nid, "unloaded", "1")

        w._reload_node(nid)

        assert len(spawned) == 1
        assert spawned[0][1] == ["/bin/bash"]  # argv natural (sem resume)
        assert w._node_unloaded(nid) is False


def test_reload_codex_usa_picker(tmp_path, monkeypatch):
    """codex (subcommand): retomar SEMPRE via `codex resume` (picker; humano escolhe)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    nid = "cx1"
    spawned = []
    with Store(tmp_path / "m.db") as store:
        w = _win(store, tmp_path, nid, _term(), base="codex")
        _patch_agents(monkeypatch, "codex")
        monkeypatch.setattr("maestro.native.canvas._spawn_into",
                            lambda *a, **k: spawned.append(a))
        w.model.set_node_cfg(nid, "unloaded", "1")

        w._reload_node(nid)

        inner = spawned[0][1][-1]
        assert inner.startswith("codex resume;") or " codex resume;" in inner


def test_reload_comando_custom_manda(tmp_path, monkeypatch):
    """Edge §4-C: nó com `command` custom bypassa o resume — o comando do usuário manda."""
    monkeypatch.setenv("HOME", str(tmp_path))
    nid = "term1"
    spawned = []
    with Store(tmp_path / "m.db") as store:
        w = _win(store, tmp_path, nid, _term())
        _patch_agents(monkeypatch, "claude")
        monkeypatch.setattr("maestro.native.canvas._spawn_into",
                            lambda *a, **k: spawned.append(a))
        w.model.set_node_cfg(nid, "unloaded", "1")
        w.model.set_node_cfg(nid, "session", "sid-42")
        w.model.set_node_cfg(nid, "command", "htop")

        w._reload_node(nid)

        argv = spawned[0][1]
        assert argv[:2] == ["/bin/bash", "-lc"] and "htop" in argv[2]
        assert "--resume" not in " ".join(argv)


def test_reload_noop_sem_flag_e_corrige_flag_mentirosa(tmp_path, monkeypatch):
    """(a) nó não-descarregado: clique no terminal é no-op (o gesto dispara em todos);
    (b) flag 'unloaded' com processo VIVO: corrige a flag e NÃO empilha spawn."""
    monkeypatch.setenv("HOME", str(tmp_path))
    nid = "term1"
    spawned = []
    with Store(tmp_path / "m.db") as store:
        w = _win(store, tmp_path, nid, _term())
        _patch_agents(monkeypatch, "claude")
        monkeypatch.setattr("maestro.native.canvas._spawn_into",
                            lambda *a, **k: spawned.append(a))
        w._reload_node(nid)  # (a) sem flag
        assert spawned == []

        w.frames[nid]._term = _term(pid=4242)  # (b) flag mente: processo vivo
        w.model.set_node_cfg(nid, "unloaded", "1")
        w._reload_node(nid)
        assert spawned == []  # não empilha um 2º processo
        assert w._node_unloaded(nid) is False  # só corrige o estado


def test_make_node_term_descarregado_nasce_sem_spawn(tmp_path, monkeypatch):
    """STARTUP (o maior ganho): nó com flag persistida nasce SEM processo — reabrir o
    app não ressuscita N agentes; nó normal segue no make_terminal de sempre."""
    monkeypatch.setenv("HOME", str(tmp_path))
    nid = "term1"
    dead, made = object(), object()
    with Store(tmp_path / "m.db") as store:
        w = _win(store, tmp_path, nid, _term())
        monkeypatch.setattr("maestro.native.canvas._dead_terminal", lambda: dead)
        monkeypatch.setattr("maestro.native.canvas.make_terminal",
                            lambda *a, **k: made)
        w.model.set_node_cfg(nid, "unloaded", "1")
        assert w._make_node_term(nid, ["/bin/bash"]) is dead  # sem spawn
        w.model.clear_node_cfg(nid, "unloaded")
        assert w._make_node_term(nid, ["/bin/bash"]) is made  # caminho normal


def test_ctx_unload_vira_toggle(tmp_path, monkeypatch):
    """⏏ na cápsula: nó carregado → confirmação de descarregar; descarregado → retomar."""
    monkeypatch.setenv("HOME", str(tmp_path))
    nid = "term1"
    calls = []
    with Store(tmp_path / "m.db") as store:
        w = _win(store, tmp_path, nid, _term())
        w._sel_nid = lambda: nid
        w._confirm_unload = lambda n: calls.append(("confirm", n))
        w._reload_node = lambda n: calls.append(("reload", n))
        w._ctx_unload_node()  # carregado
        w.model.set_node_cfg(nid, "unloaded", "1")
        w._ctx_unload_node()  # descarregado
        assert calls == [("confirm", nid), ("reload", nid)]
