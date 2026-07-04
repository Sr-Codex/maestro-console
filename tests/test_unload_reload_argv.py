"""Unload — Bloco C: argv de RETOMADA (`agent_argv(resume_session=...)`).

Testa a montagem do argv one-shot de resume com os perfis REAIS dos adapters TOML
(não sintéticos — lição do LESSONS: provar a fonte, não só o parser). Sem GTK →
roda no .venv.
"""

import pytest

from maestro.engine.adapters.base import load_profiles
from maestro.engine.sandbox import bwrap_available
from maestro.native.agents import agent_argv

pytestmark = pytest.mark.skipif(not bwrap_available(), reason="bwrap ausente")


def test_resume_claude_anexa_flags_com_id(tmp_path):
    """claude (modo flag): resume anexa `--resume <id capturado>` logo após o binário."""
    prof = load_profiles()["claude"]
    inner = agent_argv(prof, str(tmp_path), resume_session="abc-123")[-1]
    assert inner.startswith("claude --resume abc-123")
    assert "exec /bin/bash" in inner  # ao sair da IA, card vira shell (comportamento base)


def test_resume_claude_convive_com_auto_approve(tmp_path):
    """resume + auto_approve: as duas famílias de flag entram (claude aceita ambas)."""
    prof = load_profiles()["claude"]
    inner = agent_argv(prof, str(tmp_path), resume_session="abc-123",
                       auto_approve=True)[-1]
    assert "--resume abc-123" in inner
    assert "bypassPermissions" in inner


def test_resume_none_e_vazio_nao_mudam_o_claude(tmp_path):
    """Sem resume (None) OU com id vazio (claude sem captura): binário puro — o
    chamador é quem decide não retomar; aqui nunca sai um `--resume` sem id."""
    prof = load_profiles()["claude"]
    assert agent_argv(prof, str(tmp_path))[-1].startswith("claude;")
    assert agent_argv(prof, str(tmp_path), resume_session=None)[-1].startswith("claude;")
    inner_empty = agent_argv(prof, str(tmp_path), resume_session="")[-1]
    assert "--resume" not in inner_empty


def test_resume_codex_e_picker_sem_flags_de_permissao(tmp_path):
    """codex (modo subcommand): resume = `codex resume` (PICKER; id não se aplica) e
    NÃO anexa flags de permissão — o subcomando não as aceita (precedente base.py)."""
    prof = load_profiles()["codex"]
    inner = agent_argv(prof, str(tmp_path), resume_session="", auto_approve=True)[-1]
    assert inner.startswith("codex resume;")
    assert "dangerously-bypass" not in inner
    # e um id capturado por engano também não muda nada (picker ignora)
    inner_id = agent_argv(prof, str(tmp_path), resume_session="xyz")[-1]
    assert inner_id.startswith("codex resume;")
    assert "xyz" not in inner_id
