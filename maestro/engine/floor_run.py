"""Rodar um agente DENTRO de um floor (worktree) + snapshot do trabalho (V8-S2).

O agente roda com cwd = worktree do floor, confinado por bwrap (ADR-6). Ele EDITA arquivos e
lê o git (status/diff/log); **não escreve metadado git** (ADR-30): o `.git` do repo e o
ponteiro `<floor>/.git` ficam somente-leitura, senão um hook/config plantado executaria fora
do sandbox no próximo git do host (ou do usuário).

O console versiona: `commit_floor` faz o snapshot na branch do floor — assim o merge preview
(V8-S4) tem commits para comparar. `run_floor_turn` é a entrada ÚNICA (CLI e canvas): gate de
budget → agente → snapshot.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

from . import budget
from .agent_run import run_agent
from .floors import Floor, FloorError, floor_git
from .runner import RunResult, RunStatus
from .safe_git import run_git

PAUSED_MSG = "pausado por budget — libere no Limites (💰) e rode de novo."


@dataclass(frozen=True)
class Snapshot:
    committed: bool
    skipped: tuple[str, ...] = ()  # repos aninhados deixados fora do commit


@dataclass(frozen=True)
class FloorTurn:
    res: RunResult
    committed: bool = False
    skipped: tuple[str, ...] = ()
    paused: bool = False  # barrado pelo budget: nada rodou
    error: str | None = None  # recusa de segurança ou falha do snapshot

    @property
    def ok(self) -> bool:
        return self.res.ok and self.error is None

    def summary(self) -> str:
        """Texto ÚNICO de resultado (CLI e canvas dizem a mesma coisa). Traz nome de arquivo
        e stderr vindos do agente → sem control char (terminal) nem surrogate (GTK)."""
        return "".join(c if c.isprintable() else " " for c in self._text())

    def _text(self) -> str:
        if self.paused:
            return PAUSED_MSG
        if self.error:
            return f"{self.res.status}; erro: {self.error}"
        out = f"{self.res.status}; commit={'sim' if self.committed else '(nada a commitar)'}"
        if self.skipped:
            out += f"; fora do commit (repo aninhado): {', '.join(self.skipped)}"
        return out


def failed_turn(error: str) -> FloorTurn:
    return FloorTurn(_failed(error), error=error)


def _failed(stderr: str) -> RunResult:
    return RunResult(
        status=RunStatus.FAILED, returncode=None, stdout="", stderr=stderr,
        duration_s=0.0, timed_out=False,
    )


def _budget_paused(store) -> bool:
    try:
        return budget.is_paused(store)
    except Exception:
        return False  # freio best-effort (mesma postura do gate do delegate)


async def run_agent_in_floor(
    session_manager,
    profile,
    agent_id: str,
    prompt: str,
    floor: Floor,
    repo: str | Path,
    *,
    timeout: float,
    store,
    on_output=None,
    run_fn=run_agent,
) -> RunResult:
    """Executa o agente com cwd = worktree do floor, sob sessão/mutex + bwrap.

    Gate de budget (docs/29 §5.2): `store` é OBRIGATÓRIO — opcional, uma entrada o esquecia
    e gastava fora do freio. No hard: FAIL-FAST com texto de pausa (nunca "falhou"), SEM
    retenção — reter re-executaria fora do cwd do floor (emenda Fable E3).
    """
    if _budget_paused(store):
        return _failed(PAUSED_MSG)
    # git em thread: o event loop é compartilhado por toda a orquestração do canvas
    protect = (await asyncio.to_thread(floor_git, repo, floor)).protect
    return await session_manager.run_in_session(
        profile,
        agent_id,
        prompt,
        workspace=floor.path,
        timeout=timeout,
        run_fn=run_fn,
        on_output=on_output,
        ro_paths=protect,
    )


def nested_repos(root: str | Path) -> list[str]:
    """Caminhos (relativos) que são outro repo git dentro da árvore. Um `git add` do host
    neles rodaria git com a config DELES — escrita pelo agente."""
    found: list[str] = []
    for cur, dirs, files in os.walk(root):  # não segue symlink de diretório
        if cur != str(root) and (".git" in dirs or ".git" in files):
            found.append(os.path.relpath(cur, root))
            dirs[:] = []
        elif ".git" in dirs:
            dirs.remove(".git")
    return sorted(found)


def commit_floor(floor: Floor, message: str, repo: str | Path) -> Snapshot:
    """Snapshot das mudanças do worktree na branch do floor. Roda FORA do sandbox: usa o
    git-dir que o HOST conhece e nunca o que a árvore do agente aponta (ADR-30)."""
    wt = str(Path(floor.path).resolve())
    git_dir = floor_git(repo, floor).git_dir

    def git(*args: str, input: str | None = None, ok=(0,)):
        r = run_git(wt, *args, git_dir=git_dir, input=input)
        if r.returncode not in ok:
            raise FloorError(f"git {args[0]} falhou no floor {floor.name!r}: {r.stderr.strip()}")
        return r

    def gitlinks() -> set[str]:
        rows = git("ls-files", "-s", "-z").stdout.split("\0")
        return {r.split("\t", 1)[1] for r in rows if r.startswith("160000 ")}

    # O git só ENTRA num repo aninhado (e executa a config dele) se houver gitlink no índice,
    # e o índice é do host. Logo quem manda é o índice, não a varredura da árvore, que o agente
    # cega (chmod) ou corre (rename): gitlink antigo fica sempre fora do add; novo sai do índice.
    known = gitlinks()
    nested = set(nested_repos(wt))
    for _ in range(3):
        specs = [".", *(f":(exclude,literal,top){p}" for p in sorted(nested | known))]
        git("add", "-A", "--pathspec-from-file=-", "--pathspec-file-nul", input="\0".join(specs))
        new = gitlinks() - known
        if not new:
            break
        git("read-tree", "HEAD")  # descarta o índice; não toca a árvore
        nested |= new
    else:
        raise FloorError(f"repos aninhados mudando durante o snapshot do floor {floor.name!r}")
    filled = {p for p in known if os.path.lexists(os.path.join(wt, p, ".git"))}
    skipped = tuple(sorted(nested | filled))
    if git("diff", "--cached", "--quiet", "--no-ext-diff", ok=(0, 1)).returncode == 0:
        return Snapshot(False, skipped)
    git("commit", "-m", message)
    return Snapshot(True, skipped)


async def run_floor_turn(
    session_manager,
    profile,
    agent_id: str,
    prompt: str,
    floor: Floor,
    repo: str | Path,
    *,
    timeout: float,
    store,
    run_fn=run_agent,
) -> FloorTurn:
    """Turno completo no floor: gate → agente → snapshot. Entrada única de CLI e canvas.
    Nunca levanta: quem chama precisa sempre de um resultado pra mostrar."""
    if _budget_paused(store):
        return FloorTurn(_failed(PAUSED_MSG), paused=True)
    try:
        res = await run_agent_in_floor(
            session_manager, profile, agent_id, prompt, floor, repo,
            timeout=timeout, store=store, run_fn=run_fn,
        )
    except Exception as e:
        return failed_turn(str(e))
    try:
        msg = f"floor {floor.name}: {prompt[:50]}"
        snap = await asyncio.to_thread(commit_floor, floor, msg, repo)
    except Exception as e:
        return FloorTurn(res, error=str(e))
    return FloorTurn(res, committed=snap.committed, skipped=snap.skipped)
