"""Papéis ricos — role.json + CLAUDE.md/AGENTS.md por workspace (V9-S1).

Maestri-like: ao rodar um agente num papel, o console materializa a identidade do
papel no diretório de trabalho — um **role.json** portável (name, agent, color,
prompt) + **CLAUDE.md/AGENTS.md** com a instrução (claude lê CLAUDE.md; codex lê
AGENTS.md). Estende o Role existente (decisão de foundation: Opção A).
"""

from __future__ import annotations

import json
from pathlib import Path

from .safe_fs import safe_read_text, safe_write_text
from .teams import Role


def role_badge(role: Role) -> str:
    """Cor de badge efetiva do papel (atalho p/ a UI)."""
    return role.badge()


def agent_badges(team) -> dict[str, str]:
    """Mapa agente -> cor do badge, a partir dos papéis de um team.

    Se um agente tem mais de um papel no team, o PRIMEIRO papel vence (a ordem da
    rota). `team` pode ser None -> {}.
    """
    badges: dict[str, str] = {}
    if team is None:
        return badges
    for r in team.roles:
        badges.setdefault(r.agent, r.badge())
    return badges


def role_sidecar(role: Role) -> dict:
    """Conteúdo portável do role.json (name, agent, color, prompt)."""
    return {
        "name": role.name,
        "agent": role.agent,
        "color": role.badge(),
        "prompt": role.instruction,
    }


def _instruction_md(role: Role) -> str:
    return f"# Papel: {role.name}\n\nAgente: {role.agent}\n\n{role.instruction}\n"


def write_role_files(workspace: str | Path, role: Role) -> dict[str, str]:
    """Escreve role.json + CLAUDE.md + AGENTS.md no workspace. Retorna os caminhos."""
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    # S2 (review docs/33): ws é RW pro agente — safe_write_text recusa seguir symlink (arquivo
    # ou pai) que faria o host escrever fora do sandbox.
    rj = ws / "role.json"
    safe_write_text(rj, json.dumps(role_sidecar(role), ensure_ascii=False, indent=2) + "\n",
                    within=ws)
    paths["role.json"] = str(rj)

    md = _instruction_md(role)
    for fname in ("CLAUDE.md", "AGENTS.md"):
        p = ws / fname
        safe_write_text(p, md, within=ws)
        paths[fname] = str(p)
    return paths


# -- Fase 5: biblioteca reusável + sidecar portátil .maestri/role.json + Discover --
def role_from_sidecar(d: dict) -> Role:
    """Role a partir de um dict de sidecar (inverso de role_sidecar). Tolerante a chaves."""
    return Role(
        name=str(d.get("name", "")).strip(),
        agent=str(d.get("agent", "")),
        instruction=str(d.get("prompt", d.get("instruction", ""))),
        color=str(d.get("color", d.get("badgeColor", ""))),
    )


def builtin_roles() -> list[Role]:
    """Papéis-semente da biblioteca (dos teams built-in), deduplicados por nome."""
    from .teams import BUILTIN_TEAMS

    seen: dict[str, Role] = {}
    for team in BUILTIN_TEAMS.values():
        for r in team.roles:
            seen.setdefault(r.name, r)  # 1º papel com o nome vence
    return list(seen.values())


