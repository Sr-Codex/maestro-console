#!/usr/bin/env python3
"""maestro-ask — cliente do modo interativo de cabos, roda DENTRO do sandbox bwrap.

Stdlib-only DE PROPÓSITO: dentro do bwrap o pacote ``maestro`` pode não importar.
Fala com o host por um **socket Unix pathname** em ``$MAESTRO_ASK_BUS/sock`` (ADR-17):
a identidade do remetente é o CANAL (qual socket), não um campo. O host instala uma
cópia deste arquivo como ``<bus>/bin/maestro-ask`` (executável).

Uso (o agente chama via Bash):
    maestro-ask <nó-destino> "<prompt>"

Lê do ambiente:
    MAESTRO_NODE     — rótulo de debug do remetente (a identidade real vem do canal)
    MAESTRO_ASK_BUS  — a box do agente (contém o socket ``sock``)
"""

from __future__ import annotations

import json
import os
import socket
import struct
import sys
import uuid

DEFAULT_TIMEOUT = 180.0
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


def ask(
    bus_dir: str,
    frm: str,
    to: str,
    prompt: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """Conecta em ``<bus_dir>/sock``, envia o pedido ao nó ``to`` e devolve a resposta."""
    rid = uuid.uuid4().hex
    req = {"id": rid, "frm": frm, "to": to, "prompt": prompt, "depth": 0}
    path = os.path.join(bus_dir, SOCK_NAME)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(path)
            _send_msg(s, req)
            return _recv_msg(s)
    except (OSError, json.JSONDecodeError) as e:
        return {"id": rid, "ok": False, "error": f"sem resposta do host: {e}"}


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
    try:
        timeout = float(env.get("MAESTRO_ASK_TIMEOUT", DEFAULT_TIMEOUT))
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT
    resp = ask(bus, frm, to, prompt, timeout=timeout)
    if resp.get("ok"):
        print(f"Answer from {to}:\n{resp.get('answer', '')}")
        return 0
    print(f"[maestro-ask] erro: {resp.get('error')}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
