"""Probes gi das contas por nó (docs/31/ADR-28) — UI do canvas sem GTK real.

Roda no python do SISTEMA (o .venv é gi-free). Padrão canvas_harness: CanvasWindow sem
__init__; mocka só fronteira (widget/respawn — já testados nos seus arquivos), nunca o
método de domínio sob teste. Cobre: troca de conta (E3 limpa sessão; E8a descarregado
não acorda; vivo reinicia), badge (§4.5), env do VTE com conta (E7), argv rebuild/resume
na conta (E1/E2) e exclusão desassociando nós (E8b).
"""

from types import SimpleNamespace

import pytest

from maestro.engine import accounts as acc
from maestro.engine.state.store import Store

pytest.importorskip("gi")  # canvas usa PyGObject; o .venv é gi-free → python do sistema
from canvas_harness import patch_agents, win  # noqa: E402

from maestro.engine import sandbox  # noqa: E402
from maestro.engine.session_capture import project_dir  # noqa: E402


class _FakeCap:
    def __init__(self):
        self.text, self.visible, self.tooltip = "", None, ""

    def set_text(self, t):
        self.text = t

    def set_visible(self, v):
        self.visible = v

    def set_tooltip_text(self, t):
        self.tooltip = t


def _w(store, tmp_path, nid="claude-2", monkeypatch=None, root=None):
    w = win(store, tmp_path, nid, term_=SimpleNamespace(_term=None))
    w._store = store
    w.heads = {nid: SimpleNamespace(_account=_FakeCap())}
    if monkeypatch is not None and root is not None:
        monkeypatch.setattr(acc, "accounts_root", lambda: root)
    return w


def _registra(store, tmp_path, name="trabalho", agent="claude"):
    return acc.add_account(store, name, agent, root=tmp_path / "accounts")


def test_node_account_resolve_e_badge(tmp_path, monkeypatch):
    s = Store(tmp_path / "t.db")
    w = _w(s, tmp_path, monkeypatch=monkeypatch, root=tmp_path / "accounts")
    _registra(s, tmp_path)
    assert w._node_account("claude-2") is None  # sem associação = default
    w.model.set_node_cfg("claude-2", "account", "trabalho")
    a = w._node_account("claude-2")
    assert a is not None and a.name == "trabalho"
    w._refresh_account_badge("claude-2")
    cap = w.heads["claude-2"]._account
    assert cap.text == "trabalho" and cap.visible is True
    assert "trabalho" in cap.tooltip and "accounts" in cap.tooltip  # nome + dir
    w.model.clear_node_cfg("claude-2", "account")
    w._refresh_account_badge("claude-2")
    assert cap.visible is False  # some no default


def test_apply_conta_vivo_limpa_sessao_e_respawna(tmp_path, monkeypatch):
    # E3: troca limpa node_cfg session E a tabela sessions; vivo → rebuild+respawn.
    s = Store(tmp_path / "t.db")
    w = _w(s, tmp_path, monkeypatch=monkeypatch, root=tmp_path / "accounts")
    _registra(s, tmp_path)
    w.model.set_node_cfg("claude-2", "session", "sid-velha")
    s.set_session("claude-2", "sid-velha")
    calls = []
    w._rebuild_agent_argv = lambda nid: calls.append(("rebuild", nid))
    w._respawn_node = lambda nid: calls.append(("respawn", nid))
    w._audit = lambda *a, **k: None
    w._apply_node_account("claude-2", "trabalho")
    assert w.model.node_cfg("claude-2", "account") == "trabalho"
    assert w.model.node_cfg("claude-2", "session") == ""  # E3
    assert s.get_session("claude-2") is None  # E3 (tabela do engine)
    assert ("rebuild", "claude-2") in calls and ("respawn", "claude-2") in calls


def test_apply_conta_descarregado_nao_acorda(tmp_path, monkeypatch):
    # E8a: nó unloaded troca cfg+argv SEM spawn (não ressuscitar quem libera RAM).
    s = Store(tmp_path / "t.db")
    w = _w(s, tmp_path, monkeypatch=monkeypatch, root=tmp_path / "accounts")
    _registra(s, tmp_path)
    w.model.set_node_cfg("claude-2", "unloaded", "1")
    calls = []
    w._rebuild_agent_argv = lambda nid: calls.append(("rebuild", nid))
    w._respawn_node = lambda nid: calls.append(("respawn", nid))
    w._audit = lambda *a, **k: None
    w._apply_node_account("claude-2", "trabalho")
    assert ("rebuild", "claude-2") in calls
    assert ("respawn", "claude-2") not in calls
    assert w.model.node_cfg("claude-2", "unloaded") == "1"  # segue dormindo


