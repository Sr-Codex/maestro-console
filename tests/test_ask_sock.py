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


def test_add_node_substitui_sem_crashar(tmp_path):
    """F4: re-add do mesmo nó (respawn) desregistra+fecha o antigo sem KeyError; novo atende."""
    box = tmp_path / "n"
    box.mkdir()
    srv = SockServer()
    srv.add_node("n", str(box))
    _serve(srv, lambda node, req: {"ok": True})
    try:
        assert send_request(sock_path(box), {"cmd": "x"})["ok"]
        srv.add_node("n", str(box))  # re-registro do MESMO nó (fd pode reciclar)
        time.sleep(0.15)  # deixa a thread do serve drenar close+open
        assert send_request(sock_path(box), {"cmd": "x"})["ok"]  # novo listener funciona
        assert srv.nodes() == ["n"]
    finally:
        srv.stop()


def test_add_remove_concorrente_nao_derruba_o_serve(tmp_path):
    """F3: add/remove de outra thread enquanto o serve roda — sem race no selector; servidor
    continua aceitando depois."""
    srv = SockServer()
    _serve(srv, lambda node, req: {"ok": True})
    try:
        for i in range(20):
            b = tmp_path / f"n{i}"
            b.mkdir()
            srv.add_node(f"n{i}", str(b))
        time.sleep(0.25)
        assert len(srv.nodes()) == 20
        for i in range(20):
            srv.remove_node(f"n{i}")
        time.sleep(0.25)
        assert srv.nodes() == []
        # o serve sobreviveu: um nó novo ainda atende
        final = tmp_path / "final"
        final.mkdir()
        srv.add_node("final", str(final))
        time.sleep(0.15)
        assert send_request(sock_path(final), {"cmd": "x"})["ok"]
    finally:
        srv.stop()


def test_slow_read_corta_no_deadline(tmp_path, monkeypatch):
    """F2: cliente que anuncia N bytes e manda 1 (slowloris) é cortado no deadline ABSOLUTO;
    o servidor sobrevive e segue atendendo."""
    import socket as _s
    import struct as _st

    monkeypatch.setattr("maestro.engine.ask_sock._CONN_TIMEOUT", 0.4)
    box = tmp_path / "n"
    box.mkdir()
    srv = SockServer()
    srv.add_node("n", str(box))
    _serve(srv, lambda node, req: {"ok": True})
    try:
        c = _s.socket(_s.AF_UNIX, _s.SOCK_STREAM)
        c.connect(sock_path(box))
        c.sendall(_st.pack(">I", 1000))  # anuncia 1000 bytes...
        c.sendall(b"x")  # ...manda 1 e PARA
        time.sleep(0.8)  # passa do deadline (0.4s) → servidor corta a conexão
        c.close()
        assert send_request(sock_path(box), {"cmd": "ok"})["ok"]  # servidor segue vivo
    finally:
        srv.stop()


def test_teto_de_conexoes_recusa_excesso(tmp_path, monkeypatch):
    """F1: com o teto saturado, conexões novas são fast-closed (anti thread-DoS)."""
    import maestro.engine.ask_sock as mod

    monkeypatch.setattr(mod, "MAX_INFLIGHT", 1)
    box = tmp_path / "n"
    box.mkdir()
    block = threading.Event()

    def handle(node, req):
        block.wait(3.0)  # segura o ÚNICO permite ocupado
        return {"ok": True}

    srv = SockServer()
    srv.add_node("n", str(box))
    _serve(srv, handle)
    first: dict = {}
    try:
        t1 = threading.Thread(
            target=lambda: first.update(r=send_request(sock_path(box), {"cmd": "1"}, timeout=4)),
            daemon=True,
        )
        t1.start()
        time.sleep(0.3)  # garante a 1ª conexão dentro do handle (permite tomado)
        with pytest.raises((SockError, OSError)):  # 2ª: saturado → fast-close → erro
            send_request(sock_path(box), {"cmd": "2"}, timeout=2)
        block.set()
        t1.join(3)
        assert first.get("r", {}).get("ok")  # a 1ª completou normalmente
    finally:
        block.set()
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
