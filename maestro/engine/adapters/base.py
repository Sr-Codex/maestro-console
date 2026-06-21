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
    # Diretórios rw que o sandbox deve liberar (config/sessão/auth do agente),
    # ex.: ~/.claude, ~/.codex — necessários para auth e --resume.
    rw_paths: list[str] = field(default_factory=list)
    stdin: str = "devnull"
    # Onde o prompt entra no argv (quirk por CLI):
    #   "after_cmd" -> logo após o cmd base (ex.: claude -p PROMPT ...flags),
    #                  evita que flags nargs (--allowedTools) engulam o prompt;
    #   "last"      -> no fim (ex.: codex exec ...flags PROMPT).
    prompt_position: str = "last"

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
            rw_paths=list(h.get("rw_paths", [])),
            stdin=h.get("stdin", "devnull"),
            prompt_position=h.get("prompt_position", "last"),
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
            base = _subst(self.session_resume_cmd, id=session_id or "")
        else:
            base = list(self.cmd)
            if session_id and self.session_mode == "flag":
                tmpl = self.session_resume if resume else self.session_set
                base += _subst(tmpl, id=session_id)
        flags = list(self.output_args)
        if workspace:
            flags += _subst(self.permission_args, workspace=workspace)
            flags += list(self.allowed_tools_args)
        # Posição do prompt evita que flags nargs (ex.: --allowedTools) o engulam.
        if self.prompt_position == "after_cmd":
            return base + [prompt] + flags
        return base + flags + [prompt]


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
