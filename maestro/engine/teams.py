"""Teams & Roles — equipes reutilizáveis de agentes (V2-S1).

Um Team é uma cadeia ordenada de Roles; cada Role amarra um papel (coder,
reviewer, planner…) a um agente e a uma instrução técnica curta. Persistido na
tabela `teams` do Store; built-ins disponíveis mesmo sem salvar.
"""

from __future__ import annotations

from dataclasses import dataclass

from .state.store import Store


@dataclass(frozen=True)
class Role:
    name: str  # papel: coder, reviewer, planner...
    agent: str  # agente que executa (ex.: claude, codex)
    instruction: str  # instrução técnica CURTA do papel

    def to_dict(self) -> dict:
        return {"name": self.name, "agent": self.agent, "instruction": self.instruction}

    @classmethod
    def from_dict(cls, d: dict) -> Role:
        return cls(name=d["name"], agent=d["agent"], instruction=d["instruction"])


@dataclass(frozen=True)
class Team:
    name: str
    roles: list[Role]

    @property
    def route(self) -> str:
        """Rota compacta: coder(claude) → reviewer(codex)."""
        return " → ".join(f"{r.name}({r.agent})" for r in self.roles)

    def to_dicts(self) -> list[dict]:
        return [r.to_dict() for r in self.roles]

    @classmethod
    def from_dicts(cls, name: str, roles: list[dict]) -> Team:
        return cls(name=name, roles=[Role.from_dict(r) for r in roles])


BUILTIN_TEAMS: dict[str, Team] = {
    "coder-reviewer": Team(
        "coder-reviewer",
        [
            Role("coder", "claude", "Implemente a tarefa. result objetivo; artefatos por caminho."),
            Role(
                "reviewer",
                "codex",
                "Revise o resultado anterior. Aponte problemas ou aprove (DONE).",
            ),
        ],
    ),
    "planner-coder-reviewer": Team(
        "planner-coder-reviewer",
        [
            Role(
                "planner", "claude", "Planeje passos curtos para a tarefa. result = plano objetivo."
            ),
            Role("coder", "claude", "Implemente conforme o plano anterior. result objetivo."),
            Role("reviewer", "codex", "Revise a implementação. Aponte problemas ou aprove (DONE)."),
        ],
    ),
}


class TeamValidationError(ValueError):
    """Team inválido (nome/papéis/agentes/instruções)."""


def validate_team(team: Team) -> None:
    if not team.name.strip():
        raise TeamValidationError("nome do team é obrigatório")
    if not team.roles:
        raise TeamValidationError("team precisa de ao menos 1 papel")
    for r in team.roles:
        if not r.name.strip():
            raise TeamValidationError("papel sem nome")
        if not r.agent.strip():
            raise TeamValidationError(f"papel {r.name!r} sem agente")
        if not r.instruction.strip():
            raise TeamValidationError(f"papel {r.name!r} sem instrução")


class Teams:
    """Gerência de equipes (built-ins + persistidas)."""

    def __init__(self, store: Store):
        self._store = store

    def exists(self, name: str) -> bool:
        return name in self.list()

    def save(self, team: Team) -> None:
        validate_team(team)
        self._store.save_team(team.name, team.to_dicts())

    def duplicate(self, src: str, new_name: str) -> Team:
        src_team = self.get(src)
        if src_team is None:
            raise TeamValidationError(f"team de origem {src!r} não existe")
        if self.exists(new_name):
            raise TeamValidationError(f"team {new_name!r} já existe")
        dup = Team(new_name, list(src_team.roles))
        self.save(dup)
        return dup

    def get(self, name: str) -> Team | None:
        roles = self._store.get_team(name)
        if roles is not None:
            return Team.from_dicts(name, roles)
        return BUILTIN_TEAMS.get(name)

    def list(self) -> list[str]:
        return sorted(set(BUILTIN_TEAMS) | set(self._store.list_teams()))

    def delete(self, name: str) -> None:
        self._store.delete_team(name)
