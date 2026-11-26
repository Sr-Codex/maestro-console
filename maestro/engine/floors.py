"""Floors — ambientes de desenvolvimento isolados via git worktree (V8-S1).

Equivalente Linux das Floors do Maestri: cada floor = um **git worktree** +
branch `floor/<name>` de um repo de projeto. O worktree compartilha o object
store do repo → criação quase instantânea, disco mínimo (ideal p/ uConsole).
Agentes podem trabalhar em branches isoladas, sem conflito.

A engine não muda: floors são opt-in. O Store é a fonte de verdade do registro;
o git é a fonte de verdade do worktree em si.
"""

from __future__ import annotations

import re
import stat
from dataclasses import dataclass
from pathlib import Path

from . import agent_home
from .accounts import accounts_root
from .adapters.base import load_profiles
from .safe_git import run_git
from .state.store import Store

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


class FloorError(RuntimeError):
    """Erro ao criar/remover/consultar um floor."""


@dataclass(frozen=True)
class Floor:
    name: str
    branch: str
    path: str
    base_branch: str


def _check_name(name: str) -> str:
    if not _SAFE_NAME.match(name):
        raise FloorError(f"nome de floor inválido (apenas [A-Za-z0-9_-]): {name!r}")
    return name


def check_ref(ref: str) -> str:
    """Ref vinda de fora (CLI, registro, backup) não pode ser lida pelo git como OPÇÃO."""
    if not ref or ref.startswith("-"):
        raise FloorError(f"base inválida: {ref!r}")
    return ref


def _git(repo: Path, *args: str) -> str:
    """Roda git no repo; levanta FloorError com stderr em caso de falha."""
    res = run_git(repo, *args)
    if res.returncode != 0:
        raise FloorError(f"git {' '.join(args)} falhou: {res.stderr.strip()}")
    return res.stdout.strip()


def _profile_rw_roots() -> list[Path]:
    # ADR-31: a config dos CLIs não é mais rw (fotocópia), mas o slug do nó em
    # ~/.claude/projects é — projeto lá dentro continua recusado.
    extra = [Path(p).expanduser().resolve() for pr in load_profiles().values() for p in pr.rw_paths]
    return [*agent_home.protected_roots(), *extra]


def _refuse_under(path: Path, roots) -> None:
    real = path.resolve()
    for root in roots:
        if root == real or root in real.parents:
            raise FloorError(
                f"{path} fica em {root}, gravável por agentes — o git de lá pode estar "
                "adulterado; mova o projeto para fora dessa pasta para usar floors"
            )


def check_project(repo: str | Path) -> Path:
    """Recusa projeto em área gravável por QUALQUER agente; devolve o git-dir comum.

    Vale pra toda operação de floor, não só o run: um nó interativo monta os rw_paths do
    perfil (e o próprio workspace) sem travar `.git`, então a config dali já pode ter sido
    plantada antes. `rev-parse` só lê config — não executa nada dela.
    """
    from ..bootstrap import default_home  # import local: evita ciclo

    common = Path(_git(Path(repo), "rev-parse", "--path-format=absolute", "--git-common-dir"))
    roots = [*_profile_rw_roots(), default_home().resolve(), accounts_root().resolve()]
    _refuse_under(Path(repo), roots)
    _refuse_under(common, roots)
    return common


@dataclass(frozen=True)
class FloorGit:
    """Metadados git do floor segundo o HOST (nunca segundo a árvore do agente)."""

    git_dir: Path  # <common>/worktrees/<id>
    protect: tuple[str, ...]  # travar em somente-leitura no sandbox


def floor_git(repo: str | Path, floor: Floor) -> FloorGit:
    """Localiza os metadados do floor a partir do REPO e confere o ponteiro `<floor>/.git`.

    Falha fechado se o floor não é worktree deste repo ou se o ponteiro foi trocado: ele fica
    na árvore do agente e aponta de onde o git lê a config.
    """
    common = check_project(repo)
    pointer = Path(floor.path).resolve() / ".git"
    _refuse_under(pointer, _profile_rw_roots())  # o ancestral do floor também não pode ser rw
    entries = common / "worktrees"
    git_dir = None
    for d in sorted(entries.iterdir()) if entries.is_dir() else ():
        try:
            raw = Path((d / "gitdir").read_text(encoding="utf-8").strip())
        except OSError:
            continue
        back = d / raw  # relativo com worktree.useRelativePaths; absoluto vence o join
        if back.parent.resolve() / back.name == pointer:
            git_dir = d
            break
    if git_dir is None:
        raise FloorError(f"floor {floor.name!r} não é um worktree de {repo}")
    try:
        regular = stat.S_ISREG(pointer.lstat().st_mode)
        text = pointer.read_text(encoding="utf-8").strip() if regular else ""
    except (OSError, UnicodeDecodeError):
        text = ""
    target = text.removeprefix("gitdir:").strip()
    if not text.startswith("gitdir:") or (pointer.parent / target).resolve() != git_dir.resolve():
        raise FloorError(
            f"ponteiro .git do floor {floor.name!r} foi alterado — recusando; "
            f"confira {pointer} e rode `git worktree repair`"
        )
    protect = [str(pointer), str(common)]
    own = Path(repo).resolve() / ".git"
    if own.is_file():  # o projeto é ele mesmo um worktree/submódulo: outro ponteiro
        protect.append(str(own))
    return FloorGit(git_dir=git_dir, protect=tuple(protect))


class Floors:
    """Gerencia floors (worktrees) de um repo de projeto, registrados no Store."""

    def __init__(self, repo_path: str | Path, base_dir: str | Path, store: Store):
        self.repo = Path(repo_path)
        self.base = Path(base_dir).absolute()
        self._store = store
        check_project(self.repo)  # levanta FloorError se não for repo git

    def path(self, name: str) -> Path:
        return self.base / _check_name(name)

    def create(self, name: str, base_branch: str = "HEAD") -> Floor:
        _check_name(name)
        check_ref(base_branch)
        if self._store.get_floor(name) is not None:
            raise FloorError(f"floor {name!r} já existe")
        check_project(self.repo)
        wt = self.path(name)
        branch = f"floor/{name}"
        self.base.mkdir(parents=True, exist_ok=True)
        # cria worktree + branch nova a partir de base_branch
        _git(self.repo, "worktree", "add", "-b", branch, str(wt), base_branch)
        self._store.add_floor(name, branch, str(wt), base_branch)
        return Floor(name=name, branch=branch, path=str(wt), base_branch=base_branch)

    def get(self, name: str) -> Floor | None:
        row = self._store.get_floor(name)
        if row is None:
            return None
        return Floor(
            name=row["name"],
            branch=row["branch"],
            path=row["path"],
            base_branch=row["base_branch"],
        )

    def list(self) -> list[Floor]:
        return [
            Floor(name=r["name"], branch=r["branch"], path=r["path"], base_branch=r["base_branch"])
            for r in self._store.list_floors()
        ]

    def remove(self, name: str, *, delete_branch: bool = True) -> None:
        floor = self.get(name)
        if floor is None:
            raise FloorError(f"floor {name!r} não existe")
        check_project(self.repo)
        # remove o worktree (força: descarta mudanças não commitadas no worktree)
        _git(self.repo, "worktree", "remove", "--force", floor.path)
        _git(self.repo, "worktree", "prune")
        if delete_branch:
            # -D: remove mesmo sem merge (o registro é nosso, não do git)
            try:
                _git(self.repo, "branch", "-D", floor.branch)
            except FloorError:
                pass  # branch já some junto em alguns casos; não é fatal
        self._store.remove_floor(name)
