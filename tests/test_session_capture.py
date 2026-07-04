"""Unload — Bloco A′: captura da sessão do nó pelo workspace (lógica gi-free).

Prova a FONTE (LESSONS: unit test do parser não prova a fonte real): o encoding do slug
é validado contra os valores REAIS medidos em ~/.claude/projects em 2026-07-03, não só um
round-trip sintético. E `newest_session_id` é exercido com JSONL sintético + mtime real.
"""

import os

from maestro.engine.session_capture import (
    newest_session_id,
    project_dir,
    project_slug,
)
from maestro.engine.state.store import Store
from maestro.native.state import CanvasModel


# -- slug: reproduz EXATAMENTE o encoding do Claude Code (valores reais medidos) --
def test_project_slug_bate_com_dirs_reais():
    # esquerda = cwd real; direita = dir real observado em ~/.claude/projects (2026-07-03)
    casos = {
        "/home/kali": "-home-kali",
        "/home/kali/.local/share/maestro-console/workspaces/claude":
            "-home-kali--local-share-maestro-console-workspaces-claude",
        "/home/kali/.local/share/maestro-console/workspaces/claude-2":
            "-home-kali--local-share-maestro-console-workspaces-claude-2",
        "/home/kali/Documents/projets-dev/maestri-console":
            "-home-kali-Documents-projets-dev-maestri-console",
    }
    for cwd, slug in casos.items():
        assert project_slug(cwd) == slug


def test_project_dir_usa_home_injetado(tmp_path):
    d = project_dir("/ws/node1", home=tmp_path)
    assert d == tmp_path / ".claude" / "projects" / "-ws-node1"


# -- newest_session_id: o JSONL mais recente por mtime é a sessão viva --
def _mk_session(pdir, sid, mtime):
    f = pdir / f"{sid}.jsonl"
    f.write_text('{"type":"assistant"}\n', encoding="utf-8")
    os.utime(f, (mtime, mtime))
    return f


def test_newest_session_none_quando_dir_inexistente(tmp_path):
    # nó nunca gravou sessão → dir de projeto não existe → None (não explode)
    assert newest_session_id("/ws/never-ran", home=tmp_path) is None


def test_newest_session_none_quando_dir_vazio(tmp_path):
    ws = "/ws/node1"
    project_dir(ws, home=tmp_path).mkdir(parents=True)
    assert newest_session_id(ws, home=tmp_path) is None


def test_newest_session_pega_o_mais_recente(tmp_path):
    ws = "/ws/node1"
    pdir = project_dir(ws, home=tmp_path)
    pdir.mkdir(parents=True)
    _mk_session(pdir, "old-uuid", mtime=1000)
    _mk_session(pdir, "new-uuid", mtime=2000)  # mais novo → é a sessão viva
    _mk_session(pdir, "mid-uuid", mtime=1500)
    assert newest_session_id(ws, home=tmp_path) == "new-uuid"


def test_newest_session_ignora_nao_jsonl(tmp_path):
    ws = "/ws/node1"
    pdir = project_dir(ws, home=tmp_path)
    pdir.mkdir(parents=True)
    _mk_session(pdir, "real-uuid", mtime=1000)
    # arquivo não-jsonl mais novo NÃO deve ser escolhido
    other = pdir / "config.json"
    other.write_text("{}", encoding="utf-8")
    os.utime(other, (5000, 5000))
    assert newest_session_id(ws, home=tmp_path) == "real-uuid"


def test_newest_session_isolado_por_no(tmp_path):
    # dirs de projeto distintos (workspaces distintos) → sessões não vazam entre nós
    _mk_session(_dir_criado(tmp_path, "/ws/nodeA"), "sid-a", mtime=1000)
    _mk_session(_dir_criado(tmp_path, "/ws/nodeB"), "sid-b", mtime=2000)
    assert newest_session_id("/ws/nodeA", home=tmp_path) == "sid-a"
    assert newest_session_id("/ws/nodeB", home=tmp_path) == "sid-b"


def _dir_criado(home, ws):
    d = project_dir(ws, home=home)
    d.mkdir(parents=True)
    return d


# -- limpeza: Store.delete_ui + CanvasModel.clear_node_cfg (idempotente) --
def test_delete_ui_remove_linha_e_eh_idempotente(tmp_path):
    with Store(tmp_path / "m.db") as s:
        s.set_ui("k1", "v1")
        assert s.get_ui("k1") == "v1"
        s.delete_ui("k1")
        assert s.get_ui("k1") is None
        s.delete_ui("k1")  # 2ª vez não explode
        assert s.get_ui("k1") is None


def test_clear_node_cfg_apaga_sessao_persistida(tmp_path):
    db = tmp_path / "m.db"
    with Store(db) as s:
        m = CanvasModel(s)
        m.set_node_cfg("n1", "session", "sid-xyz")
        assert m.node_cfg("n1", "session") == "sid-xyz"
        m.clear_node_cfg("n1", "session")
        assert m.node_cfg("n1", "session") == ""  # default → nó reciclado não herda
    with Store(db) as s2:  # e persiste apagado após reabrir
        assert CanvasModel(s2).node_cfg("n1", "session") == ""
