"""Grupos/áreas no canvas (C2) — retângulo rotulado atrás dos nós, p/ organizar.

Persistido na tabela `groups`. Mesma forma do Notes: dataclass + CRUD sobre o Store.
A semântica "arrastar o grupo move os nós contidos junto" mora na UI (canvas).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from .state.store import Store


@dataclass
class Group:
    id: str
    title: str
    color: str
    x: float
    y: float
    w: float
    h: float


class Groups:
    """CRUD de grupos sobre o Store."""

    def __init__(self, store: Store):
        self._store = store

    def create(
        self,
        title: str = "Grupo",
        color: str = "blue",
        x: float = 0.0,
        y: float = 0.0,
        w: float = 600.0,
        h: float = 360.0,
    ) -> Group:
        g = Group(id=str(uuid.uuid4()), title=title, color=color, x=x, y=y, w=w, h=h)
        self.save(g)
        return g

    @staticmethod
    def _row_to_group(row) -> Group:
        return Group(
            id=row["id"],
            title=row["title"],
            color=row["color"],
            x=row["x"],
            y=row["y"],
            w=row["w"],
            h=row["h"],
        )

    def get(self, group_id: str) -> Group | None:
        row = self._store.get_group(group_id)
        return self._row_to_group(row) if row is not None else None

    def list(self) -> list[Group]:
        return [self._row_to_group(r) for r in self._store.list_groups()]

    def save(self, g: Group) -> None:
        self._store.upsert_group(g.id, g.title, g.color, g.x, g.y, g.w, g.h)

    def set_rect(self, group_id: str, x: float, y: float, w: float, h: float) -> None:
        g = self.get(group_id)
        if g is not None:
            g.x, g.y, g.w, g.h = x, y, w, h
            self.save(g)

    def delete(self, group_id: str) -> None:
        self._store.remove_group(group_id)
