"""Floors × git do host (ADR-30): o agente não pode executar código FORA do sandbox via git.

O host roda git sobre uma árvore que o agente escreve. Cada ataque abaixo foi reproduzido na
v0.71.0 (marcador criado fora do sandbox). Dois níveis:
- sem bwrap (roda em qualquer CI): o agente escreve só na árvore dele → defesas do host;
- sob bwrap REAL (pula só se bwrap não funciona aqui): as travas de montagem. A base fica FORA
  de /tmp — o `--tmpfs /tmp` do sandbox mascararia por acidente e o teste passaria vácuo.
"""

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import pytest

from maestro import cli_floor
from maestro.engine import budget, sandbox
from maestro.engine.floor_merge import merge_floor, merge_preview
from maestro.engine.floor_run import (
    PAUSED_MSG,
    FloorTurn,
    commit_floor,
    nested_repos,
    run_floor_turn,
)
from maestro.engine.floors import Floor, FloorError, Floors, floor_git
from maestro.engine.runner import RunResult, RunStatus
from maestro.engine.safe_git import run_git
from maestro.engine.session import SessionManager
from maestro.engine.state.store import Store
from maestro.native.floors_ui import resolve_floors
from maestro.native.orchestrate import run_floor_agent_in_thread

ID = ["-c", "user.name=p", "-c", "user.email=p@x"]


def _bwrap_works() -> bool:
    if not sandbox.bwrap_available():
        return False
    return subprocess.run(
        ["bwrap", "--ro-bind", "/", "/", "true"], capture_output=True
    ).returncode == 0


needs_bwrap = pytest.mark.skipif(not _bwrap_works(), reason="bwrap não funciona neste ambiente")


class Env:
    """Repo + floor + payload. `mark` só existe se algo executou fora do sandbox."""

    def __init__(self, root: Path, *, hooks_path: str | None = None, submodule: str | None = None):
        self.root, self.repo, self.mark = root, root / "repo", root / "MARK"
        self.repo.mkdir(parents=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "p")
        self.git("config", "user.email", "p@x")
        (self.repo / "a").write_text("1\n")
        (self.repo / ".husky").mkdir()
        for h in ("pre-commit", "pre-merge-commit", "post-merge", "reference-transaction"):
            self.script(self.repo / ".husky" / h, "exit 0")
        self.git("add", ".")
        if submodule:  # gitlink legítimo do projeto (num worktree nasce como pasta vazia)
            oid = self.git("hash-object", "-w", "a").stdout.strip()
            tree = self.git("mktree", input="").stdout.strip()
            sub = self.git("commit-tree", "-m", "s", tree).stdout.strip()
            assert oid and sub
            self.git("update-index", "--add", "--cacheinfo", f"160000,{sub},{submodule}")
        self.git("commit", "-qm", "base")
        if hooks_path:
            self.git("config", "core.hooksPath", hooks_path)
        self.store = Store(root / "m.db")
        self.floors = Floors(self.repo, root / "floors", self.store)
        self.floor = self.floors.create("t", "main")
        self.wt = Path(self.floor.path)
        self.pay = self.script(self.wt / ".p.sh", f"touch {self.mark}")
        (self.wt / "novo").write_text("n\n")

    def git(self, *a, cwd=None, input=None):
        return subprocess.run(
            ["git", *a], cwd=cwd or self.repo, check=True, capture_output=True, text=True,
            input=input, stdin=subprocess.DEVNULL if input is None else None, timeout=20,
        )

    @staticmethod
    def script(path: Path, body: str) -> Path:
        path.write_text(f"#!/bin/sh\n{body}\nexit 0\n")
        path.chmod(0o755)
        return path

    def plant_repo(self, path: Path, *config):
        path.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", cwd=path)
        (path / "q").write_text("1\n")
        (path / ".gitattributes").write_text("* filter=z\n")
        self.git("add", "-A", cwd=path)
        self.git(*ID, "commit", "-qm", "x", cwd=path)
        for k, v in config:
            self.git("config", k, v, cwd=path)
        (path / "q").write_text(f"{os.urandom(4).hex()}\n")

    def snap(self):
        return commit_floor(self.floor, "m", self.repo)

    def ahead(self) -> int:
        return int(self.git("rev-list", "--count", f"main..{self.floor.branch}").stdout)

    def agent(self, script: str, **kw):
        """Roda `script` como o agente do floor: wrap() real + travas reais."""
        argv = sandbox.wrap(
            ["/bin/sh", "-c", script], workspace=str(self.wt),
            ro_paths=floor_git(self.repo, self.floor).protect, **kw,
        )
        return subprocess.run(
            argv, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30
        )


