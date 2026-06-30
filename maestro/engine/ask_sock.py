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
import time
from collections.abc import Callable

SOCK_NAME = "sock"  # nome do socket dentro de cada box: <box>/sock
MAX_MSG_BYTES = 1 << 16  # teto de frame (64 KiB); a validação de conteúdo é à parte
_CONN_TIMEOUT = 30.0  # DEADLINE ABSOLUTO p/ ler o req (não por-recv → mata slowloris, F2)
MAX_INFLIGHT = 32  # teto de conexões tratadas em paralelo (anti thread-DoS, F1)


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


def _recv_exact(conn: socket.socket, n: int, deadline: float | None = None) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        if deadline is not None:  # deadline ABSOLUTO (total), não por-recv → anti slowloris
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SockError("deadline de leitura excedido (slow-read)")
            conn.settimeout(remaining)
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise SockError("conexão fechada no meio do frame")
        buf += chunk
    return bytes(buf)


def _recv_msg(conn: socket.socket, deadline: float | None = None) -> dict:
    (n,) = struct.unpack(">I", _recv_exact(conn, 4, deadline))
    if n > MAX_MSG_BYTES:
        raise SockError("frame grande demais")
    obj = json.loads(_recv_exact(conn, n, deadline).decode("utf-8"))
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
        self._pending: list[tuple] = []  # ops p/ a thread do serve aplicar no selector
        self._lock = threading.Lock()  # protege _listeners e _pending (NÃO o selector)
        self._inflight = threading.BoundedSemaphore(MAX_INFLIGHT)  # teto de conexões (F1)
        self._stop = False
        # socketpair p/ acordar o select() ao adicionar/remover nó de outra thread
        self._wake_r, self._wake_w = socket.socketpair()
        # único register fora da thread do serve: aqui no init, antes do serve existir
        self._sel.register(self._wake_r, selectors.EVENT_READ, ("_wake", ""))

    def add_node(self, node: str, box_dir: str | os.PathLike) -> str:
        """Cria/escuta ``<box_dir>/sock`` e associa ao ``node``. Retorna o caminho.

        O socket é criado aqui (independe do selector), mas o ``register`` é ENFILEIRADO
        p/ a thread do serve — o selector da stdlib NÃO é thread-safe (F3/F4)."""
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
            if old is not None:  # F4: desregistra+fecha o antigo, mas SEM unlink — o path já
                self._pending.append(("close", old[0], old[1], False))  # pertence ao novo socket
            self._pending.append(("open", srv, node))
        self._wake()
        return path

    def nodes(self) -> list[str]:
        """Nós com listener ativo (= agentes vivos)."""
        with self._lock:
            return list(self._listeners.keys())

    def remove_node(self, node: str) -> None:
        """Fecha e remove o listener do ``node`` (ao dispensar/fechar o agente)."""
        with self._lock:
            entry = self._listeners.pop(node, None)
            if entry is not None:
                self._pending.append(("close", entry[0], entry[1], True))  # unlink: o nó saiu
        self._wake()

    def _drain_pending(self) -> None:
        """Aplica os register/unregister ENFILEIRADOS. Roda SÓ na thread do serve."""
        with self._lock:
            ops, self._pending = self._pending, []
        for op in ops:
            kind = op[0]
            if kind == "open":
                _, srv, node = op
                try:
                    self._sel.register(srv, selectors.EVENT_READ, ("listen", node))
                except (KeyError, ValueError):
                    pass
            elif kind == "close":
                _, srv, path, do_unlink = op
                try:
                    self._sel.unregister(srv)
                except (KeyError, ValueError):
                    pass
                self._close_listener(srv, path if do_unlink else None)

    def serve(self, handle: Handler) -> None:
        """Loop bloqueante (rode numa thread daemon). SÓ esta thread toca o selector."""
        while not self._stop:
            self._drain_pending()  # aplica add/remove pendentes ANTES do select
            for key, _ in self._sel.select(timeout=1.0):
                kind, node = key.data
                if kind == "_wake":
                    try:
                        self._wake_r.recv(4096)
                    except OSError:
                        pass
                elif kind == "listen":
                    self._accept(key.fileobj, node, handle)
        self._drain_pending()  # processa os closes pendentes do stop()

    def stop(self) -> None:
        """Desliga (shutdown). Fecha os sockets diretamente — fechar um fd NÃO muta o dict
        do selector (o kernel o tira do epoll), então não reintroduz a corrida do F3."""
        self._stop = True
        self._wake()
        with self._lock:
            entries = list(self._listeners.values())
            self._listeners.clear()
            self._pending.clear()
        for srv, path in entries:
            self._close_listener(srv, path)

    # -- internos --
    def _accept(self, srv: socket.socket, node: str, handle: Handler) -> None:
        try:
            conn, _ = srv.accept()
        except OSError:
            return
        if not self._inflight.acquire(blocking=False):  # saturado: fast-fail (anti DoS, F1)
            try:
                conn.close()
            except OSError:
                pass
            return
        # conexão curta tratada numa thread própria: o handle pode bloquear (idle_add)
        threading.Thread(
            target=self._handle_conn, args=(conn, node, handle), daemon=True
        ).start()

    def _handle_conn(self, conn: socket.socket, node: str, handle: Handler) -> None:
        try:
            with conn:
                deadline = time.monotonic() + _CONN_TIMEOUT  # deadline absoluto p/ ler o req
                try:
                    req = _recv_msg(conn, deadline=deadline)
                except (SockError, OSError, json.JSONDecodeError, ValueError):
                    return
                try:
                    resp = handle(node, req)  # IDENTIDADE: node vem do canal, não do payload
                    if not isinstance(resp, dict):
                        resp = {"ok": False, "error": "resposta inválida do host"}
                except Exception:  # noqa: BLE001 — nunca derruba o servidor por um req ruim
                    resp = {"ok": False, "error": "erro interno no host"}
                try:
                    conn.settimeout(_CONN_TIMEOUT)  # teto também p/ a escrita da resposta
                    _send_msg(conn, resp)
                except (SockError, OSError):
                    pass
        finally:
            self._inflight.release()  # devolve o permite, sempre (F1)

    def _wake(self) -> None:
        try:
            self._wake_w.send(b"x")
        except OSError:
            pass

    @staticmethod
    def _close_listener(srv: socket.socket, path: str | None) -> None:
        """Fecha o fd; só faz unlink se ``path`` for dado (None = o path pertence a outro
        socket, ex.: substituição de listener no respawn — fechar o fd, não apagar o arquivo)."""
        try:
            srv.close()
        except OSError:
            pass
        if path is None:
            return
        try:
            os.unlink(path)
        except (FileNotFoundError, OSError):
            pass
