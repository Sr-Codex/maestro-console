"""Provas de RUNTIME do Maestro mode seguro (ADR-17) — regressão contínua, não script avulso.

Estas antes eram scripts manuais (o revisor de conduta apontou: prova em PDF = teatro).
Agora são testes: só precisam de **bwrap** (sem agente/tokens), então rodam sempre que o
bwrap existe. Provam o que os testes com mocks NÃO conseguem:
- identidade-por-canal ATRAVÉS de um bind-mount bwrap real (não mock de socket);
- o kill-switch COLAPSANDO a subárvore de um bwrap real (SIGKILL via pidfd).
"""

from __future__ import annotations

import glob
import json
import os
import signal
import subprocess
import threading
import time

import pytest

from maestro.engine.ask_sock import SockServer, sock_path
from maestro.engine.sandbox import bwrap_available

pytestmark = pytest.mark.skipif(not bwrap_available(), reason="live: requer bwrap")

_BWRAP_BASE = ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
               "--tmpfs", "/tmp", "--unshare-pid", "--die-with-parent", "--cap-drop", "ALL"]


def test_socket_atravessa_bwrap_e_identidade_por_canal(tmp_path):
    """Um cliente DENTRO de um bwrap real (box bind RW + cap-drop ALL) conecta no
    <box>/sock por caminho; o host carimba a identidade do CANAL e IGNORA o frm forjado."""
    box = tmp_path / "bus" / "box" / "A"
    box.mkdir(parents=True)
    srv = SockServer()
    srv.add_node("A", str(box))
    seen: dict = {}

    def handle(node, req):
        seen["node"], seen["frm"] = node, req.get("frm")
        return {"ok": True, "as_node": node, "id": req.get("id")}

    threading.Thread(target=srv.serve, args=(handle,), daemon=True).start()
    try:
        client = (
            "import socket,struct,json\n"
            "s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.settimeout(5)\n"
            f"s.connect({sock_path(box)!r})\n"
            'd=json.dumps({"id":"x1","frm":"EVIL","cmd":"list","args":[]}).encode()\n'
            's.sendall(struct.pack(">I",len(d))+d)\n'
            'n=struct.unpack(">I",s.recv(4))[0]; print(s.recv(n).decode())\n'
        )
        out = subprocess.run(
            [*_BWRAP_BASE, "--bind", str(box), str(box), "--", "python3", "-c", client],
            capture_output=True, text=True, timeout=20,
        )
        assert out.returncode == 0, out.stderr
        resp = json.loads(out.stdout.strip())
        assert resp["ok"] and resp["as_node"] == "A"  # cliente recebeu a resposta pelo bind-mount
        assert seen["node"] == "A"  # host derivou a identidade do CANAL
        assert seen["frm"] == "EVIL"  # o frm forjado do payload foi IGNORADO
    finally:
        srv.stop()


def _ppid_of(pid: int):
    try:
        with open(f"/proc/{pid}/stat") as f:
            data = f.read()
        return int(data[data.rindex(")") + 2:].split()[1])
    except (OSError, ValueError, IndexError):
        return None


def _descendants(root: int) -> list[int]:
    kids: dict[int, list[int]] = {}
    for path in glob.glob("/proc/[0-9]*"):
        pid = int(path.rsplit("/", 1)[1])
        pp = _ppid_of(pid)
        if pp is not None:
            kids.setdefault(pp, []).append(pid)
    out, stack = [], [root]
    while stack:
        for c in kids.get(stack.pop(), []):
            out.append(c)
            stack.append(c)
    return out


@pytest.mark.skipif(not hasattr(signal, "pidfd_send_signal"),
                    reason="requer pidfd (Linux 5.9+/Python 3.9+)")
def test_killswitch_reapeia_a_subarvore():
    """Drill do kill-switch: cada agente é um bwrap --unshare-pid, então o SIGKILL via pidfd
    no topo COLAPSA a árvore interna. Prova que NÃO sobra processo (o que _kill_all_agents faz)."""
    mark = "987654"
    p = subprocess.Popen(
        [*_BWRAP_BASE, "--", "bash", "-c", f"sleep {mark} & sleep {mark} & wait"]
    )
    try:
        time.sleep(1.0)

        def is_our_sleep(pid):
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    return mark.encode() in f.read()
            except OSError:
                return False

        sleeps = [d for d in _descendants(p.pid) if is_our_sleep(d)]
        assert len(sleeps) >= 2, "os sleeps internos deviam estar vivos antes do kill"

        fd = os.pidfd_open(p.pid)  # EXATAMENTE como CanvasWindow._signal_child
        signal.pidfd_send_signal(fd, signal.SIGKILL)
        os.close(fd)
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        time.sleep(0.5)

        alive = []
        for s in sleeps:
            try:
                os.kill(s, 0)
                alive.append(s)
            except ProcessLookupError:
                pass
            except PermissionError:
                alive.append(s)
        assert alive == [], f"a subárvore não foi ceifada: {alive} ainda vivos"
    finally:
        if p.poll() is None:
            p.kill()
