"""Agent Adapter — perfis declarativos por CLI (E2-S1 / FR6).

Um agente é descrito por um arquivo ``.toml`` (sem código no core): comando
headless, modo de sessão, args de saída e de permissão. Adicionar um agente =
adicionar um ``.toml`` (nenhuma mudança no core — NFR5).

A política de permissão e o workspace isolado são *declarados* aqui e
*aplicados* (com criação/escopo do workspace) no E2-S2; a fiação fina de
sessão fica no Session Manager (E2-S3).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ADAPTERS_DIR = Path(__file__).parent


def _subst(args: list[str], **vars: str) -> list[str]:
    out = []
    for a in args:
        for k, v in vars.items():
            a = a.replace("{" + k + "}", v)
        out.append(a)
    return out


@dataclass(frozen=True)
class AgentProfile:
    name: str
    cmd: list[str]
    session_mode: str = "flag"  # "flag" (claude) | "subcommand" (codex)
    session_set: list[str] = field(default_factory=list)
    session_resume: list[str] = field(default_factory=list)
    session_resume_cmd: list[str] = field(default_factory=list)
    output_args: list[str] = field(default_factory=list)
    permission_args: list[str] = field(default_factory=list)
    allowed_tools_args: list[str] = field(default_factory=list)
    stdin: str = "devnull"

    @classmethod
    def from_dict(cls, data: dict) -> AgentProfile:
        h = data.get("headless", {})
        sess = h.get("session", {})
        perms = h.get("permissions", {})
        return cls(
            name=data["name"],
            cmd=list(h["cmd"]),
            session_mode=sess.get("mode", "flag"),
            session_set=list(sess.get("set", [])),
            session_resume=list(sess.get("resume", [])),
            session_resume_cmd=list(sess.get("resume_cmd", [])),
            output_args=list(h.get("output_args", [])),
            permission_args=list(perms.get("args", [])),
            allowed_tools_args=list(perms.get("allowed_tools", [])),
            stdin=h.get("stdin", "devnull"),
        )

    def build_command(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        resume: bool = False,
        workspace: str | None = None,
    ) -> list[str]:
        """Monta o argv headless aplicando cmd/sessão/permissão/saída."""
        if resume and self.session_mode == "subcommand":
            argv = _subst(self.session_resume_cmd, id=session_id or "")
        else:
            argv = list(self.cmd)
            if session_id and self.session_mode == "flag":
                tmpl = self.session_resume if resume else self.session_set
                argv += _subst(tmpl, id=session_id)
        argv += list(self.output_args)
        if workspace:
            argv += _subst(self.permission_args, workspace=workspace)
            argv += list(self.allowed_tools_args)
        argv.append(prompt)
        return argv


def load_profile(path: str | Path) -> AgentProfile:
    with open(path, "rb") as f:
        return AgentProfile.from_dict(tomllib.load(f))


def load_profiles(directory: str | Path = ADAPTERS_DIR) -> dict[str, AgentProfile]:
    """Carrega todos os perfis ``*.toml`` de um diretório, indexados por nome."""
    profiles: dict[str, AgentProfile] = {}
    for p in sorted(Path(directory).glob("*.toml")):
        prof = load_profile(p)
        profiles[prof.name] = prof
    return profiles
