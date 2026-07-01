"""Testes de Team Templates (Fase A — orquestração de equipe, docs/14 §5.A1)."""

import pytest

from maestro.engine.team_templates import (
    BUILTIN_TEAM_TEMPLATES,
    GroupSpec,
    TeamTemplate,
    TeamTemplateValidationError,
    load_team_templates,
    placeholder_names,
    render_team_template,
    save_team_templates,
    validate_team_template,
)
from maestro.engine.teams import Role


def _simple_template(name="t1") -> TeamTemplate:
    return TeamTemplate(
        name=name,
        description="desc",
        groups=[
            GroupSpec(
                name="Grupo A",
                color="blue",
                leader="coder",
                members=[
                    Role("coder", "claude", "implemente"),
                    Role("reviewer", "codex", "revise"),
                ],
            )
        ],
    )


def test_groupspec_roundtrip_com_leader():
    g = GroupSpec(name="G", color="red", leader="coder", members=[Role("coder", "claude", "x")])
    d = g.to_dict()
    assert d["leader"] == "coder"
    assert GroupSpec.from_dict(d) == g


def test_groupspec_from_dict_sem_leader_retrocompativel():
    member = {"name": "coder", "agent": "claude", "instruction": "x"}
    g = GroupSpec.from_dict({"name": "G", "members": [member]})
    assert g.leader is None


def test_team_template_roundtrip():
    t = _simple_template()
    d = t.to_dict()
    got = TeamTemplate.from_dict(d)
    assert got == t
    assert got.total_members == 2


def test_validate_team_template_ok():
    validate_team_template(_simple_template())  # não levanta


@pytest.mark.parametrize(
    "template",
    [
        TeamTemplate(name="", groups=[GroupSpec(name="G", members=[Role("c", "claude", "x")])]),
        TeamTemplate(name="t", groups=[]),
        TeamTemplate(name="t", groups=[GroupSpec(name="", members=[Role("c", "claude", "x")])]),
        TeamTemplate(name="t", groups=[GroupSpec(name="G", members=[])]),
        TeamTemplate(name="t", groups=[GroupSpec(name="G", members=[Role("", "claude", "x")])]),
        TeamTemplate(name="t", groups=[GroupSpec(name="G", members=[Role("c", "", "x")])]),
        TeamTemplate(name="t", groups=[GroupSpec(name="G", members=[Role("c", "claude", "")])]),
    ],
)
def test_validate_team_template_rejeita_invalido(template):
    with pytest.raises(TeamTemplateValidationError):
        validate_team_template(template)


def test_builtins_validos():
    for tpl in BUILTIN_TEAM_TEMPLATES.values():
        validate_team_template(tpl)


def test_builtin_equipe_projeto_tem_placeholder():
    tpl = BUILTIN_TEAM_TEMPLATES["equipe-projeto"]
    assert "{projeto}" in tpl.description
    assert any("{projeto}" in g.name for g in tpl.groups)


def test_render_team_template_interpola_placeholders():
    tpl = BUILTIN_TEAM_TEMPLATES["equipe-projeto"]
    rendered = render_team_template(tpl, projeto="n8n")
    assert "{projeto}" not in rendered.description
    assert rendered.description == "Equipe de domínio para o projeto n8n, com arquiteto, dev e QE."
    assert rendered.groups[0].name == "Equipe n8n"
    assert "n8n" in rendered.groups[0].members[0].instruction
    validate_team_template(rendered)


def test_render_team_template_chave_ausente_nao_quebra():
    tpl = BUILTIN_TEAM_TEMPLATES["equipe-projeto"]
    rendered = render_team_template(tpl)  # sem kwargs
    assert "{projeto}" in rendered.description  # fica literal, não levanta KeyError


def test_render_team_template_sem_placeholder_eh_noop():
    tpl = _simple_template()
    rendered = render_team_template(tpl, projeto="x")
    assert rendered == tpl


def test_save_load_atomico(tmp_path):
    path = tmp_path / "team_templates.json"
    templates = [_simple_template("a"), _simple_template("b")]
    save_team_templates(path, templates)
    loaded = load_team_templates(path)
    assert {t.name for t in loaded} == {"a", "b"}
    assert loaded[0].groups[0].leader == "coder"


def test_load_team_templates_arquivo_ausente_devolve_builtins(tmp_path):
    loaded = load_team_templates(tmp_path / "nope.json")
    assert {t.name for t in loaded} == set(BUILTIN_TEAM_TEMPLATES)


def test_placeholder_names_detecta_e_dedup():
    tpl = BUILTIN_TEAM_TEMPLATES["equipe-projeto"]
    assert placeholder_names(tpl) == ["projeto"]  # aparece várias vezes, mas só 1x na lista


def test_placeholder_names_vazio_quando_sem_chave():
    assert placeholder_names(_simple_template()) == []


def test_load_team_templates_arquivo_invalido_devolve_builtins(tmp_path):
    path = tmp_path / "team_templates.json"
    path.write_text("{ nao é uma lista json valida ][", encoding="utf-8")
    loaded = load_team_templates(path)
    assert {t.name for t in loaded} == set(BUILTIN_TEAM_TEMPLATES)