@pytest.fixture
def mk(monkeypatch):
    made = []

    def make(**kw):
        root = Path(tempfile.mkdtemp(prefix="maestro-floorgit-", dir=Path.home()))
        monkeypatch.setenv("MAESTRO_HOME", str(root / "home"))
        e = Env(root, **kw)
        made.append(e)
        return e

    yield make
    for e in made:
        e.store.close()
        shutil.rmtree(e.root, ignore_errors=True)


# -- defesas do HOST (sem bwrap) ---------------------------------------
def test_snapshot_normal_commita(mk):
    e = mk()
    s = e.snap()
    assert s.committed and s.skipped == () and e.ahead() == 1
    assert e.snap().committed is False  # nada novo


def test_hook_versionado_reescrito_nao_executa_no_commit_nem_no_merge(mk):
    """husky: hooksPath aponta pra dentro da árvore, que o agente edita legitimamente."""
    e = mk(hooks_path=".husky")
    for h in (e.wt / ".husky").iterdir():
        e.script(h, f"touch {e.mark}")
    assert e.snap().committed
    assert not e.mark.exists()
    assert merge_floor(e.repo, e.floor).ok
    assert not e.mark.exists()  # post-merge já vem do agente


def test_hooks_do_repo_nao_executam_no_merge(mk):
    e = mk()
    e.snap()
    (e.repo / ".git" / "hooks").mkdir(exist_ok=True)
    for h in ("post-merge", "pre-merge-commit", "reference-transaction"):
        e.script(e.repo / ".git" / "hooks" / h, f"touch {e.mark}")
    assert merge_preview(e.repo, e.floor).clean
    assert merge_floor(e.repo, e.floor).ok and not e.mark.exists()


@pytest.mark.parametrize("como", ["arquivo", "symlink", "pasta", "ausente", "lixo"])
def test_ponteiro_git_trocado_e_recusado(mk, como):
    e = mk()
    gd = e.root / "gd"
    e.git("init", "-q", "--bare", str(gd))
    e.git(f"--git-dir={gd}", "config", "filter.z.clean", str(e.pay))
    e.git(f"--git-dir={gd}", "config", "core.fsmonitor", str(e.pay))
    (e.wt / ".gitattributes").write_text("* filter=z\n")
    ptr = e.wt / ".git"
    ptr.unlink()
    if como == "arquivo":
        ptr.write_text(f"gitdir: {gd}\n")
    elif como == "symlink":
        ptr.symlink_to(gd)
    elif como == "pasta":
        shutil.copytree(gd, ptr)
    elif como == "lixo":
        ptr.write_bytes(b"\xff\xfe")
    with pytest.raises(FloorError, match="ponteiro"):
        e.snap()
    with pytest.raises(FloorError, match="ponteiro"):
        floor_git(e.repo, e.floor)  # o próximo run também recusa
    assert not e.mark.exists()


def test_repo_aninhado_fica_fora_e_avisa(mk):
    e = mk()
    e.plant_repo(e.wt / "x" / "n", ("filter.z.clean", str(e.pay)), ("core.fsmonitor", str(e.pay)))
    for _ in range(2):  # 2º turno: gitlink já no índice faria o git entrar nele
        (e.wt / "novo").write_text(os.urandom(4).hex())
        s = e.snap()
        assert s.committed and s.skipped == ("x/n",)
    assert not e.mark.exists()
    assert "x/n" not in e.git("ls-tree", "-r", "--name-only", e.floor.branch).stdout


def test_submodulo_legitimo_preenchido_pelo_agente_nao_executa(mk):
    """Gitlink JÁ no índice do projeto: o caminho que faz o git rodar status lá dentro."""
    e = mk(submodule="sub")
    e.plant_repo(e.wt / "sub", ("filter.z.clean", str(e.pay)), ("core.fsmonitor", str(e.pay)))
    s = e.snap()
    assert s.committed and s.skipped == ("sub",) and not e.mark.exists()


