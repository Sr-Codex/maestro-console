"""Sentinela de crash: dirty-flag no `ui_state` pra distinguir fechamento limpo de crash.

Padrão clássico de *recovery* (bancos/editores): grava "sujo" no boot e limpa no
shutdown limpo; se no próximo boot a flag ainda está suja, o run anterior **crashou**
(o handler de shutdown não chegou a rodar). Gi-free (só usa `Store`) → testável no
`.venv`. Base da detecção de nós órfãos — ver `docs/25` §4-R1 (plano) e ADR-25.

Durabilidade: o `Store` é SQLite WAL e `set_ui` commita, então a flag suja sobrevive a
crash de processo; só power-loss do SO arriscaria a última escrita — que é justamente o
crash que se quer detectar.
"""

from __future__ import annotations

KEY = "dirty_run"


def check_and_arm(store) -> bool:
    """Retorna True se o run ANTERIOR não fechou limpo (crash), e re-arma a flag p/ ESTE run.

    Lê o estado gravado (sujo = o run anterior crashou, pois não passou por `disarm`),
    depois grava "sujo" para o run atual. Chamar UMA vez no boot, logo após abrir o Store.
    """
    was_dirty = bool(store.get_ui(KEY))
    store.set_ui(KEY, "1")
    return was_dirty


def disarm(store) -> None:
    """Marca fechamento limpo (limpa a flag). Chamar no shutdown limpo (inclui SIGTERM/SIGHUP)."""
    store.delete_ui(KEY)
