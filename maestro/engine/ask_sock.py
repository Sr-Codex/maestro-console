"""Transporte de IPC por SOCKET Unix *pathname*, um listener por agente (ADR-17).

**Identidade por canal (kernel-backed, infalsificável):** o host cria UM listener
por agente em ``<box>/sock`` — um *pathname socket* dentro da box que é bind-montada
**só** naquele agente. A identidade do remetente vem de **qual listener aceitou a
conexão**, não de um campo que o agente preenche. O host **ignora** qualquer ``frm``
do payload e carimba o nó dono do listener.

**Por que pathname e NÃO abstract socket:** abstract sockets (``\\0nome``) vivem no
*network namespace* — que os agentes compartilham (eles têm rede) → seriam visíveis a
todos e spoofáveis. O *pathname* vive no *filesystem*; o bind-mount por-agente o isola
(a box de um agente não existe no namespace de mount do outro). A segurança vem da
**ausência do mount**, não de permissão — ver ADR-17.

Stdlib puro (sem ``gi``) → testável no ``.venv``. O host roda :meth:`SockServer.serve`
numa thread daemon; cada conexão é curta (1 req → 1 resp) e tratada numa thread própria,
porque o ``handle`` pode bloquear (round-trip até a main-thread via ``idle_add``).
"""

from __future__ import annotations

import json
import os
import selectors
import socket
import struct
import threading
from collections.abc import Callable

SOCK_NAME = "sock"  # nome do socket dentro de cada box: <box>/sock
MAX_MSG_BYTES = 1 << 16  # teto de frame (64 KiB); a validação de conteúdo é à parte
_CONN_TIMEOUT = 30.0  # tempo máx. p/ ler um req / escrever um resp numa conexão


class SockError(Exception):
    """Falha de protocolo no transporte (frame inválido, conexão cortada, etc.)."""


def sock_path(box_dir: str | os.PathLike) -> str:
    """Caminho do socket dentro da box de um agente."""
    return os.path.join(str(box_dir), SOCK_NAME)


# -- framing: 4 bytes big-endian (tamanho) + JSON UTF-8 --------------------------
def _send_msg(conn: socket.socket, obj: dict) -> None:
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    if len(data) > MAX_MSG_BYTES:
        raise SockError("mensagem grande demais")
    conn.sendall(struct.pack(">I", len(data)) + data)


def _recv_exact(conn: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise SockError("conexão fechada no meio do frame")
        buf += chunk
    return bytes(buf)


def _recv_msg(conn: socket.socket) -> dict:
    (n,) = struct.unpack(">I", _recv_exact(conn, 4))
    if n > MAX_MSG_BYTES:
        raise SockError("frame grande demais")
    obj = json.loads(_recv_exact(conn, n).decode("utf-8"))
    if not isinstance(obj, dict):
        raise SockError("payload não é objeto JSON")
    return obj


# -- cliente (referência p/ testes; os shims duplicam isto inline em stdlib) ------
def send_request(path: str, req: dict, *, timeout: float = 25.0) -> dict:
    """Conecta no socket ``path``, envia ``req`` e devolve a resposta (1 round-trip)."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(path)
        _send_msg(s, req)
        return _recv_msg(s)


# -- servidor (host) -------------------------------------------------------------
Handler = Callable[[str, dict], dict]  # (nó_do_canal, req) -> resp


class SockServer:
    """Mantém um listener pathname por agente; identidade = listener que aceitou.

    Uso (host)::

        srv = SockServer()
        srv.add_node("mgr", box_dir)                 # cria <box>/sock
        threading.Thread(target=srv.serve, args=(handle,), daemon=True).start()
        ...
        srv.remove_node("mgr"); srv.stop()

    ``handle(node, req)`` roda na thread do servidor; o ``node`` é a identidade
    confiável (derivada do canal). O payload pode trazer um ``frm`` — é ignorado.
    """

    def __init__(self) -> None:
        self._sel = selectors.DefaultSelector()
        self._listeners: dict[str, tuple[socket.socket, str]] = {}
        self._lock = threading.Lock()
        self._stop = False
        # socketpair p/ acordar o select() ao adicionar/remover nó de outra thread
        self._wake_r, self._wake_w = socket.socketpair()
        self._sel.register(self._wake_r, selectors.EVENT_READ, ("_wake", ""))

    def add_node(self, node: str, box_dir: str | os.PathLike) -> str:
        """Cria/escuta ``<box_dir>/sock`` e associa ao ``node``. Retorna o caminho."""
        path = sock_path(box_dir)
        try:
            os.unlink(path)  # remove um socket órfão de um spawn anterior
        except FileNotFoundError:
            pass
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(path)
        os.chmod(path, 0o600)  # defesa-em-profundidade (isolamento real é o bind-mount)
        srv.listen(16)
        srv.setblocking(False)
        with self._lock:
            old = self._listeners.pop(node, None)
            self._listeners[node] = (srv, path)
        if old is not None:
            self._close_listener(*old)
        self._sel.register(srv, selectors.EVENT_READ, ("listen", node))
        self._wake()
        return path

    def remove_node(self, node: str) -> None:
        """Fecha e remove o listener do ``node`` (ao dispensar/fechar o agente)."""
        with self._lock:
            entry = self._listeners.pop(node, None)
        if entry is not None:
            try:
                self._sel.unregister(entry[0])
            except (KeyError, ValueError):
                pass
            self._close_listener(*entry)
        self._wake()

    def serve(self, handle: Handler) -> None:
        """Loop bloqueante (rode numa thread daemon). Aceita conexões e despacha."""
        while not self._stop:
            for key, _ in self._sel.select(timeout=1.0):
                kind, node = key.data
                if kind == "_wake":
                    try:
                        self._wake_r.recv(4096)
                    except OSError:
                        pass
                elif kind == "listen":
                    self._accept(key.fileobj, node, handle)

    def stop(self) -> None:
        self._stop = True
        self._wake()
        with self._lock:
            entries = list(self._listeners.values())
            self._listeners.clear()
        for srv, path in entries:
            try:
                self._sel.unregister(srv)
            except (KeyError, ValueError):
                pass
            self._close_listener(srv, path)
        try:
            self._wake_w.close()
            self._wake_r.close()
        except OSError:
            pass

    # -- internos --
    def _accept(self, srv: socket.socket, node: str, handle: Handler) -> None:
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        # conexão curta tratada numa thread própria: o handle pode bloquear (idle_add)
        threading.Thread(
            target=self._handle_conn, args=(conn, node, handle), daemon=True
        ).start()

    def _handle_conn(self, conn: socket.socket, node: str, handle: Handler) -> None:
        with conn:
            conn.settimeout(_CONN_TIMEOUT)
            try:
                req = _recv_msg(conn)
            except (SockError, OSError, json.JSONDecodeError, ValueError):
                return
            try:
                resp = handle(node, req)  # IDENTIDADE: node vem do canal, não do payload
                if not isinstance(resp, dict):
                    resp = {"ok": False, "error": "resposta inválida do host"}
            except Exception:  # noqa: BLE001 — nunca derruba o servidor por um req ruim
                resp = {"ok": False, "error": "erro interno no host"}
            try:
                _send_msg(conn, resp)
            except (SockError, OSError):
                pass

    def _wake(self) -> None:
        try:
            self._wake_w.send(b"x")
        except OSError:
            pass

    @staticmethod
    def _close_listener(srv: socket.socket, path: str) -> None:
        try:
            srv.close()
        except OSError:
            pass
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        except OSError:
            pass