def test_remove_account_desassocia_so_os_do_agente(tmp_path, monkeypatch):
    # E8b: excluir desassocia os nós DAQUELA conta/agente; homônimo de outro agente fica.
    s = Store(tmp_path / "t.db")
    w = _w(s, tmp_path, monkeypatch=monkeypatch, root=tmp_path / "accounts")
    a = _registra(s, tmp_path, "trabalho", "claude")
    w.model.set_node_roster([
        {"nid": "claude-2", "kind": "agent", "base": "claude"},
        {"nid": "codex-1", "kind": "agent", "base": "codex"},
    ])
    w.model.set_node_cfg("claude-2", "account", "trabalho")
    w.model.set_node_cfg("codex-1", "account", "trabalho")  # homônimo, agente codex
    applied = []
    w._apply_node_account = lambda nid, name: applied.append((nid, name))
    w._audit = lambda *a, **k: None
    w._remove_account(a)
    assert applied == [("claude-2", "")]
    assert acc.find_account(s, "trabalho", "claude", root=tmp_path / "accounts") is None


def test_node_envv_conta_entra_e_no_vence(tmp_path, monkeypatch):
    # E7: conta entra no env do VTE (cobre comando custom); env do nó VENCE a conta.
    s = Store(tmp_path / "t.db")
    w = _w(s, tmp_path, monkeypatch=monkeypatch, root=tmp_path / "accounts")
    a = _registra(s, tmp_path)
    assert w._node_envv("claude-2") is None  # sem conta e sem env = herda
    w.model.set_node_cfg("claude-2", "account", "trabalho")
    env = dict(kv.split("=", 1) for kv in w._node_envv("claude-2"))
    assert env["CLAUDE_CONFIG_DIR"] == str(a.config_dir())
    w.model.set_node_cfg("claude-2", "env", "CLAUDE_CONFIG_DIR=/custom")
    env = dict(kv.split("=", 1) for kv in w._node_envv("claude-2"))
    assert env["CLAUDE_CONFIG_DIR"] == "/custom"  # nó vence conta (E6)


def test_rebuild_e_resume_argv_na_conta(tmp_path, monkeypatch):
    # E1/E2: o argv reconstruído (respawn) e o de resume rodam na CONTA do nó —
    # config-dir bound rw, var setada, e NENHUM path default do adapter em rw.
    s = Store(tmp_path / "t.db")
    w = _w(s, tmp_path, monkeypatch=monkeypatch, root=tmp_path / "accounts")
    a = _registra(s, tmp_path)
    w.model.set_node_cfg("claude-2", "account", "trabalho")
    patch_agents(monkeypatch, "claude")
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    w._rebuild_agent_argv("claude-2")
    joined = " ".join(w.frames["claude-2"]._base_argv)
    assert "--setenv CLAUDE_CONFIG_DIR" in joined and str(a.config_dir()) in joined
    assert "--bind ~/.claude" not in joined  # E1 (paths do TOML são ~/…)
    w.model.set_node_cfg("claude-2", "session", "sid-1")
    resume = " ".join(w._resume_argv("claude-2"))
    assert "--setenv CLAUDE_CONFIG_DIR" in resume  # E2: resume one-shot idem
    assert "sid-1" in resume


def test_capture_sessao_segue_a_conta(tmp_path, monkeypatch):
    # E3: unload captura a sessão no config-dir da conta (não no ~/.claude).
    s = Store(tmp_path / "t.db")
    w = _w(s, tmp_path, monkeypatch=monkeypatch, root=tmp_path / "accounts")
    a = _registra(s, tmp_path)
    w.model.set_node_cfg("claude-2", "account", "trabalho")
    pdir = project_dir(w._node_ws("claude-2"), config_dir=str(a.config_dir()))
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "sid-9.jsonl").write_text('{"type":"assistant"}\n', encoding="utf-8")
    assert w._capture_node_session("claude-2") == "sid-9"
    assert w.model.node_cfg("claude-2", "session") == "sid-9"