def load_role_library(path: str | Path) -> list[Role]:
    """Biblioteca de papéis (JSON). Se o arquivo não existe, devolve os built-in."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        roles = [role_from_sidecar(d) for d in data if d.get("name")]
        return roles or builtin_roles()
    except (OSError, ValueError):
        return builtin_roles()


def save_role_library(path: str | Path, roles: list[Role]) -> None:
    """Salva a biblioteca de forma ATÔMICA (temp + os.replace) — um crash no meio não trunca
    o arquivo nem apaga os papéis custom (H2)."""
    import os
    import tempfile

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps([role_sidecar(r) for r in roles], ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".roles-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, p)  # rename atômico: o leitor vê o arquivo antigo OU o novo, nunca metade
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_role_sidecar(directory: str | Path, role: Role) -> str:
    """Escreve o sidecar PORTÁTIL `.maestri/role.json` no diretório (cwd do terminal)."""
    base = Path(directory)
    d = base / ".maestri"
    d.mkdir(parents=True, exist_ok=True)
    rj = d / "role.json"
    # within=base: se `.maestri` (pai) virou symlink pra fora, a contenção recusa (S2).
    safe_write_text(rj, json.dumps(role_sidecar(role), ensure_ascii=False, indent=2) + "\n",
                    within=base)
    return str(rj)


ROLE_BLOCK_BEGIN = "<!-- maestro-role:begin -->"
ROLE_BLOCK_END = "<!-- maestro-role:end -->"


def role_block_text(role: Role) -> str:
    """Bloco MARCADO com o papel — inserido no CLAUDE.md/AGENTS.md (a IA lê no start)."""
    return (
        f"{ROLE_BLOCK_BEGIN}\n"
        f"## Seu papel: {role.name}\n\n"
        f"{role.instruction}\n"
        f"{ROLE_BLOCK_END}"
    )


def _replace_block(existing: str, block: str) -> str:
    """Substitui o bloco marcado (ou anexa, se não existe) — NÃO sobrescreve o resto."""
    if ROLE_BLOCK_BEGIN in existing and ROLE_BLOCK_END in existing:
        pre = existing.split(ROLE_BLOCK_BEGIN, 1)[0].rstrip("\n")
        post = existing.split(ROLE_BLOCK_END, 1)[1].lstrip("\n")
        joined = f"{pre}\n\n{block}\n"
        return f"{joined}\n{post}" if post else joined
    sep = "" if not existing or existing.endswith("\n") else "\n"
    return f"{existing}{sep}\n{block}\n"


def install_role_block(target_dir: str | Path, role: Role) -> None:
    """Insere/atualiza o bloco de role em CLAUDE.md e AGENTS.md de `target_dir` (append seguro)."""
    d = Path(target_dir)
    d.mkdir(parents=True, exist_ok=True)
    block = role_block_text(role)
    for fname in ("CLAUDE.md", "AGENTS.md"):
        p = d / fname
        existing = safe_read_text(p, within=d)  # S2: symlink → "" (não segue)
        safe_write_text(p, _replace_block(existing, block), within=d)


def remove_role_block(target_dir: str | Path) -> None:
    """Remove o bloco de role marcado (desatribuir) — preserva o resto do arquivo."""
    d = Path(target_dir)
    for fname in ("CLAUDE.md", "AGENTS.md"):
        p = d / fname
        existing = safe_read_text(p, within=d)  # S2: symlink → "" (não segue; o irmão faltava)
        if not existing:
            continue
        if ROLE_BLOCK_BEGIN in existing and ROLE_BLOCK_END in existing:
            pre = existing.split(ROLE_BLOCK_BEGIN, 1)[0].rstrip("\n")
            post = existing.split(ROLE_BLOCK_END, 1)[1].lstrip("\n")
            safe_write_text(p, f"{pre}\n{post}" if post else f"{pre}\n", within=d)


def discover_roles(cwd: str | Path) -> list[Role]:
    """Varre o cwd por papéis: `role.json`, `.maestri/role.json` e `*/.maestri/role.json`
    (branches de colegas). Deduplicado por nome."""
    base = Path(cwd)
    candidates = [base / "role.json", base / ".maestri" / "role.json"]
    try:
        for sub in base.iterdir():
            if sub.is_dir():
                candidates.append(sub / ".maestri" / "role.json")
    except OSError:
        pass
    found: dict[str, Role] = {}
    for c in candidates:
        try:
            if c.is_file():
                r = role_from_sidecar(json.loads(c.read_text(encoding="utf-8")))
                if r.name:
                    found.setdefault(r.name, r)
        except (OSError, ValueError):
            continue
    return list(found.values())
