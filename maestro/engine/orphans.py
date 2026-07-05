"""Detecção de nós órfãos pós-crash (reattach — `docs/25` §4-R2).

Um nó-agente é **órfão-recuperável** sse: o run anterior crashou (dirty-flag, ver
`crash_flag`) ∧ é agente ∧ NÃO foi descarregado de propósito (`unloaded`) ∧ tem transcript
no disco (há sessão pra `--resume`, ver `session_capture`). Gi-free (só `CanvasModel` +
`newest_session_id`) → testável no `.venv`.

Opção A (`docs/25` §4-R2): o órfão recebe `unloaded=1` (reusa a dormência + o `_reload_node`
do unload SEM tocar na parte delicada do canvas) MAIS `orphan=1` (flag própria e persistida
que distingue crash-órfão de descarregado-de-propósito — a distinção que a revisão do Fable
exigiu). As 3 ações de recuperação (R3) limpam ambas.
"""

from __future__ import annotations

from .session_capture import newest_session_id


def detect_orphans(model, roster, crashed: bool, ws_base: str, *, home=None) -> list[str]:
    """Marca os nós órfãos no `node_cfg` e retorna os nids. No-op se não houve crash.

    Chamar no boot, DEPOIS de abrir `model`/`roster` e ANTES de construir a janela (pra o
    card nascer dormente via `_make_node_term`). `ws_base` = `<base>/workspaces`; `home`
    é injetável só para teste (produção usa `~`).
    """
    if not crashed:
        return []
    out: list[str] = []
    for spec in roster:
        nid = spec.get("nid")
        if not nid or spec.get("kind") != "agent":
            continue  # shell não tem sessão a retomar
        if model.node_cfg(nid, "unloaded"):
            continue  # descarregado de propósito → não é órfão (nada a recuperar)
        sid = newest_session_id(f"{ws_base}/{nid}", home=home)
        if not sid:
            continue  # sem transcript no disco → nada a resumir → boot normal
        model.set_node_cfg(nid, "session", sid)  # sessão a retomar (Reanexar)
        model.set_node_cfg(nid, "unloaded", "1")  # reusa dormência + _reload_node
        model.set_node_cfg(nid, "orphan", "1")  # flag distinta (label "recuperável")
        out.append(nid)
    return out
