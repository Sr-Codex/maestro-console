"""Lógica pura de vigilância do Maestro mode (ADR-17, Etapa 4) — sem GTK, testável.

- ``has_cycle``: ciclo no grafo NÃO-direcionado de cabos (agentes que se referenciam em
  laço → risco de ping-pong de asks). Surfaceado no HUD e na auditoria.
- ``spawn_anomaly``: rajada de recrutamentos BLOQUEADOS na janela = manager em loop de
  runaway (martelando o cap) → gatilho para o kill-switch AUTOMÁTICO (tira o trail do
  modo passivo, como a pesquisa exigiu).
"""

from __future__ import annotations


def has_cycle(edges: list[tuple]) -> bool:
    """True se o grafo não-direcionado dos cabos tem ciclo (ou self-loop). Union-find."""
    parent: dict = {}

    def find(x):
        parent.setdefault(x, x)
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:  # path-compression
            parent[x], x = root, parent[x]
        return root

    for a, b in edges:
        if a == b:
            return True  # self-loop
        ra, rb = find(a), find(b)
        if ra == rb:
            return True  # já conectados → este cabo fecha um ciclo
        parent[ra] = rb
    return False


# eventos de ABUSO contados pela anomalia (5d: não só recruit — TODOS os comandos mutadores)
ABUSE_EVENTS = frozenset({"recruit_blocked", "rate_blocked", "recruit_denied"})


def spawn_anomaly(events: list[dict], *, now: float, window: float = 30.0,
                  blocked_threshold: int = 8) -> bool:
    """True se houve >= ``blocked_threshold`` eventos de ABUSO (recruit/rate bloqueado, recruit
    negado) nos últimos ``window`` s — assinatura de um manager em loop de runaway por QUALQUER
    comando mutador (wire/dismiss/reassign também geram rate_blocked, não só recruit)."""
    n = 0
    for e in events:
        if e.get("event") in ABUSE_EVENTS and now - float(e.get("ts", 0)) <= window:
            n += 1
    return n >= blocked_threshold
