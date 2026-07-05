"""R2 do reattach (docs/25 §4-R2): detecção de nós órfãos pós-crash.

Gi-free. Exercita o critério inteiro (crash ∧ agent ∧ ¬unloaded ∧ transcript-no-disco) e
prova que os nós certos ganham as flags `orphan`+`unloaded`+`session` e os errados NÃO.
Molde do `test_session_capture.py`: home injetável + JSONL sintético no dir de projeto.
"""

from maestro.engine.orphans import detect_orphans
from maestro.engine.session_capture import project_dir
from maestro.engine.state.store import Store
from maestro.native.state import CanvasModel


def _mk_transcript(ws_base, nid, home):
    """Cria um JSONL de sessão no dir de projeto do nó (como o Claude Code grava)."""
    pdir = project_dir(f"{ws_base}/{nid}", home=home)
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "sess-abc.jsonl").write_text('{"type":"assistant"}\n', encoding="utf-8")


def _model(tmp_path):
    return CanvasModel(Store(tmp_path / "m.db"))


def test_sem_crash_nao_marca_nada(tmp_path):
    home = tmp_path / "home"
    ws = str(tmp_path / "ws")
    _mk_transcript(ws, "claude", home)
    m = _model(tmp_path)
    roster = [{"nid": "claude", "kind": "agent", "base": "claude"}]
    assert detect_orphans(m, roster, crashed=False, ws_base=ws, home=home) == []
    assert not m.node_cfg("claude", "orphan")


def test_agente_com_transcript_vira_orfao(tmp_path):
    home = tmp_path / "home"
    ws = str(tmp_path / "ws")
    _mk_transcript(ws, "claude", home)
    m = _model(tmp_path)
    roster = [{"nid": "claude", "kind": "agent", "base": "claude"}]
    out = detect_orphans(m, roster, crashed=True, ws_base=ws, home=home)
    assert out == ["claude"]
    assert m.node_cfg("claude", "orphan") == "1"
    assert m.node_cfg("claude", "unloaded") == "1"  # reusa dormência
    assert m.node_cfg("claude", "session") == "sess-abc"  # sessão a retomar


def test_agente_sem_transcript_nao_e_orfao(tmp_path):
    # subiu e morreu antes de gravar qualquer JSONL → nada a resumir → boot normal
    home = tmp_path / "home"
    ws = str(tmp_path / "ws")
    m = _model(tmp_path)
    roster = [{"nid": "claude", "kind": "agent", "base": "claude"}]
    assert detect_orphans(m, roster, crashed=True, ws_base=ws, home=home) == []
    assert not m.node_cfg("claude", "orphan")


def test_descarregado_de_proposito_nao_vira_orfao(tmp_path):
    # unloaded=1 antes do crash = escolha do usuário → NÃO é órfão (sem perda a recuperar)
    home = tmp_path / "home"
    ws = str(tmp_path / "ws")
    _mk_transcript(ws, "claude", home)
    m = _model(tmp_path)
    m.set_node_cfg("claude", "unloaded", "1")
    roster = [{"nid": "claude", "kind": "agent", "base": "claude"}]
    assert detect_orphans(m, roster, crashed=True, ws_base=ws, home=home) == []
    assert not m.node_cfg("claude", "orphan")  # não recebe o rótulo de órfão


def test_shell_nunca_e_orfao(tmp_path):
    # shell não tem sessão a retomar (mesmo com crash)
    home = tmp_path / "home"
    ws = str(tmp_path / "ws")
    m = _model(tmp_path)
    roster = [{"nid": "shell-1", "kind": "shell", "base": None}]
    assert detect_orphans(m, roster, crashed=True, ws_base=ws, home=home) == []
    assert not m.node_cfg("shell-1", "orphan")


def test_so_os_agentes_certos_no_roster_misto(tmp_path):
    home = tmp_path / "home"
    ws = str(tmp_path / "ws")
    _mk_transcript(ws, "claude", home)  # tem transcript
    _mk_transcript(ws, "codex", home)  # tem transcript
    # "gemini" sem transcript; "shell-1" é shell
    m = _model(tmp_path)
    m.set_node_cfg("codex", "unloaded", "1")  # descarregado de propósito
    roster = [
        {"nid": "claude", "kind": "agent", "base": "claude"},
        {"nid": "codex", "kind": "agent", "base": "codex"},
        {"nid": "gemini", "kind": "agent", "base": "gemini"},
        {"nid": "shell-1", "kind": "shell", "base": None},
    ]
    out = detect_orphans(m, roster, crashed=True, ws_base=ws, home=home)
    assert out == ["claude"]  # só o claude: agent + transcript + não-descarregado
