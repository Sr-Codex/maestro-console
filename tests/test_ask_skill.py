"""Testes da Fase 4: skill no workspace + política calibrável por env (ADR-11)."""

from maestro.engine.ask_bus import (
    ASK_SKILL_MARKER,
    NOTES_SKILL_BEGIN,
    ask_skill_text,
    install_ask_skill,
    install_connected_notes_skill,
)
from maestro.engine.ask_router import AskPolicy, policy_from_env


def test_install_ask_skill_escreve_nos_dois_arquivos(tmp_path):
    install_ask_skill(tmp_path, "B")
    for fname in ("CLAUDE.md", "AGENTS.md"):
        txt = (tmp_path / fname).read_text(encoding="utf-8")
        assert ASK_SKILL_MARKER in txt
        assert "maestro-ask" in txt and "agente 'B'" in txt


def test_install_ask_skill_idempotente(tmp_path):
    install_ask_skill(tmp_path, "B")
    install_ask_skill(tmp_path, "B")  # 2ª vez não duplica
    txt = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert txt.count(ASK_SKILL_MARKER) == 1


def test_install_ask_skill_preserva_conteudo_existente(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# Papel: revisor\nregras...", encoding="utf-8")
    install_ask_skill(tmp_path, "B")
    txt = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "# Papel: revisor" in txt  # não clobberou
    assert ASK_SKILL_MARKER in txt  # e acrescentou a skill


def test_ask_skill_text_menciona_no():
    assert "agente 'codex'" in ask_skill_text("codex")


# -- Fase 4b: manifesto de notas conectadas --------------------------
def test_connected_notes_skill_escreve_e_lista(tmp_path):
    install_connected_notes_skill(tmp_path, "claude", [("Plano", "notes/n1.md")])
    for fname in ("CLAUDE.md", "AGENTS.md"):
        txt = (tmp_path / fname).read_text(encoding="utf-8")
        assert NOTES_SKILL_BEGIN in txt
        assert "Plano" in txt and "notes/n1.md" in txt and "agente 'claude'" not in txt


def test_connected_notes_skill_substitui_bloco(tmp_path):
    install_connected_notes_skill(tmp_path, "claude", [("A", "notes/a.md")])
    install_connected_notes_skill(tmp_path, "claude", [("B", "notes/b.md")])  # troca conexões
    txt = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert txt.count(NOTES_SKILL_BEGIN) == 1  # bloco substituído, não duplicado
    assert "notes/b.md" in txt and "notes/a.md" not in txt


def test_connected_notes_skill_preserva_ask_skill(tmp_path):
    install_ask_skill(tmp_path, "claude")  # bloco do maestro-ask já existe
    install_connected_notes_skill(tmp_path, "claude", [("A", "notes/a.md")])
    txt = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert ASK_SKILL_MARKER in txt and NOTES_SKILL_BEGIN in txt  # convivem


def test_connected_notes_skill_vazio(tmp_path):
    install_connected_notes_skill(tmp_path, "claude", [])
    txt = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "nenhuma nota conectada" in txt


def test_policy_from_env_default():
    p = policy_from_env(env={})
    assert (p.max_turns_per_pair, p.max_depth, p.identity_refresh_every) == (6, 3, 3)


def test_policy_from_env_override():
    p = policy_from_env(env={"MAESTRO_ASK_MAX_TURNS": "10", "MAESTRO_ASK_MAX_DEPTH": "5"})
    assert p.max_turns_per_pair == 10 and p.max_depth == 5


def test_policy_from_env_invalido_cai_no_default():
    p = policy_from_env(env={"MAESTRO_ASK_MAX_TURNS": "abc", "MAESTRO_ASK_IDENTITY_EVERY": "0"})
    assert p.max_turns_per_pair == 6  # inválido -> default
    assert p.identity_refresh_every == 1  # max(1, 0) = 1
    assert isinstance(p, AskPolicy)
