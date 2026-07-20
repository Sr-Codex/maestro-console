"""S2 (review docs/33): stamp de brief/role não pode seguir symlink → escrita no host.

O workspace é RW pro agente; um agente hostil troca CLAUDE.md/AGENTS.md/role.json (ou um
pai como `.maestri`) por symlink pra um alvo no host → o host (não-sandboxed) escreveria lá.
Testa a defesa (safe_fs) E as duas entradas que a usam (briefs, roles). gi-free → roda no CI.
"""

from pathlib import Path

import pytest

from maestro.engine import briefs, roles
from maestro.engine.safe_fs import UnsafeStampPath, safe_read_text, safe_write_text
from maestro.engine.teams import Role


def _victim(tmp_path):
    """Arquivo-alvo no 'host', fora do workspace."""
    v = tmp_path / "host_secret"
    v.write_text("ORIGINAL DO HOST\n")
    return v


def test_safe_write_recusa_seguir_symlink_de_arquivo(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    victim = _victim(tmp_path)
    (ws / "CLAUDE.md").symlink_to(victim)  # booby-trap do agente
    safe_write_text(ws / "CLAUDE.md", "BRIEF NOVO\n", within=ws)
    # o alvo do host permanece intacto; o symlink foi trocado por arquivo regular no ws
    assert victim.read_text() == "ORIGINAL DO HOST\n"
    assert not (ws / "CLAUDE.md").is_symlink()
    assert (ws / "CLAUDE.md").read_text() == "BRIEF NOVO\n"


def test_safe_write_recusa_pai_symlinkado(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    outside = tmp_path / "fora"
    outside.mkdir()
    (ws / ".maestri").symlink_to(outside)  # pai symlinkado pra fora do ws
    with pytest.raises(UnsafeStampPath):
        safe_write_text(ws / ".maestri" / "role.json", "{}", within=ws)
    assert not (outside / "role.json").exists()  # nada escrito fora


def test_safe_read_trata_symlink_como_vazio(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    victim = _victim(tmp_path)
    (ws / "CLAUDE.md").symlink_to(victim)
    assert safe_read_text(ws / "CLAUDE.md") == ""  # não puxa conteúdo do host


def test_briefs_install_nao_escreve_no_alvo_do_symlink(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    victim = _victim(tmp_path)
    (ws / "CLAUDE.md").symlink_to(victim)
    briefs.install_brief_block(str(ws), "objetivo", "decisões", "2026-07-20")
    assert victim.read_text() == "ORIGINAL DO HOST\n"          # host intacto
    assert "objetivo" in (ws / "CLAUDE.md").read_text()        # brief no ws (regular)
    assert not (ws / "CLAUDE.md").is_symlink()


def test_roles_install_block_nao_segue_symlink(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    victim = _victim(tmp_path)
    (ws / "AGENTS.md").symlink_to(victim)
    roles.install_role_block(str(ws), Role(name="coder", agent="claude", instruction="faça X"))
    assert victim.read_text() == "ORIGINAL DO HOST\n"
    assert "coder" in (ws / "AGENTS.md").read_text()


def test_roles_sidecar_pai_symlinkado_recusa(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    outside = tmp_path / "fora"
    outside.mkdir()
    (ws / ".maestri").symlink_to(outside)
    with pytest.raises(UnsafeStampPath):
        roles.write_role_sidecar(str(ws), Role(name="coder", agent="claude", instruction="X"))
    assert not (outside / "role.json").exists()


def test_caminho_normal_ainda_funciona(tmp_path):
    """Sanidade: sem symlink, o stamp escreve normalmente."""
    ws = tmp_path / "ws"
    ws.mkdir()
    briefs.install_brief_block(str(ws), "obj", "brief")
    assert "obj" in (ws / "CLAUDE.md").read_text()
    p = roles.write_role_sidecar(str(ws), Role(name="r", agent="claude", instruction="i"))
    assert Path(p).read_text().strip().startswith("{")