@pytest.mark.parametrize("sub", ["sub", "vendor/lib"])
def test_submodulo_escondido_por_permissao_nao_executa(mk, sub):
    """Achado Fable 1: `chmod 111` cega o os.walk, mas o git só precisa de lstat pro gitlink
    que JÁ está no índice — a exclusão tem de vir do índice (do host), não da árvore."""
    e = mk(submodule=sub)
    e.plant_repo(e.wt / sub, ("filter.z.clean", str(e.pay)), ("core.fsmonitor", str(e.pay)))
    esconde = e.wt if "/" not in sub else (e.wt / sub).parent
    esconde.chmod(0o111)
    try:
        for _ in range(3):
            s = e.snap()
    finally:
        esconde.chmod(0o755)
    assert not e.mark.exists() and s.skipped == (sub,)


def test_corrida_entre_varredura_e_add_nao_deixa_gitlink(mk, monkeypatch):
    """Achado Fable 2: outro agente no mesmo floor esconde o repo durante a varredura. O
    gitlink não pode ficar no índice/commit (no turno seguinte o git entraria nele)."""
    e = mk()
    e.plant_repo(e.wt / "x" / "n", ("filter.z.clean", str(e.pay)), ("core.fsmonitor", str(e.pay)))
    monkeypatch.setattr("maestro.engine.floor_run.nested_repos", lambda root: [])
    for _ in range(2):
        (e.wt / "novo").write_text(os.urandom(4).hex())
        s = e.snap()
        assert s.committed and s.skipped == ("x/n",)
        (e.wt / "x" / "n" / "q").write_text(os.urandom(4).hex())
    assert not e.mark.exists()
    assert "160000" not in e.git("ls-tree", "-r", e.floor.branch).stdout
    assert "novo" in e.git("ls-tree", "--name-only", e.floor.branch).stdout


@pytest.mark.parametrize("onde", ["igual", "dentro", "symlink", "estado-do-app"])
def test_projeto_em_area_gravavel_por_agente_e_recusado_em_todo_caminho(mk, monkeypatch, onde):
    """Achado Fable 3: o nó INTERATIVO monta os rw_paths sem trava de .git; um projeto ali já
    pode estar envenenado. A recusa vale pra QUALQUER operação, não só o run."""
    e = mk()
    alvo, env = e.repo, None
    if onde == "dentro":
        alvo = e.root
    elif onde == "symlink":
        alvo = e.root / "atalho"
        alvo.symlink_to(e.repo)
    elif onde == "estado-do-app":
        env, alvo = str(e.root), None

    class Prof:
        rw_paths = [str(alvo)] if alvo else []

    monkeypatch.setattr("maestro.engine.floors.load_profiles", lambda: {"p": Prof()})
    if env:
        monkeypatch.setenv("MAESTRO_HOME", env)
    e.git("config", "filter.z.clean", str(e.pay))
    (e.wt / ".gitattributes").write_text("* filter=z\n")
    for op in (
        lambda: Floors(e.repo, e.root / "floors", e.store),
        lambda: floor_git(e.repo, e.floor),
        lambda: e.snap(),
        lambda: merge_preview(e.repo, e.floor),
        lambda: merge_floor(e.repo, e.floor),
        lambda: e.floors.create("novo"),
        lambda: e.floors.remove("t"),
    ):
        with pytest.raises(FloorError, match="gravável"):
            op()
    assert not e.mark.exists()
    assert resolve_floors(e.store, e.root / "floors", e.repo) is None  # canvas abre sem floors


@pytest.mark.parametrize("onde", ["repo-igual", "repo-dentro", "comum", "floor", "contas"])
def test_cada_caminho_do_projeto_e_conferido(mk, monkeypatch, onde):
    """Projeto que é worktree ligado: pasta e git-dir comum ficam em lugares diferentes, e a
    recusa tem de olhar os dois (e o próprio floor, e a raiz das contas)."""
    e = mk()
    (e.root / "area").mkdir()
    lw = e.root / "area" / "linked"
    e.git("worktree", "add", "-q", "-b", "l", str(lw))
    Floors(lw, e.root / "floors", e.store)  # controle: sem área gravável, aceita
    atalho = e.root / "atalho"  # e por symlink: quem vale é o caminho real
    atalho.symlink_to(lw)
    raiz = {"repo-igual": lw, "repo-dentro": lw.parent, "comum": e.repo,
            "floor": e.root / "floors", "contas": None}[onde]

    class Prof:
        rw_paths = [str(raiz)] if raiz else []

    monkeypatch.setattr("maestro.engine.floors.load_profiles", lambda: {"p": Prof()})
    if onde == "contas":
        monkeypatch.setattr("maestro.engine.floors.accounts_root", lambda: lw.parent)
    with pytest.raises(FloorError, match="gravável"):
        if onde == "floor":
            e.snap()
        else:
            Floors(atalho, e.root / "floors", e.store)


