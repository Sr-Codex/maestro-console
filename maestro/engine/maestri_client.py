#!/usr/bin/env python3
"""maestri — CLI de Maestro mode (sub-orquestração), roda DENTRO do sandbox bwrap.

Stdlib-only DE PROPÓSITO (dentro do bwrap o pacote ``maestro`` pode não importar).
Fala com o host por um **socket Unix pathname** em ``$MAESTRO_ASK_BUS/sock`` (ADR-17):
a identidade do remetente é o CANAL (qual socket), não um campo — o host ignora o
``frm`` do payload. O host instala uma cópia deste arquivo como ``<bus>/bin/maestri``.

Uso (o agente-manager chama via Bash):
    maestri recruit <agente> [papel]
    maestri list
    maestri reassign <nó> <papel>
    maestri wire <a> [b]
    maestri dismiss <nó>

Lê do ambiente: MAESTRO_NODE (rótulo de debug) e MAESTRO_ASK_BUS (a box do agente).
"""

from __future__ import annotations

import json
import os
import socket
import struct
import sys
import uuid

DEFAULT_TIMEOUT = 60.0
SOCK_NAME = "sock"
_MAX = 1 << 16


def _send_msg(conn: socket.socket, obj: dict) -> None:
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    conn.sendall(struct.pack(">I", len(data)) + data)


def _recv_exact(conn: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise OSError("conexão fechada no meio do frame")
        buf += chunk
    return bytes(buf)


def _recv_msg(conn: socket.socket) -> dict:
    (n,) = struct.unpack(">I", _recv_exact(conn, 4))
    if n > _MAX:
        raise OSError("frame grande demais")
    return json.loads(_recv_exact(conn, n).decode("utf-8"))


def run_cmd(
    bus_dir: str,
    frm: str,
    cmd: str,
    args: list[str],
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """Conecta em ``<bus_dir>/sock``, envia o comando e devolve a resposta do host."""
    rid = uuid.uuid4().hex
    req = {"id": rid, "frm": frm, "to": "", "prompt": "", "depth": 0, "cmd": cmd, "args": args}
    path = os.path.join(bus_dir, SOCK_NAME)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(path)
            _send_msg(s, req)
            return _recv_msg(s)
    except (OSError, json.JSONDecodeError) as e:
        return {"id": rid, "ok": False, "error": f"sem resposta do host: {e}"}


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
