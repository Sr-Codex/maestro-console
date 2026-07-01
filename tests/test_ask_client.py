"""Testes da ponte sandbox: cliente maestro-ask por SOCKET (ADR-17) + setenv + wiring."""

import ast
import threading

import pytest

from maestro.engine.ask_bus import install_client
from maestro.engine.ask_client import ask, main
from maestro.engine.ask_sock import SockServer
from maestro.engine.sandbox import bwrap_available
from maestro.engine.sandbox import wrap as sandbox_wrap
from maestro.native.agents import agent_argv


def _serve(box_dir, node, handle) -> SockServer:
    srv = SockServer()
    srv.add_node(node, str(box_dir))
    threading.Thread(target=srv.serve, args=(handle,), daemon=True).start()
    return srv


def test_ask_roundtrip(tmp_path):
    box = tmp_path / "box"
    box.mkdir()
    srv = _serve(box, "A", lambda node, req: {"id": req.get("id"), "ok": True, "answer": "42"})
    try:
        resp = ask(str(box), "A", "B", "oi", timeout=5)
        assert resp["ok"] and resp["answer"] == "42"
    finally:
        srv.stop()


def test_identidade_vem_do_canal_e_protocolo(tmp_path):
    """O host recebe a identidade do CANAL (node), e o protocolo to/prompt chega certo."""
    box = tmp_path / "box"
    box.mkdir()
    cap: dict = {}

    def handle(node, req):
        cap["node"], cap["req"] = node, req
        return {"id": req.get("id"), "ok": True, "answer": "ok!"}

    srv = _serve(box, "A", handle)
    try:
        resp = ask(str(box), "A", "B", "revise foo.py", timeout=5)
        assert cap["node"] == "A"  # identidade = canal (não o frm do payload)
        assert cap["req"]["to"] == "B" and cap["req"]["prompt"] == "revise foo.py"
        assert resp["ok"] and resp["answer"] == "ok!"
    finally:
        srv.stop()


def test_ask_sem_host_devolve_erro(tmp_path):
    # sem socket no caminho -> conexão recusada -> erro (não trava nem levanta)
    resp = ask(str(tmp_path / "box"), "A", "B", "oi", timeout=1)
    assert not resp["ok"] and resp["error"]


def test_main_sem_env_recusa():
    assert main(["B", "oi"], env={}) == 2  # falta MAESTRO_NODE/MAESTRO_ASK_BUS


def test_main_args_insuficientes():
    assert main(["B"], env={"MAESTRO_NODE": "A", "MAESTRO_ASK_BUS": "/x"}) == 2


def test_install_client_copia_executavel_valido(tmp_path):
    dest = install_client(tmp_path / "bus")
    assert dest.name == "maestro-ask" and dest.exists()
    assert dest.parent.name == "bin"  # ADR-17: shims ficam em <bus>/bin (RO)
    assert dest.stat().st_mode & 0o111  # executável
    ast.parse(dest.read_text(encoding="utf-8"))  # é Python válido


@pytest.mark.skipif(not bwrap_available(), reason="bwrap ausente")
def test_wrap_emite_setenv(tmp_path):
    argv = sandbox_wrap(["x"], workspace=str(tmp_path), setenv={"MAESTRO_NODE": "A"})
    assert "--setenv" in argv
    i = argv.index("--setenv")
    assert argv[i + 1] == "MAESTRO_NODE" and argv[i + 2] == "A"


@pytest.mark.skipif(not bwrap_available(), reason="bwrap ausente")
def test_wrap_dropa_capabilities(tmp_path):
    argv = sandbox_wrap(["x"], workspace=str(tmp_path))
    assert "--cap-drop" in argv and argv[argv.index("--cap-drop") + 1] == "ALL"


@pytest.mark.skipif(not bwrap_available(), reason="bwrap ausente")
def test_agent_argv_monta_box_e_env(tmp_path):
    bus = tmp_path / "bus"
    bus.mkdir()

    class _Prof:
        cmd = ["/bin/sh"]
        rw_paths = []

    argv = agent_argv(_Prof(), str(tmp_path / "ws"), node="A", ask_bus_dir=str(bus))
    box = str(bus / "box" / "A")
    bindir = str(bus / "bin")
    # env: MAESTRO_ASK_BUS aponta p/ a BOX do agente; MAESTRO_BIN p/ os shims
    assert argv[argv.index("MAESTRO_ASK_BUS") + 1] == box
    assert argv[argv.index("MAESTRO_BIN") + 1] == bindir
    assert argv[argv.index("MAESTRO_NODE") + 1] == "A"
    # ADR-17: a box é criada (p/ o bind existir) e é SÓ ela que é montada (não o <bus> pai)
    assert (bus / "box" / "A").is_dir()
    assert any(a.startswith(f"{bindir}:") for a in argv)  # PATH começa pelo bin/
    assert str(bus) not in [
        a for i, a in enumerate(argv) if i and argv[i - 1] == "--bind"
    ]  # nenhum --bind do <bus> inteiro
    assert "/bin/bash" in argv and any("exec /bin/bash" in a for a in argv)


@pytest.mark.skipif(not bwrap_available(), reason="bwrap ausente")
def test_agent_argv_cai_no_shell_ao_sair_da_ia(tmp_path):
    class _Prof:
        cmd = ["claude"]
        rw_paths = []

    argv = agent_argv(_Prof(), str(tmp_path / "ws"))
    inner = argv[argv.index("--") + 1 :]  # comando após o '--' do bwrap
    assert inner == ["/bin/bash", "-c", "claude; exec /bin/bash -i"]
