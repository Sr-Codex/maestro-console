"""Git do HOST — ponto ÚNICO por onde o console chama git (ADR-30).

O console roda git FORA do sandbox sobre árvores que o agente escreve. Git não é só dado:
config, hooks, filtros e o próprio ponteiro `.git` podem mandar executar programas. Duas
camadas, nenhuma basta sozinha:

1. o agente não escreve metadado git (`Floor` → `ro_paths` do sandbox);
2. o host nunca DESCOBRE o repositório pela árvore do agente (`--git-dir` explícito) e
   desliga o que executa código a partir da árvore (hooks, fsmonitor, submódulos).

Só travas `-c` NÃO resolvem: filtro tem nome arbitrário e a config local sempre é lida.
`tests/test_floor_git_sandbox.py` barra `["git", ...]` cru em qualquer outro módulo.
"""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path

_HARDEN = (
    "-c", "core.hooksPath=/dev/null",  # inclui hook versionado (husky): o agente edita a árvore
    "-c", "core.fsmonitor=false",
    "-c", "submodule.recurse=false",
    "-c", "diff.ignoreSubmodules=all",  # não roda git DENTRO de um repo plantado na árvore
)

# Redirecionariam o git pra outro repositório/índice se herdadas do ambiente do app.
_LOCATION_ENV = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE",
)


def run_git(
    repo: str | Path,
    *args: str,
    git_dir: str | Path | None = None,
    input: str | None = None,
    timeout: float = 600.0,
) -> subprocess.CompletedProcess[str]:
    """Roda git endurecido com cwd em `repo`. Com `git_dir`, a árvore é `repo` e NÃO há
    descoberta (obrigatório quando `repo` é gravável por agente). Nunca levanta por exit≠0
    nem por tempo (vira returncode 124). Nomes não-UTF8 vão e voltam (surrogateescape)."""
    where = [f"--git-dir={git_dir}", f"--work-tree={repo}"] if git_dir is not None else []
    env = {k: v for k, v in os.environ.items() if k not in _LOCATION_ENV}
    env["GIT_TERMINAL_PROMPT"] = "0"
    argv = ["git", *_HARDEN, "-C", str(repo), *where, *args]
    proc = subprocess.Popen(
        argv, env=env, encoding="utf-8", errors="surrogateescape",
        stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True,  # o timeout mata o GRUPO: neto vivo (gpg) seguraria o pipe
    )
    try:
        out, err = proc.communicate(input, timeout=timeout)
        return subprocess.CompletedProcess(argv, proc.returncode, out, err)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)  # git remove o próprio index.lock no SIGTERM
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
        return subprocess.CompletedProcess(argv, 124, "", f"tempo esgotado ({timeout:.0f}s)")
