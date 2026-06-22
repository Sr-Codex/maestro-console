"""CLI `maestro routine` — add/list/rm/run/enable/disable/serve (V10-S3).

Multi-step: o prompt pode conter ` && ` para virar passos sequenciais. Routines
são referenciadas por id ou por nome. `run`/`serve` precisam do controller
(injetável p/ testes; senão build_controller). Lógica testável (sem GTK).
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .engine.routines import Routines, run_routine_once
from .engine.scheduler import serve as scheduler_serve
from .engine.state.store import Store

_NEEDS_REF = {"rm", "run", "enable", "disable"}
_NEEDS_CTRL = {"run", "serve"}


def _build_parser(home_default) -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--home", default=home_default, help="MAESTRO_HOME (estado)")

    p = argparse.ArgumentParser(prog="maestro routine", description="prompts agendados")
    sub = p.add_subparsers(dest="action", required=True)
    a = sub.add_parser("add", parents=[common], help="cria uma routine")
    a.add_argument("name")
    a.add_argument("agent")
    a.add_argument("prompt", nargs="+", help="prompt; use ' && ' p/ multi-step")
    a.add_argument("--interval", type=float, default=600.0, help="intervalo em segundos")
    sub.add_parser("list", parents=[common], help="lista routines")
    for act in ("rm", "run", "enable", "disable"):
        s = sub.add_parser(act, parents=[common], help=f"{act} routine (por id ou nome)")
        s.add_argument("ref")
    sv = sub.add_parser("serve", parents=[common], help="roda o scheduler (dispara as vencidas)")
    sv.add_argument("--interval", type=float, default=5.0, help="segundos entre ticks")
    sv.add_argument("--ticks", type=int, default=None, help="parar após N ticks")
    return p


def _resolve(routines: Routines, ref: str):
    if routines.get(ref) is not None:
        return routines.get(ref)
    for r in routines.list():
        if r.name == ref:
            return r
    return None


def routine_cli(argv: list[str], *, home: str | Path | None = None, controller=None) -> int:
    args = _build_parser(home).parse_args(argv)
    base = Path(args.home) if args.home else None
    from .bootstrap import default_home

    base = base or default_home()
    if args.action in _NEEDS_CTRL and controller is None:
        from .bootstrap import build_controller

        controller, store = build_controller(home=base)
    else:
        store = Store(base / "maestro.db")
    routines = Routines(store)
    try:
        return _dispatch(args, routines, controller)
    finally:
        store.close()


def _dispatch(args, routines: Routines, controller) -> int:
    if args.action == "add":
        steps = [s.strip() for s in " ".join(args.prompt).split(" && ") if s.strip()]
        r = routines.create(args.name, args.agent, steps, args.interval)
        print(f"routine {r.name!r} criada (id {r.id}, {len(steps)} passo(s), {r.interval_s:.0f}s)")
        return 0
    if args.action == "list":
        rs = routines.list()
        if not rs:
            print("(nenhuma routine)")
        for r in rs:
            on = "on" if r.enabled else "off"
            print(f"{r.id}\t{r.name}\t{r.agent}\t{r.interval_s:.0f}s\t[{on}]\truns={r.run_count}")
        return 0

    if args.action in _NEEDS_REF:
        r = _resolve(routines, args.ref)
        if r is None:
            print(f"erro: routine {args.ref!r} não encontrada")
            return 1
        if args.action == "rm":
            routines.delete(r.id)
            print(f"routine {r.name!r} removida")
            return 0
        if args.action in ("enable", "disable"):
            routines.set_enabled(r.id, args.action == "enable")
            print(f"routine {r.name!r} {'habilitada' if args.action == 'enable' else 'pausada'}")
            return 0
        if args.action == "run":
            run = asyncio.run(run_routine_once(controller, r, routines))
            status = "OK" if run.ok else f"parou no passo {run.stopped_at}"
            print(f"routine {r.name!r}: {status} ({len(run.envelopes)} passo(s))")
            return 0 if run.ok else 1

    if args.action == "serve":
        print(f"scheduler ativo (tick {args.interval:.0f}s) — Ctrl-C p/ sair")
        ticks = asyncio.run(
            scheduler_serve(controller, routines, interval_s=args.interval, max_ticks=args.ticks)
        )
        print(f"scheduler encerrado ({ticks} tick(s))")
        return 0
    return 0
