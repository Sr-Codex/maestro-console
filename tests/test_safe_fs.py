"""S2 (review docs/33): stamp de brief/role/skill não pode seguir symlink → escrita no host.

O workspace é RW pro agente; um agente hostil troca CLAUDE.md/AGENTS.md/role.json (ou um pai
como `.maestri`) por symlink pra um alvo no host → o host (não-sandboxed) escreveria lá. Testa a
defesa (safe_fs, incl. TOCTOU do pai por race) E TODAS as entradas que a usam (briefs, roles,
ask_bus skills). gi-free → roda no CI.
"""

import threading
from pathlib import Path

import pytest

from maestro.engine import ask_bus, briefs, roles
from maestro.engine.safe_fs import UnsafeStampPath, safe_read_text, safe_write_text
from maestro.engine.teams import Role

_R = Role(name="coder", agent="claude", instruction="faça X")


def _victim(tmp_path, body="ORIGINAL DO HOST\n"):
    v = tmp_path / "host_secret"
    v.write_text(body)
    return v


# --- safe_fs primitivo --------------------------------------------------------


def test_safe_write_recusa_seguir_symlink_de_arquivo(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    victim = _victim(tmp_path)
    (ws / "CLAUDE.md").symlink_to(victim)
    safe_write_text(ws / "CLAUDE.md", "BRIEF NOVO\n", within=ws)
    assert victim.read_text() == "ORIGINAL DO HOST\n"      # host intacto
    assert not (ws / "CLAUDE.md").is_symlink()             # link trocado por regular
    assert (ws / "CLAUDE.md").read_text() == "BRIEF NOVO\n"


def test_safe_write_recusa_pai_symlinkado(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    outside = tmp_path / "fora"
    outside.mkdir()
    (ws / ".maestri").symlink_to(outside)
    with pytest.raises(UnsafeStampPath):
        safe_write_text(ws / ".maestri" / "role.json", "{}", within=ws)
    assert not (outside / "role.json").exists()


def test_safe_write_recusa_pai_intermediario_symlinkado(tmp_path):
    """Symlink no MEIO do caminho (não só o pai direto): ws/a/b/x com `a` symlink."""
    ws = tmp_path / "ws"
    ws.mkdir()
    outside = tmp_path / "fora"
    (outside / "b").mkdir(parents=True)
    (ws / "a").symlink_to(outside)
    with pytest.raises(UnsafeStampPath):
        safe_write_text(ws / "a" / "b" / "x", "y", within=ws)
    assert not (outside / "b" / "x").exists()


def test_safe_write_recusa_escapar_com_dotdot(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    with pytest.raises(UnsafeStampPath):
        safe_write_text(ws / ".." / "escapou", "y", within=ws)


def test_safe_read_trata_symlink_como_vazio(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "CLAUDE.md").symlink_to(_victim(tmp_path))
    assert safe_read_text(ws / "CLAUDE.md", within=ws) == ""


def test_toctou_pai_por_race_nunca_escreve_no_host(tmp_path):
    """FURO 2 da revisão Fable: um agente concorrente flipa `.maestri` (dir↔symlink) na janela
    entre a checagem e o open. A descida por dir_fd+O_NOFOLLOW fecha isso — o host NUNCA é
    escrito, aconteça o que acontecer com a ordem. (O `_assert_within` antigo furava aqui.)"""
    ws = tmp_path / "ws"
    ws.mkdir()
    outside = tmp_path / "fora"
    outside.mkdir()
    victim = outside / "role.json"
    stop = threading.Event()

    def flip():
        d = ws / ".maestri"
        while not stop.is_set():
            try:
                if d.is_symlink() or d.exists():
                    if d.is_dir() and not d.is_symlink():
                        for c in d.iterdir():
                            c.unlink()
                        d.rmdir()
                    else:
                        d.unlink()
                d.symlink_to(outside)  # aponta pra fora
            except OSError:
                pass
            try:
                d.unlink()
                d.mkdir()  # volta a ser dir real
            except OSError:
                pass

    t = threading.Thread(target=flip)
    t.start()
    try:
        for _ in range(300):
            try:
                safe_write_text(ws / ".maestri" / "role.json", "PAYLOAD", within=ws)
            except (UnsafeStampPath, OSError):
                pass  # recusa é o esperado quando o pai está symlinkado
    finally:
        stop.set()
        t.join()
    # invariante: em NENHUMA iteração o arquivo do host (fora do ws) foi escrito
    assert not victim.exists(), "escreveu no host via race no pai (TOCTOU não fechado)"


# --- as ENTRADAS reais: TODAS que o host carimba no workspace do agente -------
# (revisão Fable FURO 1: 4 stampers ficaram de fora do 1º commit)


def _symlinked(ws, fname, victim):
    (ws / fname).symlink_to(victim)


def test_briefs_install_nao_segue_symlink(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    v = _victim(tmp_path)
    _symlinked(ws, "CLAUDE.md", v)
    briefs.install_brief_block(str(ws), "objetivo", "decisões")
    assert v.read_text() == "ORIGINAL DO HOST\n"
    assert "objetivo" in (ws / "CLAUDE.md").read_text()


def test_roles_install_block_nao_segue_symlink(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    v = _victim(tmp_path)
    _symlinked(ws, "AGENTS.md", v)
    roles.install_role_block(str(ws), _R)
    assert v.read_text() == "ORIGINAL DO HOST\n"
    assert "coder" in (ws / "AGENTS.md").read_text()


def test_roles_remove_block_nao_segue_symlink(tmp_path):
    """FURO 1: remove_role_block (o irmão remove_brief_block foi convertido; este faltava)."""
    ws = tmp_path / "ws"
    ws.mkdir()
    body = "antes\n<!-- maestro-role:begin -->x<!-- maestro-role:end -->\ndepois\n"
    v = _victim(tmp_path, body)
    _symlinked(ws, "CLAUDE.md", v)
    roles.remove_role_block(str(ws))
    assert "maestro-role:begin" in v.read_text()  # host NÃO foi reescrito


def test_ask_bus_install_maestro_skill_nao_segue_symlink(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    v = _victim(tmp_path)
    _symlinked(ws, "CLAUDE.md", v)
    ask_bus.install_maestro_skill(str(ws), "claude-2")
    assert v.read_text() == "ORIGINAL DO HOST\n"  # não appendou no ~/.bashrc-like


def test_ask_bus_install_ask_skill_append_nao_segue_symlink(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    v = _victim(tmp_path)
    _symlinked(ws, "AGENTS.md", v)
    ask_bus.install_ask_skill(str(ws), "claude-2")
    assert v.read_text() == "ORIGINAL DO HOST\n"  # o open("a") cru appendaria no host


def test_ask_bus_connected_notes_nao_segue_symlink(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    v = _victim(tmp_path)
    _symlinked(ws, "CLAUDE.md", v)
    ask_bus.install_connected_notes_skill(str(ws), "claude-2", [("nota", "nota.md")])
    assert v.read_text() == "ORIGINAL DO HOST\n"


def test_roles_sidecar_pai_symlinkado_recusa(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    outside = tmp_path / "fora"
    outside.mkdir()
    (ws / ".maestri").symlink_to(outside)
    with pytest.raises(UnsafeStampPath):
        roles.write_role_sidecar(str(ws), _R)
    assert not (outside / "role.json").exists()


def test_caminho_normal_ainda_funciona(tmp_path):
    """Sanidade: sem symlink, todos os stampers escrevem normalmente."""
    ws = tmp_path / "ws"
    ws.mkdir()
    briefs.install_brief_block(str(ws), "obj", "brief")
    assert "obj" in (ws / "CLAUDE.md").read_text()
    ask_bus.install_maestro_skill(str(ws), "claude-2")
    ask_bus.install_ask_skill(str(ws), "claude-2")
    assert "maestro" in (ws / "CLAUDE.md").read_text().lower()
    p = roles.write_role_sidecar(str(ws), _R)
    assert Path(p).read_text().strip().startswith("{")
