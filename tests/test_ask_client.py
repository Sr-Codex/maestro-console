"""Testes da ponte sandbox (Fase 2): cliente maestro-ask + setenv + wiring (ADR-11)."""

import ast

import pytest

from maestro.engine.ask_bus import AskBus, AskResponse, install_client
from maestro.engine.ask_client import ask, main
from maestro.engine.sandbox import bwrap_available
from maestro.engine.sandbox import wrap as sandbox_wrap
from maestro.native.agents import agent_argv


def test_ask_roundtrip(tmp_path):
    bus = tmp_path / "bus"
    bus.mkdir()
    estado = {}

    def host_responde(_delay):  # simula o host respondendo na 1ª espera
        if "ok" in estado:
            return
        reqs = list(bus.glob("req-*.json"))
        if reqs:
            rid = reqs[0].name[len("req-") : -len(".json")]
            (bus / f"resp-{rid}.json").write_text(
                '{"id":"%s","ok":true,"answer":"42"}' % rid, encoding="utf-8"
            )
            estado["ok"] = True

    resp = ask(str(bus), "A", "B", "oi", sleep=host_responde)
    assert resp["ok"] and resp["answer"] == "42"


def test_compat_client_req_lido_e_resp_escrita_pelo_askbus(tmp_path):
    # prova que o cliente (stdlib) e o AskBus (engine) falam o MESMO protocolo
    bus_dir = str(tmp_path / "bus")
    bus = AskBus(bus_dir)
    cap = {}

    def host(_delay):
        if "ok" in cap:
            return
        pend = bus.pending_requests()  # AskBus LÊ o req do cliente
        if pend:
            cap["req"] = pend[0]
            bus.write_response(AskResponse(id=pend[0].id, ok=True, answer="ok!"))
            cap["ok"] = True

    resp = ask(bus_dir, "A", "B", "revise foo.py", sleep=host)
    assert cap["req"].frm == "A" and cap["req"].prompt == "revise foo.py"
    assert resp["ok"] and resp["answer"] == "ok!"  # cliente LÊ a resp do AskBus


def test_ask_timeout(tmp_path):
    ticks = iter([0, 1, 2, 3, 1000])  # deadline=5; última leitura passa do prazo
    resp = ask(
        str(tmp_path / "bus"),
        "A",
        "B",
        "oi",
        timeout=5,
        sleep=lambda _d: None,
        clock=lambda: next(ticks),
    )
    assert not resp["ok"] and "timeout" in resp["error"]


def test_main_sem_env_recusa():
    assert main(["B", "oi"], env={}) == 2  # falta MAESTRO_NODE/MAESTRO_ASK_BUS


def test_main_args_insuficientes():
    assert main(["B"], env={"MAESTRO_NODE": "A", "MAESTRO_ASK_BUS": "/x"}) == 2


def test_install_client_copia_executavel_valido(tmp_path):
    dest = install_client(tmp_path / "bus")
    assert dest.name == "maestro-ask" and dest.exists()
    assert dest.stat().st_mode & 0o111  # executável
    ast.parse(dest.read_text(encoding="utf-8"))  # é Python válido


@pytest.mark.skipif(not bwrap_available(), reason="bwrap ausente")
def test_wrap_emite_setenv():
    argv = sandbox_wrap(["x"], workspace="/tmp", setenv={"MAESTRO_NODE": "A"})
    assert "--setenv" in argv
    i = argv.index("--setenv")
    assert argv[i + 1] == "MAESTRO_NODE" and argv[i + 2] == "A"


@pytest.mark.skipif(not bwrap_available(), reason="bwrap ausente")
def test_agent_argv_monta_mailbox_e_env(tmp_path):
    bus = tmp_path / "bus"
    bus.mkdir()

    class _Prof:
        cmd = ["/bin/sh"]
        rw_paths = []

    argv = agent_argv(_Prof(), str(tmp_path / "ws"), node="A", ask_bus_dir=str(bus))
    joined = " ".join(argv)
    assert "MAESTRO_NODE" in argv and str(bus.resolve()) in joined
    assert "MAESTRO_ASK_BUS" in argv
    # mailbox no PATH -> agente chama 'maestro-ask' direto (sem caminho absoluto)
    assert "PATH" in argv and any(a.startswith(f"{bus}:") for a in argv)