def test_repo_aninhado_sem_commit_nao_bloqueia_o_snapshot(mk):
    """`git add` FALHA num repo aninhado vazio — a varredura o tira antes."""
    e = mk()
    (e.wt / "v").mkdir()
    e.git("init", "-q", cwd=e.wt / "v")
    s = e.snap()
    assert s.committed and s.skipped == ("v",)


def test_nome_nao_utf8_nao_derruba_o_snapshot(mk):
    """Achado Fable 4: UnicodeEncodeError no pathspec deixava o canvas preso em 'rodando…'."""
    e = mk()
    ruim = os.fsencode(e.wt) + b"/bad\xff"
    e.plant_repo(Path(os.fsdecode(ruim)))
    with open(os.fsencode(e.wt) + b"/x\xff", "w") as fh:
        fh.write("1")
    s = e.snap()
    assert s.committed and s.skipped == (os.fsdecode(b"bad\xff"),)


def test_erro_ilegivel_vira_FloorError(mk):
    e = mk()
    p = os.fsencode(e.wt) + b"/x\xff"
    with open(p, "w") as fh:
        fh.write("1")
    os.chmod(p, 0)
    with pytest.raises(FloorError):
        e.snap()


def test_resumo_nao_injeta_no_terminal_nem_quebra_a_ui():
    ok = RunResult(RunStatus.OK, 0, "", "", 0.0, False)
    t = FloorTurn(ok, committed=True, skipped=("a\x1b[2J\r\nb", "\udcff"))
    assert t.summary().isprintable() and t.summary().encode("utf-8")


def test_worker_do_canvas_sempre_chama_on_done(mk, monkeypatch):
    e = mk()

    async def explode(*a, **k):
        raise RuntimeError("inesperado")

    t, _ = _turn(e, run_fn=explode)
    assert t.error and "inesperado" in t.error  # turno converte

    def snap_explode(*a, **k):
        raise RuntimeError("no snapshot")

    with monkeypatch.context() as m:
        m.setattr("maestro.engine.floor_run.commit_floor", snap_explode)
        t, _ = _turn(e)
    assert t.res.ok and not t.ok and "no snapshot" in t.summary()
    monkeypatch.setattr("maestro.native.orchestrate.run_floor_turn", explode)
    got, done = [], threading.Event()
    run_floor_agent_in_thread(
        SessionManager(e.store), _Prof(), "a", "p", e.floor, e.repo,
        lambda turn: (got.append(turn), done.set()), store=e.store,
    )
    assert done.wait(10) and "inesperado" in got[0].summary()


def test_git_lento_nao_trava_o_event_loop(mk, monkeypatch):
    """O loop é compartilhado por toda a orquestração do canvas: git lento de um floor não
    pode congelar os outros agentes (nem no snapshot, nem na conferência antes do run)."""
    import maestro.engine.floor_run as fr

    e = mk()
    for nome in ("commit_floor", "floor_git"):
        real = getattr(fr, nome)

        def lento(*a, _real=real, **k):
            time.sleep(0.4)
            return _real(*a, **k)

        monkeypatch.setattr(fr, nome, lento)

    async def run_fn(profile, prompt, **kw):
        return RunResult(RunStatus.OK, 0, "", "", 0.0, False)

    async def main():
        pior, vivo = 0.0, True

        async def relogio():
            nonlocal pior
            while vivo:
                t0 = time.monotonic()
                await asyncio.sleep(0.02)
                pior = max(pior, time.monotonic() - t0)

        r = asyncio.create_task(relogio())
        await asyncio.sleep(0.05)  # o relógio tem de estar correndo ANTES (senão é vácuo)
        t = await run_floor_turn(
            SessionManager(e.store), _Prof(), "ag", "p", e.floor, e.repo,
            timeout=5, store=e.store, run_fn=run_fn,
        )
        vivo = False
        await r
        return t, pior

    t, pior = asyncio.run(main())
    assert t.committed and pior < 0.3, pior


