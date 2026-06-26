#!/usr/bin/env python3
"""maestro-ask — cliente do modo interativo de cabos, roda DENTRO do sandbox bwrap.

Stdlib-only DE PROPÓSITO: dentro do bwrap o pacote ``maestro`` pode não estar
importável. Mantém o MESMO protocolo de arquivos do ``engine.ask_bus`` (req/resp
JSON). O host instala uma cópia deste arquivo como ``<bus>/maestro-ask`` (executável).

Uso (o agente chama via Bash):
    maestro-ask <nó-destino> "<prompt>"

Lê do ambiente:
    MAESTRO_NODE     — o nó remetente (quem está perguntando)
    MAESTRO_ASK_BUS  — diretório do mailbox (montado rw no sandbox)
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid

POLL = 0.25
DEFAULT_TIMEOUT = 180.0


def ask(
    bus_dir: str,
    frm: str,
    to: str,
    prompt: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    poll: float = POLL,
    sleep=time.sleep,
    clock=time.monotonic,
) -> dict:
    """Escreve req-<id>.json e aguarda resp-<id>.json. Retorna o dict da resposta."""
    rid = uuid.uuid4().hex
    os.makedirs(bus_dir, exist_ok=True)
    req = {"id": rid, "frm": frm, "to": to, "prompt": prompt, "depth": 0}
    req_path = os.path.join(bus_dir, f"req-{rid}.json")
    tmp = req_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(req, f, ensure_ascii=False)
    os.replace(tmp, req_path)  # escrita atômica (host nunca lê pedido parcial)

    resp_path = os.path.join(bus_dir, f"resp-{rid}.json")
    deadline = clock() + timeout
    while clock() < deadline:
        if os.path.exists(resp_path):
            try:
                with open(resp_path, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                pass  # ainda sendo escrito; tenta de novo
        sleep(poll)
    return {"id": rid, "ok": False, "error": "timeout esperando resposta"}


def main(argv: list[str] | None = None, env: dict | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    env = dict(os.environ) if env is None else env
    if len(argv) < 2:
        print('uso: maestro-ask <nó> "<prompt>"', file=sys.stderr)
        return 2
    to, prompt = argv[0], argv[1]
    frm = env.get("MAESTRO_NODE", "")
    bus = env.get("MAESTRO_ASK_BUS", "")
    if not frm or not bus:
        print(
            "MAESTRO_NODE/MAESTRO_ASK_BUS ausentes — este cabo não está configurado.",
            file=sys.stderr,
        )
        return 2
    resp = ask(bus, frm, to, prompt)
    if resp.get("ok"):
        print(f"Answer from {to}:\n{resp.get('answer', '')}")
        return 0
    print(f"[maestro-ask] erro: {resp.get('error')}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
