"""Registro de workspaces/projetos — multi-projeto (Fase C). gi-free, testável.

Cada workspace = nome + diretório do projeto + estado ISOLADO (DB próprio). Um JSON
global (`<base>/workspaces.json`) guarda a lista e o atual. Trocar de workspace =
relançar o app apontando para ele.

O workspace **default** reusa o DB legado (`<base>/maestro.db`) para preservar o
estado já existente do usuário; os demais ficam em `<base>/ws/<nome>/maestro.db`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_SAFE_NAME = re.compile(r"^[A-Za-z0-9 _.-]{1,40}$")
DEFAULT = "default"


@dataclass(frozen=True)
class Workspace:
    name: str
    project_dir: str


class WorkspaceRegistry:
    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir)
        self._file = self.base / "workspaces.json"

    def _load(self) -> dict:
        try:
            d = json.loads(self._file.read_text(encoding="utf-8"))
            if isinstance(d, dict) and isinstance(d.get("workspaces"), dict):
                d.setdefault("current", DEFAULT)
                return d
        except (OSError, json.JSONDecodeError):
            pass
        return {"workspaces": {}, "current": DEFAULT}

    def _save(self, data: dict) -> None:
        self.base.mkdir(parents=True, exist_ok=True)
        tmp = self._file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._file)

    def ensure_default(self, project_dir: str | Path) -> None:
        """Garante que o workspace 'default' existe (estado legado vira o default)."""
        d = self._load()
        if DEFAULT not in d["workspaces"]:
            d["workspaces"][DEFAULT] = {"project_dir": str(project_dir)}
            self._save(d)

    def list(self) -> list[Workspace]:
        d = self._load()
        return [
            Workspace(n, w.get("project_dir", "")) for n, w in sorted(d["workspaces"].items())
        ]

    def current(self) -> str:
        return self._load().get("current", DEFAULT)

    def get(self, name: str) -> Workspace | None:
        w = self._load()["workspaces"].get(name)
        return Workspace(name, w.get("project_dir", "")) if w else None

    def add(self, name: str, project_dir: str | Path) -> Workspace:
        if not _SAFE_NAME.match(name or ""):
            raise ValueError(f"nome de workspace inválido: {name!r}")
        d = self._load()
        d["workspaces"][name] = {"project_dir": str(project_dir)}
        self._save(d)
        return Workspace(name, str(project_dir))

    def set_current(self, name: str) -> None:
        d = self._load()
        if name not in d["workspaces"]:
            raise ValueError(f"workspace desconhecido: {name}")
        d["current"] = name
        self._save(d)

    def db_path(self, name: str) -> Path:
        """DB isolado do workspace. 'default' reusa o DB legado (preserva o estado)."""
        if name == DEFAULT:
            return self.base / "maestro.db"
        return self.base / "ws" / name / "maestro.db"