def test_timeout_no_add_nao_deixa_index_lock(mk):
    """SIGKILL direto deixaria o `index.lock` e o floor nunca mais faria snapshot."""
    e = mk()
    gd = floor_git(e.repo, e.floor).git_dir
    big = e.wt / "big"
    with big.open("wb") as fh:
        fh.truncate(40 * 2**30)  # esparso: `git add` leva minutos
    r = run_git(e.wt, "add", "-A", git_dir=gd, timeout=1)
    assert r.returncode == 124, r
    big.unlink()
    assert not (gd / "index.lock").exists()
    assert e.snap().committed


def test_git_travado_expira_e_mata_o_grupo(mk):
    """O neto herda o stdout: matar só o git deixaria o communicate() preso no pipe."""
    e = mk()
    t0 = time.monotonic()
    r = run_git(e.repo, "-c", "alias.x=!sleep 20 & sleep 20", "x", timeout=1)
    assert r.returncode != 0 and "tempo" in r.stderr and time.monotonic() - t0 < 10


def test_wrap_recusa_symlink_no_caminho_travado(tmp_path, monkeypatch):
    """bwrap segue symlink no DESTINO do bind: a trava cairia noutro arquivo."""
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    (tmp_path / "alvo").write_text("x")
    (tmp_path / ".git").symlink_to("alvo")
    with pytest.raises(sandbox.SandboxUnavailable):
        sandbox.wrap(["x"], workspace=tmp_path, ro_paths=[str(tmp_path / ".git")])


def test_nested_repos_acha_arquivo_pasta_e_symlink(tmp_path):
    (tmp_path / ".git").write_text("gitdir: x")  # o do próprio floor não conta
    (tmp_path / "a" / ".git").mkdir(parents=True)
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / ".git").write_text("gitdir: y")
    (tmp_path / "c").mkdir()
    (tmp_path / "c" / ".git").symlink_to("/nao/existe")
    (tmp_path / "d").mkdir()
    assert nested_repos(tmp_path) == ["a", "b", "c"]


def test_ponteiro_symlink_com_conteudo_valido_e_recusado(mk):
    """Conteúdo certo AGORA, mas o alvo é arquivo comum da árvore: troca-se depois."""
    e = mk()
    ptr = e.wt / ".git"
    ptr.rename(e.wt / "o")
    ptr.symlink_to("o")
    with pytest.raises(FloorError, match="ponteiro"):
        floor_git(e.repo, e.floor)


@pytest.mark.parametrize("nome", ["n*", "*\n:(top)"])
def test_caminho_hostil_de_repo_aninhado_vira_literal(mk, nome):
    """Como glob, `n*` excluiria também o arquivo `novo` — o agente esconderia mudanças."""
    e = mk()
    e.plant_repo(e.wt / nome)
    s = e.snap()
    assert s.committed and s.skipped == (nome,) and e.ahead() == 1
    assert "novo" in e.git("ls-tree", "--name-only", e.floor.branch).stdout


