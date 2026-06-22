"""CLI `maestro floor` — create / list / preview / merge / rm / run (V8-S4).

Resolve o repo de projeto por cwd, com `MAESTRO_PROJECT`/`--project` como
override (decisão de foundation). Lógica testável (sem GTK).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .engine.floor_merge import merge_floor, merge_preview
from .engine.floors import FloorError, Floors
from .engine.project import ProjectError, resolve_project
from .engine.state.store import Store

_NEEDS_NAME = {"preview", "merge", "rm", "run"}


def _build_parser(home_default) -> argparse.ArgumentParser:
    # opções comuns (em cada subparser → aceitas após o subcomando)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project", default=None, help="repo (override do cwd/MAESTRO_PROJECT)")
    common.add_argument("--home", default=home_default, help="MAESTRO_HOME (estado)")

    p = argparse.ArgumentParser(prog="maestro floor", description="ambientes isolados (worktree)")
    sub = p.add_subparsers(dest="action", required=True)
    c = sub.add_parser("create", parents=[common], help="cria um floor (worktree + branch)")
    c.add_argument("name")
    c.add_argument("--from", dest="base", default="HEAD", help="branch/ref base (default HEAD)")
    sub.add_parser("list", parents=[common], help="lista floors")
    pv = sub.add_parser("preview", parents=[common], help="merge preview (diff + conflitos)")
    pv.add_argument("name")
    mg = sub.add_parser("merge", parents=[common], help="integra o floor na base")
    mg.add_argument("name")
    rm = sub.add_parser("rm", parents=[common], help="remove o floor (worktree + branch)")
    rm.add_argument("name")
    rn = sub.add_parser("run", parents=[common], help="roda um agente no floor")
    rn.add_argument("name")
    rn.add_argument("agent")
    rn.add_argument("prompt", nargs="+")
    return p


def floor_cli(argv: list[str], *, home: str | Path | None = None) -> int:
    parser = _build_parser(home)
    args = parser.parse_args(argv)
    try:
        repo = resolve_project(override=args.project)
    except ProjectError as e:
        print(f"erro: {e}")
        return 2
    from .bootstrap import default_home

    base = Path(args.home) if args.home else default_home()
    store = Store(base / "maestro.db")
    try:
        floors = Floors(repo, base / "floors", store)
        return _dispatch(args, repo, floors)
    except FloorError as e:
        print(f"erro: {e}")
        return 1
    finally:
        store.close()


def _dispatch(args, repo, floors) -> int:
    if args.action == "create":
        f = floors.create(args.name, args.base)
        print(f"floor {f.name!r} criado: {f.path} (branch {f.branch}, base {f.base_branch})")
        return 0
    if args.action == "list":
        fs = floors.list()
        if not fs:
            print("(nenhum floor)")
        for f in fs:
            print(f"{f.name}\t{f.branch}\t{f.path}")
        return 0

    # ações por nome
    f = floors.get(args.name)
    if args.action in _NEEDS_NAME and f is None:
        print(f"erro: floor {args.name!r} não existe")
        return 1

    if args.action == "preview":
        pv = merge_preview(repo, f)
        print(f"base: {pv.base} | {len(pv.files)} arquivo(s) +{pv.insertions}/-{pv.deletions}")
        for path in pv.files:
            print(f"  ~ {path}")
        if pv.conflicts:
            print(f"CONFLITOS ({len(pv.conflicts)}):")
            for c in pv.conflicts:
                print(f"  ! {c}")
        else:
            print("sem conflitos — merge limpo possível")
        return 0
    if args.action == "merge":
        r = merge_floor(repo, f)
        if r.ok:
            print(f"floor {f.name!r} integrado com sucesso")
            return 0
        print(f"merge não realizado: {r.reason}")
        for c in r.conflicts:
            print(f"  ! {c}")
        return 1
    if args.action == "rm":
        floors.remove(args.name)
        print(f"floor {args.name!r} removido")
        return 0
    if args.action == "run":
        return _do_run(repo, floors._store, f, args.agent, args.prompt)
    return 0


def _do_run(repo, store, floor, agent_id: str, prompt_words: list[str]) -> int:
    import asyncio
    import shutil

    from .engine.adapters.base import load_profiles
    from .engine.floor_run import commit_floor, run_agent_in_floor
    from .engine.session import SessionManager

    profiles = {n: p for n, p in load_profiles().items() if shutil.which(p.cmd[0])}
    if agent_id not in profiles:
        print(f"erro: agente {agent_id!r} não instalado/desconhecido")
        return 1
    sm = SessionManager(store)
    prompt = " ".join(prompt_words)
    res = asyncio.run(
        run_agent_in_floor(sm, profiles[agent_id], agent_id, prompt, floor, repo, timeout=180)
    )
    committed = commit_floor(floor, f"floor {floor.name}: {prompt[:50]}")
    print(f"agente {agent_id}: {res.status}; commit={'sim' if committed else '(nada a commitar)'}")
    return 0 if str(res.status) == "OK" else 1
