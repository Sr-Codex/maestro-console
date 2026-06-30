"""Testes do transporte por socket (ADR-17) — identidade por canal, gi-free (.venv).

O ponto central: o host carimba o remetente a partir de QUAL listener aceitou a
conexão; um payload com ``frm`` forjado é ignorado. Prova o anti-spoofing sem GTK.
"""

from __future__ import annotations

import threading
import time

import pytest

from maestro.engine.ask_sock import SockError, SockServer, send_request, sock_path


def _serve(srv: SockServer, handle) -> threading.Thread:
    t = threading.Thread(target=srv.serve, args=(handle,), daemon=True)
    t.start()
    return t


def test_identidade_vem_do_canal_nao_do_payload(tmp_path):
    """Pedido com frm='B' chegando pelo socket de A é tratado como A (spoof neutralizado)."""
    box_a = tmp_path / "A"
    box_b = tmp_path / "B"
    box_a.mkdir()
    box_b.mkdir()
    srv = SockServer()
    srv.add_node("A", str(box_a))
    srv.add_node("B", str(box_b))

    seen: list[tuple[str, dict]] = []

    def handle(node, req):
        seen.append((node, req))
        return {"ok": True, "as_node": node}

    _serve(srv, handle)
    try:
        # cliente de A tenta se passar por B no payload
        resp = send_request(sock_path(box_a), {"frm": "B", "cmd": "recruit", "args": ["codex"]})
        assert resp["ok"] and resp["as_node"] == "A"  # host usou o CANAL, não o frm
        assert seen[0][0] == "A"  # o handle recebeu a identidade real
        # cliente de B é tratado como B
        resp_b = send_request(sock_path(box_b), {"frm": "A", "cmd": "list"})
        assert resp_b["as_node"] == "B"
    finally:
        srv.stop()


def test_roundtrip_normal_e_resposta(tmp_path):
    box = tmp_path / "n"
    box.mkdir()
    srv = SockServer()
    srv.add_node("n", str(box))
    _serve(srv, lambda node, req: {"ok": True, "echo": req.get("cmd", "")})
    try:
        resp = send_request(sock_path(box), {"cmd": "list", "args": []})
        assert resp == {"ok": True, "echo": "list"}
    finally:
        srv.stop()


def test_remove_node_fecha_socket(tmp_path):
    box = tmp_path / "n"
    box.mkdir()
    srv = SockServer()
    path = srv.add_node("n", str(box))
    _serve(srv, lambda node, req: {"ok": True})
    try:
        assert send_request(path, {"cmd": "x"})["ok"]
        srv.remove_node("n")
        time.sleep(0.05)
        with pytest.raises((ConnectionRefusedError, FileNotFoundError, OSError)):
            send_request(path, {"cmd": "x"}, timeout=1.0)
    finally:
        srv.stop()


def test_handler_que_explode_nao_derruba_servidor(tmp_path):
    box = tmp_path / "n"
    box.mkdir()
    srv = SockServer()
    srv.add_node("n", str(box))

    def handle(node, req):
        if req.get("cmd") == "boom":
            raise RuntimeError("erro de propósito")
        return {"ok": True}

    _serve(srv, handle)
    try:
        # o pedido que explode recebe erro, mas o servidor segue vivo
        bad = send_request(sock_path(box), {"cmd": "boom"})
        assert bad["ok"] is False and "erro" in bad["error"]
        assert send_request(sock_path(box), {"cmd": "ok"})["ok"] is True
    finally:
        srv.stop()


def test_concorrencia_varias_conexoes(tmp_path):
    box = tmp_path / "n"
    box.mkdir()
    srv = SockServer()
    srv.add_node("n", str(box))
    _serve(srv, lambda node, req: {"ok": True, "i": req.get("i")})
    results: dict[int, dict] = {}
    try:

        def call(i):
            results[i] = send_request(sock_path(box), {"cmd": "x", "i": i})

        threads = [threading.Thread(target=call, args=(i,)) for i in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert len(results) == 12
        assert all(r["ok"] and r["i"] == i for i, r in results.items())
    finally:
        srv.stop()


def test_frame_grande_demais_rejeitado(tmp_path):
    box = tmp_path / "n"
    box.mkdir()
    srv = SockServer()
    srv.add_node("n", str(box))
    _serve(srv, lambda node, req: {"ok": True})
    try:
        with pytest.raises(SockError):
            send_request(sock_path(box), {"cmd": "x", "blob": "z" * (1 << 17)})
    finally:
        srv.stop()
