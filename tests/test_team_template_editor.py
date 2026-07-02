"""Testes do editor visual de Team Templates (Fase C, docs/14 §11).

`_save_team_from_staging` é a lógica extraída (build+valida+persiste), testável sem GTK —
espelha `_apply_team_decision` da Fase B. Os diálogos (`_team_edit_dialog`/
`_team_group_edit_dialog`) só manipulam widgets e chamam essa função; não testados aqui
diretamente (fronteira GTK), só a lógica que importa pra correção.
"""

import pytest

pytest.importorskip("gi")  # canvas usa PyGObject; o .venv é gi-free → roda no python do sistema
from maestro.engine.team_templates import BUILTIN_TEAM_TEMPLATES  # noqa: E402
from maestro.native.canvas import CanvasWindow  # noqa: E402


def _make_win(tmp_path):
    w = CanvasWindow.__new__(CanvasWindow)  # sem __init__ → não cria GTK
    path = tmp_path / "team_templates.json"
    w._team_templates_path = lambda: path  # isola do arquivo real do usuário
    return w


def _valid_staging(name="meu-time"):
    return {
        "name": name,
        "description": "desc",
        "manager": None,
        "groups": [
            {
                "name": "Grupo",
                "color": "",
                "leader": None,
                "members": [
                    {"name": "coder", "agent": "claude", "instruction": "implemente", "color": ""},
                ],
            }
        ],
    }


def test_save_novo_template_persiste(tmp_path):
    w = _make_win(tmp_path)
    ok, msg = CanvasWindow._save_team_from_staging(w, _valid_staging(), None)
    assert ok and msg == ""
    assert "meu-time" in {t.name for t in CanvasWindow._team_templates(w)}


def test_save_template_sem_grupo_recusa_e_nao_persiste(tmp_path):
    w = _make_win(tmp_path)
    staging = _valid_staging()
    staging["groups"] = []
    ok, msg = CanvasWindow._save_team_from_staging(w, staging, None)
    assert not ok
    assert "grupo" in msg.lower()
    assert "meu-time" not in {t.name for t in CanvasWindow._team_templates(w)}


def test_save_template_sem_nome_recusa(tmp_path):
    w = _make_win(tmp_path)
    staging = _valid_staging(name="")
    ok, msg = CanvasWindow._save_team_from_staging(w, staging, None)
    assert not ok
    assert "nome" in msg.lower()


def test_save_grupo_sem_membro_recusa(tmp_path):
    w = _make_win(tmp_path)
    staging = _valid_staging()
    staging["groups"][0]["members"] = []
    ok, msg = CanvasWindow._save_team_from_staging(w, staging, None)
    assert not ok
    assert "membro" in msg.lower()


def test_save_membro_sem_agente_recusa(tmp_path):
    w = _make_win(tmp_path)
    staging = _valid_staging()
    staging["groups"][0]["members"][0]["agent"] = ""
    ok, msg = CanvasWindow._save_team_from_staging(w, staging, None)
    assert not ok
    assert "agente" in msg.lower()


def test_save_membro_sem_instrucao_recusa(tmp_path):
    w = _make_win(tmp_path)
    staging = _valid_staging()
    staging["groups"][0]["members"][0]["instruction"] = ""
    ok, msg = CanvasWindow._save_team_from_staging(w, staging, None)
    assert not ok
    assert "instrução" in msg.lower()


def test_save_edicao_sem_rename_substitui_a_versao_anterior(tmp_path):
    w = _make_win(tmp_path)
    CanvasWindow._save_team_from_staging(w, _valid_staging(), None)
    staging2 = _valid_staging()
    staging2["description"] = "nova descricao"
    ok, _msg = CanvasWindow._save_team_from_staging(w, staging2, "meu-time")
    assert ok
    matches = [t for t in CanvasWindow._team_templates(w) if t.name == "meu-time"]
    assert len(matches) == 1
    assert matches[0].description == "nova descricao"


def test_save_edicao_com_rename_remove_o_nome_antigo(tmp_path):
    w = _make_win(tmp_path)
    CanvasWindow._save_team_from_staging(w, _valid_staging("nome-velho"), None)
    staging2 = _valid_staging("nome-novo")
    ok, _msg = CanvasWindow._save_team_from_staging(w, staging2, "nome-velho")
    assert ok
    names = {t.name for t in CanvasWindow._team_templates(w)}
    assert "nome-novo" in names
    assert "nome-velho" not in names


def test_save_duplicar_builtin_cria_copia_sem_alterar_o_original(tmp_path):
    w = _make_win(tmp_path)
    original = BUILTIN_TEAM_TEMPLATES["dev-trio"]
    staging = original.to_dict()
    staging["name"] = "dev-trio-copia"
    ok, _msg = CanvasWindow._save_team_from_staging(w, staging, None)
    assert ok
    names = {t.name for t in CanvasWindow._team_templates(w)}
    assert "dev-trio" in names and "dev-trio-copia" in names
    assert BUILTIN_TEAM_TEMPLATES["dev-trio"] == original  # built-in original intacto


def test_save_grupo_com_leader_valido_persiste(tmp_path):
    w = _make_win(tmp_path)
    staging = _valid_staging()
    staging["groups"][0]["members"].append(
        {"name": "reviewer", "agent": "codex", "instruction": "revise", "color": ""}
    )
    staging["groups"][0]["leader"] = "coder"
    ok, _msg = CanvasWindow._save_team_from_staging(w, staging, None)
    assert ok
    tpl = next(t for t in CanvasWindow._team_templates(w) if t.name == "meu-time")
    assert tpl.groups[0].leader == "coder"
