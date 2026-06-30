#!/usr/bin/env python3
"""maestri — CLI de Maestro mode (sub-orquestração), roda DENTRO do sandbox bwrap.

Stdlib-only DE PROPÓSITO (dentro do bwrap o pacote ``maestro`` pode não importar).
Mesmo mailbox/protocolo do ``engine.ask_bus`` (req/resp JSON), mas com ``cmd``/``args``.
O host instala uma cópia deste arquivo como ``<bus>/maestri`` (executável).

Uso (o agente-manager chama via Bash):
    maestri recruit <agente> [papel]
    maestri list
    maestri reassign <nó> <papel>
    maestri wire <a> [b]
    maestri dismiss <nó>

Lê do ambiente: MAESTRO_NODE (o manager) e MAESTRO_ASK_BUS (mailbox).
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid

POLL = 0.25
DEFAULT_TIMEOUT = 60.0


def run_cmd(
    bus_dir: str,
    frm: str,
    cmd: str,
    args: list[str],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    poll: float = POLL,
    sleep=time.sleep,
    clock=time.monotonic,
) -> dict:
    """Escreve req-<id>.json (com cmd/args) e aguarda resp-<id>.json. Devolve o dict."""
    rid = uuid.uuid4().hex
    os.makedirs(bus_dir, exist_ok=True)
    req = {"id": rid, "frm": frm, "to": "", "prompt": "", "depth": 0, "cmd": cmd, "args": args}
    req_path = os.path.join(bus_dir, f"req-{rid}.json")
    tmp = req_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(req, f, ensure_ascii=False)
    os.replace(tmp, req_path)  # escrita atômica

    resp_path = os.path.join(bus_dir, f"resp-{rid}.json")
    deadline = clock() + timeout
    while clock() < deadline:
        if os.path.exists(resp_path):
            try:
                with open(resp_path, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                pass
        sleep(poll)
    return {"id": rid, "ok": False, "error": "timeout esperando resposta"}


_USAGE = "uso: maestri <recruit|list|reassign|wire|dismiss> [args...]"


def main(argv: list[str] | None = None, env: dict | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    env = dict(os.environ) if env is None else env
    if not argv:
        print(_USAGE, file=sys.stderr)
        return 2
    cmd, args = argv[0], argv[1:]
    frm = env.get("MAESTRO_NODE", "")
    bus = env.get("MAESTRO_ASK_BUS", "")
    if not frm or not bus:
        print("MAESTRO_NODE/MAESTRO_ASK_BUS ausentes — Maestro mode não configurado.",
              file=sys.stderr)
        return 2
    resp = run_cmd(bus, frm, cmd, args)
    if resp.get("ok"):
        print(resp.get("answer", "ok"))
        return 0
    print(f"[maestri] erro: {resp.get('error')}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
