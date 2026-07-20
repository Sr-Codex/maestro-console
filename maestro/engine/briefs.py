"""Briefing por grupo — bloco marcado em CLAUDE.md/AGENTS.md do workspace (docs/30).

O "quadro de avisos" do grupo: objetivo atual + brief (decisões/contexto) editados SÓ pelo
host, entregues aos agentes pelo MESMO trilho dos papéis (`roles.install_role_block`) — bloco
marcado no CLAUDE.md/AGENTS.md do workspace isolado, que o CLI lê sozinho no start (terminal
vivo, headless com cwd=workspace, reattach/--resume). Fonte da verdade é o Store; o arquivo é
ESPELHO descartável, re-carimbado a cada start e NUNCA lido de volta (emenda Fable E3).

gi-free, testável no .venv.
"""

from __future__ import annotations

import re
from pathlib import Path

from .safe_fs import safe_read_text, safe_write_text

# Caps validados (docs/30 §10; evidência Chroma "Context Rot" + guia CLAUDE.md "concise")
BRIEF_MAX = 1000
GOAL_MAX = 80

BRIEF_BLOCK_BEGIN = "<!-- maestro-brief:begin -->"
BRIEF_BLOCK_END = "<!-- maestro-brief:end -->"

# Unicode INVISÍVEL que esconde instrução de LLM em arquivo de regras (ataque "Rules File
# Backdoor", Pillar Security 2025 / CSA 2026): zero-width (200B-200F, 2060-2064, FEFF),
# controles bidi (202A-202E, 2066-2069), Unicode tags (E0000-E007F), soft hyphen (00AD).
_INVISIBLE = re.compile(
    "[\u00ad\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff"
    "\U000e0000-\U000e007f]"
)
# Controles ASCII exceto \n e \t (colar de terminal pode trazer ESC etc.)
_CONTROLS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def sanitize_brief(text: str | None, cap: int = BRIEF_MAX) -> str:
    """Sanitiza texto de brief/objetivo vindo da UI: remove Unicode invisível + controles,
    normaliza fim de linha e aplica o cap. Roda SÓ no save do host (o arquivo espelhado
    nunca volta pra cá — sem caminho de re-ingestão)."""
    t = _INVISIBLE.sub("", text or "")
    t = _CONTROLS.sub("", t.replace("\r\n", "\n").replace("\r", "\n"))
    return t.strip()[:cap]


def brief_block_text(goal: str, brief: str, edited: str = "") -> str:
    """Bloco MARCADO do briefing (a IA lê no start). Inclui a data da edição — o agente
    sabe a IDADE do contexto que recebeu (mitiga brief obsoleto, docs/30 §6)."""
    lines = [BRIEF_BLOCK_BEGIN, "## Briefing do grupo (definido pelo humano)"]
    if goal:
        lines.append(f"\n**Objetivo atual:** {goal}")
    if brief:
        lines.append(f"\n{brief}")
    if edited:
        lines.append(f"\n_(editado em {edited})_")
    lines.append(BRIEF_BLOCK_END)
    return "\n".join(lines)


def _replace_block(existing: str, block: str) -> str:
    """Substitui o bloco de brief marcado (ou anexa) — NÃO sobrescreve o resto do arquivo
    (mesma mecânica do bloco de role; blocos coexistem)."""
    if BRIEF_BLOCK_BEGIN in existing and BRIEF_BLOCK_END in existing:
        pre = existing.split(BRIEF_BLOCK_BEGIN, 1)[0].rstrip("\n")
        post = existing.split(BRIEF_BLOCK_END, 1)[1].lstrip("\n")
        joined = f"{pre}\n\n{block}\n"
        return f"{joined}\n{post}" if post else joined
    sep = "" if not existing or existing.endswith("\n") else "\n"
    return f"{existing}{sep}\n{block}\n"


def install_brief_block(target_dir: str | Path, goal: str, brief: str, edited: str = "") -> None:
    """Insere/atualiza o bloco de brief em CLAUDE.md e AGENTS.md de `target_dir` (idempotente;
    re-instalar SUBSTITUI o bloco — o re-carimbo a cada start desfaz rabisco de agente)."""
    d = Path(target_dir)
    d.mkdir(parents=True, exist_ok=True)
    block = brief_block_text(goal, brief, edited)
    for fname in ("CLAUDE.md", "AGENTS.md"):
        p = d / fname
        # S2 (review docs/33): o workspace é RW pro agente; um CLAUDE.md trocado por symlink
        # faria o host escrever fora do sandbox. safe_* recusa seguir symlink e exige contenção.
        existing = safe_read_text(p)
        safe_write_text(p, _replace_block(existing, block), within=d)


def remove_brief_block(target_dir: str | Path) -> None:
    """Remove o bloco de brief marcado (nó saiu do grupo / grupo apagado) — preserva o resto."""
    d = Path(target_dir)
    for fname in ("CLAUDE.md", "AGENTS.md"):
        p = d / fname
        existing = safe_read_text(p)  # symlink → "" (não segue)
        if not existing:
            continue
        if BRIEF_BLOCK_BEGIN in existing and BRIEF_BLOCK_END in existing:
            pre = existing.split(BRIEF_BLOCK_BEGIN, 1)[0].rstrip("\n")
            post = existing.split(BRIEF_BLOCK_END, 1)[1].lstrip("\n")
            safe_write_text(p, f"{pre}\n{post}" if post else f"{pre}\n", within=d)