def test_git_dir_do_ambiente_nao_desvia_o_host(mk, monkeypatch):
    e = mk()
    monkeypatch.setenv("GIT_DIR", str(e.root / "outro"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(e.root / "idx"))
    assert e.snap().committed


@pytest.mark.parametrize("base", ["-f", "--lock", "--output=/tmp/x", ""])
def test_base_que_parece_opcao_e_recusada(mk, base):
    """`--from -f` virava OPÇÃO do `git worktree add`; num registro/backup, do diff/merge."""
    e = mk()
    with pytest.raises(FloorError, match="base inválida"):
        e.floors.create("novo", base)
    if base:  # vazio = branch atual (registro legado)
        ruim = Floor("t", e.floor.branch, e.floor.path, base)
        for op in (merge_preview, merge_floor):
            with pytest.raises(FloorError, match="base inválida"):
                op(e.repo, ruim)


def test_floor_de_outro_repo_e_recusado(mk):
    e, outro = mk(), mk()
    with pytest.raises(FloorError, match="não é um worktree"):
        commit_floor(e.floor, "m", outro.repo)


def test_nenhum_git_cru_fora_do_safe_git():
    raiz = Path(sandbox.__file__).resolve().parents[1]
    crus = [
        str(p.relative_to(raiz)) for p in raiz.rglob("*.py")
        if p.name != "safe_git.py" and re.search(r"""\[\s*['"]git['"]""", p.read_text())
    ]
    assert crus == []


# -- trava no sandbox --------------------------------------------------
def test_wrap_trava_por_cima_de_todo_bind(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    g = tmp_path / ".git"
    g.mkdir()
    a = sandbox.wrap(
        ["x"], workspace=tmp_path, rw_paths=[str(tmp_path)], shared_paths=[str(g)],
        ro_paths=[str(g)],
    )
    ro = max(i for i, v in enumerate(a) if v == "--ro-bind" and a[i + 1] == str(g))
    assert ro > max(i for i, v in enumerate(a) if v in ("--bind", "--tmpfs"))


def test_wrap_falha_fechado_sem_o_caminho(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    with pytest.raises(sandbox.SandboxUnavailable):
        sandbox.wrap(["x"], workspace=tmp_path, ro_paths=[str(tmp_path / "nao")])


ATAQUES = {
    "hook": "mkdir -p $R/.git/hooks; cp $P $R/.git/hooks/pre-commit",
    "fsmonitor": "git -C $R config core.fsmonitor $P",
    "filtro": "git -C $R config filter.z.clean $P; echo '* filter=z' > $W/.gitattributes",
    "hooksPath": "mkdir $W/h; cp $P $W/h/pre-commit; git -C $R config core.hooksPath $W/h",
    "ponteiro": "rm -f $W/.git; echo gitdir: $W/gd > $W/.git; mv $W/.git $W/o; ln -sf o $W/.git",
    "commondir": "cp -r $R/.git $W/cd; git --git-dir=$W/cd config filter.z.clean $P;"
    " echo '* filter=z' > $W/.gitattributes; echo $W/cd > $R/.git/worktrees/t/commondir",
    "config.worktree": "git -C $R config extensions.worktreeConfig true;"
    " git -C $W config --worktree core.fsmonitor $P",
    "move main": "git -C $W update-ref refs/heads/main $(git -C $W commit-tree -m x HEAD^{tree})",
    "renomeia .git": "mv $R/.git $R/.g2; mv $W/.git $W/.g3",
}


@needs_bwrap
@pytest.mark.parametrize("nome", ATAQUES)
@pytest.mark.parametrize("cfg_rw", [False, True], ids=["normal", "repo-em-pasta-rw"])
def test_ataque_sob_bwrap_real(mk, nome, cfg_rw):
    """`repo-em-pasta-rw`: a camada de sandbox sozinha — mesmo com o projeto rw, a trava vence.
    (O floor real recusa antes: projeto em área gravável, ver o teste do achado Fable 3.)"""
    e = mk()
    antes = (e.git("rev-parse", "main").stdout, (e.repo / ".git" / "config").read_bytes())
    kw = {"rw_paths": [str(e.repo)]} if cfg_rw else {}
    r = e.agent(f"R={e.repo}; W={e.wt}; P={e.pay}; {ATAQUES[nome]}; echo fim > $W/prova", **kw)
    assert (e.wt / "prova").exists(), r.stderr  # o agente rodou mesmo (não é passe vácuo)
    s = e.snap()
    e.git("status", "--ignore-submodules=all")  # o git do USUÁRIO depois
    assert not e.mark.exists()
    assert s.committed
    depois = (e.git("rev-parse", "main").stdout, (e.repo / ".git" / "config").read_bytes())
    assert depois == antes


class _RwPai:
    """Perfil que libera rw uma pasta ACIMA do projeto."""

    session_assign, cmd = "caller", ["sh"]

    def __init__(self, e, script):
        self.rw_paths, self.script = [str(e.root)], script

    def build_command(self, prompt, **kw):
        return ["/bin/sh", "-c", self.script]


@needs_bwrap
def test_projeto_dentro_de_pasta_rw_do_perfil_e_recusado(mk, monkeypatch):
    """A trava fica no `.git`, mas renomear o PAI do ponto de montagem é permitido: o agente
    trocaria `repo/` inteiro por uma cópia com config dele."""
    e = mk()
    ataque = (
        f"mv {e.repo} {e.repo}2; cp -r {e.repo}2 {e.repo};"
        f" git --git-dir={e.repo}/.git config filter.z.clean {e.pay};"
        f" echo '* filter=z' > {e.wt}/.gitattributes"
    )
    prof = _RwPai(e, ataque)
    monkeypatch.setattr("maestro.engine.floors.load_profiles", lambda: {"p": prof})
    t = asyncio.run(run_floor_turn(
        SessionManager(e.store), prof, "ag", "p", e.floor, e.repo,
        timeout=20, store=e.store,
    ))
    assert not e.mark.exists()
    assert t.error and "gravável" in t.error


def test_projeto_que_e_worktree_tem_o_proprio_ponteiro_travado(mk):
    e = mk()
    lw = e.root / "linked"
    e.git("worktree", "add", "-q", "-b", "l", str(lw))
    fl = Floors(lw, e.root / "floors", e.store)
    f = fl.create("t2", "main")
    assert set(floor_git(lw, f).protect) == {
        f"{f.path}/.git", str(e.repo / ".git"), str(lw / ".git")
    }


@needs_bwrap
def test_agente_benigno_le_git_mas_nao_commita(mk):
    e = mk()
    r = e.agent("git status --short && git diff && git log --oneline && echo LEU")
    assert "LEU" in r.stdout, r.stderr
    assert e.agent(f"git {' '.join(ID)} commit -qam x").returncode != 0
    assert e.snap().committed and e.ahead() == 1


# -- turno único: budget, recusa e CLI ---------------------------------
class _Prof:
    session_assign, rw_paths, cmd = "caller", (), ["sh"]


def _turn(e, **over):
    calls = []

    async def run_fn(profile, prompt, **kw):
        calls.append(kw)
        return RunResult(RunStatus.OK, 0, "", "", 0.0, False)

    kw = {"timeout": 5, "store": e.store, "run_fn": run_fn, **over}
    t = asyncio.run(
        run_floor_turn(SessionManager(e.store), _Prof(), "ag", "p", e.floor, e.repo, **kw)
    )
    return t, calls


def test_turno_trava_o_git_e_commita(mk):
    e = mk()
    t, calls = _turn(e)
    assert t.ok and t.committed
    assert set(calls[0]["ro_paths"]) == {str(e.wt / ".git"), str(e.repo / ".git")}


@needs_bwrap
def test_turno_real_ponta_a_ponta(mk):
    """Caminho de PRODUÇÃO inteiro (turno→sessão→run_agent→wrap→bwrap), sem run_fn falso."""
    e = mk()
    hook = f"{e.repo}/.git/hooks/pre-commit"
    ataque = f"mkdir -p {e.repo}/.git/hooks; cp {e.pay} {hook}; rm -f {e.wt}/.git"

    class Real(_Prof):
        def build_command(self, prompt, **kw):
            return ["/bin/sh", "-c", f"{ataque}; echo ok > {e.wt}/prova"]

    t = asyncio.run(run_floor_turn(
        SessionManager(e.store), Real(), "ag", "p", e.floor, e.repo, timeout=20, store=e.store
    ))
    assert (e.wt / "prova").exists(), t
    assert t.ok and t.committed, t.summary()
    assert not Path(hook).exists() and not e.mark.exists()


def test_turno_com_ponteiro_trocado_nao_roda_o_agente(mk):
    e = mk()
    (e.wt / ".git").write_text("gitdir: /x\n")
    t, calls = _turn(e)
    assert not t.ok and calls == [] and "ponteiro" in t.summary()


def _estoura(store):
    store.set_ui("budget_hard", "1")
    budget.record_spend(store, "x", 5.0)
    assert budget.is_paused(store)


def test_turno_pausado_nao_roda_nem_commita(mk):
    e = mk()
    _estoura(e.store)
    t, calls = _turn(e)
    assert t.paused and calls == [] and e.ahead() == 0 and t.summary() == PAUSED_MSG


def test_agente_nao_forja_pausa_pelo_stderr(mk):
    e = mk()

    async def mente(profile, prompt, **kw):
        return RunResult(RunStatus.FAILED, 1, "", "pausado por budget", 0.0, False)

    t, _ = _turn(e, run_fn=mente)
    assert not t.paused and t.committed


def test_cli_floor_run_respeita_o_budget(mk, monkeypatch, capsys):
    """A entrada que esquecia o `store`: gastava com o hard estourado (v0.71.0)."""
    e = mk()
    _estoura(e.store)
    calls = []

    async def run_in_session(self, *a, **k):
        calls.append(a)
        return RunResult(RunStatus.OK, 0, "", "", 0.0, False)

    monkeypatch.setattr(SessionManager, "run_in_session", run_in_session)
    monkeypatch.setattr("maestro.engine.adapters.base.load_profiles", lambda: {"f": _Prof()})
    rc = cli_floor._do_run(e.repo, e.store, e.floor, "f", ["oi"])
    assert rc == 1 and calls == []
    assert "pausado por budget" in capsys.readouterr().out
