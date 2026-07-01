"""Team Templates — organizações inteiras materializadas de uma vez (Fase A).

Um `TeamTemplate` agrupa `GroupSpec`s; cada `GroupSpec` agrupa `AgentSpec`s (= `Role`,
reuso direto de `engine/teams.py` — ver docs/14-plano-orquestracao-equipe.md §3).
Persistência espelha `roles.py:save_role_library`/`load_role_library` (JSON atômico,
builtins como semente). Suporta placeholders (`{projeto}` etc.) nos campos de texto.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path

from .teams import Role

# AgentSpec = Role (mesmos campos: name, agent, instruction, color) — sem wrapper novo.
AgentSpec = Role


@dataclass(frozen=True)
class GroupSpec:
    name: str
    members: list[AgentSpec] = field(default_factory=list)
    color: str = ""
    # Nome do papel líder do grupo. SÓ schema no v1 — sem comportamento de delegate-mode
    # ainda (evita migration de dado depois; ver docs/14 §2.1/§7).
    leader: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "color": self.color,
            "leader": self.leader,
            "members": [m.to_dict() for m in self.members],
        }

    @classmethod
    def from_dict(cls, d: dict) -> GroupSpec:
        return cls(
            name=d["name"],
            color=d.get("color", ""),
            leader=d.get("leader"),
            members=[Role.from_dict(m) for m in d.get("members", [])],
        )


@dataclass(frozen=True)
class TeamTemplate:
    name: str
    groups: list[GroupSpec] = field(default_factory=list)
    description: str = ""
    manager: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "manager": self.manager,
            "groups": [g.to_dict() for g in self.groups],
        }

    @classmethod
    def from_dict(cls, d: dict) -> TeamTemplate:
        return cls(
            name=d["name"],
            description=d.get("description", ""),
            manager=d.get("manager"),
            groups=[GroupSpec.from_dict(g) for g in d.get("groups", [])],
        )

    @property
    def total_members(self) -> int:
        return sum(len(g.members) for g in self.groups)


class TeamTemplateValidationError(ValueError):
    """TeamTemplate inválido (nome/grupos/membros)."""


def validate_team_template(template: TeamTemplate) -> None:
    if not template.name.strip():
        raise TeamTemplateValidationError("nome do template é obrigatório")
    if not template.groups:
        raise TeamTemplateValidationError("template precisa de ao menos 1 grupo")
    for g in template.groups:
        if not g.name.strip():
            raise TeamTemplateValidationError("grupo sem nome")
        if not g.members:
            raise TeamTemplateValidationError(f"grupo {g.name!r} precisa de ao menos 1 membro")
        for m in g.members:
            if not m.name.strip():
                raise TeamTemplateValidationError(f"grupo {g.name!r} tem papel sem nome")
            if not m.agent.strip():
                raise TeamTemplateValidationError(f"papel {m.name!r} sem agente")
            if not m.instruction.strip():
                raise TeamTemplateValidationError(f"papel {m.name!r} sem instrução")


# -- Placeholders (`{projeto}` etc.) — chave ausente NÃO quebra (fica literal) --
class _SafeDict(dict):
    def __missing__(self, key):  # noqa: D105 - comportamento óbvio pelo nome
        return "{" + key + "}"


def _interpolate(text: str, values: dict) -> str:
    if not text or "{" not in text:
        return text
    return text.format_map(_SafeDict(values))


_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def placeholder_names(template: TeamTemplate) -> list[str]:
    """Nomes únicos de placeholder (`{projeto}` -> `projeto`) nos campos de texto do
    template, na ordem em que aparecem — usado pelo dialog (Fase A) e pela validação (Fase B)."""
    seen: dict[str, None] = {}
    texts = [template.description]
    for g in template.groups:
        texts.append(g.name)
        for m in g.members:
            texts.append(m.name)
            texts.append(m.instruction)
    for text in texts:
        for match in _PLACEHOLDER_RE.finditer(text or ""):
            seen.setdefault(match.group(1), None)
    return list(seen)


def render_team_template(template: TeamTemplate, **values) -> TeamTemplate:
    """Aplica placeholders nos campos de texto (nome/instrução/descrição). Não valida —
    chame `validate_team_template` no resultado se for materializar."""
    groups = []
    for g in template.groups:
        members = [
            replace(
                m,
                name=_interpolate(m.name, values),
                instruction=_interpolate(m.instruction, values),
            )
            for m in g.members
        ]
        groups.append(replace(g, name=_interpolate(g.name, values), members=members))
    return replace(template, description=_interpolate(template.description, values), groups=groups)


BUILTIN_TEAM_TEMPLATES: dict[str, TeamTemplate] = {
    "dev-trio": TeamTemplate(
        name="dev-trio",
        description="Time enxuto de desenvolvimento: codar, revisar, testar.",
        groups=[
            GroupSpec(
                name="Dev",
                leader="coder",
                members=[
                    Role(
                        "coder",
                        "claude",
                        "Implemente a tarefa. result objetivo; artefatos por caminho.",
                    ),
                    Role(
                        "reviewer",
                        "codex",
                        "Revise o resultado anterior. Aponte problemas ou aprove (DONE).",
                    ),
                    Role(
                        "qe",
                        "codex",
                        "Escreva/rode testes da tarefa. Aponte falhas ou aprove (DONE).",
                    ),
                ],
            ),
        ],
    ),
    "equipe-projeto": TeamTemplate(
        name="equipe-projeto",
        description="Equipe de domínio para o projeto {projeto}, com arquiteto, dev e QE.",
        groups=[
            GroupSpec(
                name="Equipe {projeto}",
                leader="arquiteto",
                members=[
                    Role(
                        "arquiteto",
                        "claude",
                        "Arquiteto do projeto {projeto}. Decide desenho técnico; result objetivo.",
                    ),
                    Role(
                        "dev",
                        "claude",
                        "Desenvolvedor do {projeto}. Implementa conforme o arquiteto; "
                        "artefatos por caminho.",
                    ),
                    Role(
                        "qe",
                        "codex",
                        "QE do {projeto}. Testa e aponta falhas ou aprova (DONE).",
                    ),
                ],
            ),
        ],
    ),
}


def default_team_templates_path() -> Path:
    return Path.home() / ".config" / "maestro-console" / "team_templates.json"


def load_team_templates(path: str | Path) -> list[TeamTemplate]:
    """Templates salvos (JSON). Se o arquivo não existe/é inválido, devolve os built-in
    (semente) — mesmo padrão de `roles.py:load_role_library`."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        templates = [TeamTemplate.from_dict(d) for d in data if d.get("name")]
        return templates or list(BUILTIN_TEAM_TEMPLATES.values())
    except (OSError, ValueError):
        return list(BUILTIN_TEAM_TEMPLATES.values())


def save_team_templates(path: str | Path, templates: list[TeamTemplate]) -> None:
    """Salva de forma ATÔMICA (temp + os.replace) — um crash no meio não trunca o arquivo
    nem apaga os templates custom."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps([t.to_dict() for t in templates], ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".team-templates-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, p)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
