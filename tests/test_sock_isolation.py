"""S1 (review docs/33): isolamento das boxes de socket entre agentes.

O `--ro-bind / /` do sandbox reexpõe `<bus>/box/<todos>` (o ask-bus vive sob $HOME). Sem
mascarar, um agente hostil conecta no socket de OUTRO e o host carimba `frm=vítima` (spoof
total de identidade — quebra o invariante-mãe do ADR-17). O fix: `sandbox.wrap` mascara
`<home>/ask-bus/box` (tmpfs) em TODO spawn — a máscara mora na CAMADA de sandbox, não no
chamador, pra cobrir interativo E headless/floor (run_agent); a PRÓPRIA box reaparece pelo
bind de shared_paths (ordem tmpfs→bind).

Níveis: unit gi-free (o argv mascara, interativo E headless; roda no CI) + o teste T1 do
isolamento sob bwrap REAL, que FALTAVA e deixou o S1 passar (gated por MAESTRO_LIVE).
"""

import os
import socket

import pytest

from maestro.engine import sandbox
from maestro.engine.adapters.base import load_profiles
from maestro.native.agents import agent_argv


def _pair_index(args, flag, value):
    for i, a in enumerate(args):
        if a == flag and i + 1 < len(args) and args[i + 1] == value:
            return i
    return -1


def _seed_bus(base):
    """Cria `<base>/ask-bus/box/<nó>` — a máscara só monta o que existe."""
    box = base / "ask-bus" / "box"
    (box / "claude-2").mkdir(parents=True)
    return box


def test_interativo_mascara_boxes_irmas_antes_de_bindar_a_propria(tmp_path, monkeypatch):
    """Unit (CI): o argv interativo põe `--tmpfs <bus>/box` ANTES de `--bind <bus>/box/<nó>`."""
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    monkeypatch.setenv("MAESTRO_HOME", str(tmp_path))  # default_home() → tmp_path
    box_parent = str(_seed_bus(tmp_path))
    prof = load_profiles()["claude"]
    ws = tmp_path / "ws"
    ws.mkdir()
    args = agent_argv(prof, str(ws), node="claude-2", ask_bus_dir=str(tmp_path / "ask-bus"))
    i_mask = _pair_index(args, "--tmpfs", box_parent)
    i_bind = _pair_index(args, "--bind", str(tmp_path / "ask-bus" / "box" / "claude-2"))
    assert i_mask != -1, "as boxes irmãs NÃO foram mascaradas (--tmpfs <bus>/box ausente)"
    assert i_bind != -1, "a própria box não foi re-bindada"
    assert i_mask < i_bind, "ordem errada: o tmpfs tem de vir ANTES do bind da própria box"


def test_headless_floor_tambem_mascara(tmp_path, monkeypatch):
    """Unit (CI) — o FURO da revisão Fable: o caminho headless/floor (`run_agent` chama
    `sandbox.wrap` direto, sem box própria) TAMBÉM tem de esconder as boxes irmãs. Como a
    máscara mora no wrap(), um `wrap()` cru (sem shared box) já mascara `<bus>/box`."""
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    monkeypatch.setenv("MAESTRO_HOME", str(tmp_path))
    box_parent = str(_seed_bus(tmp_path))
    ws = tmp_path / "ws"
    ws.mkdir()
    git_dir = tmp_path / "git"
    git_dir.mkdir()
    args = sandbox.wrap(["cli"], workspace=ws, shared_paths=[str(git_dir)])  # como o floor
    assert _pair_index(args, "--tmpfs", box_parent) != -1, \
        "caminho headless/floor NÃO mascara as boxes irmãs (spoof continua por run_agent)"


@pytest.mark.skipif(not os.environ.get("MAESTRO_LIVE"),
                    reason="T1: isolamento sob bwrap REAL — MAESTRO_LIVE=1 pra rodar")
def test_t1_box_irma_invisivel_sob_bwrap_real():
    """T1 (o teste que faltava, review docs/33 Fase 4): sob bwrap REAL um agente NÃO enxerga
    nem conecta na box de outro. Espelha a prova da Fase 3, mas asserta o FIX (as duas pontas:
    `listdir(<bus>/box)` não lista a vítima e `connect(<bus>/box/victim/sock)` falha).

    CRÍTICO: o bus fica FORA de /tmp — senão o `--tmpfs /tmp` mascara por acidente e o teste
    passa VÁCUO (a armadilha que a Fase 3 flagou)."""
    if not sandbox.bwrap_available():
        pytest.skip("bwrap ausente")
    import shutil
    import tempfile
    from pathlib import Path
    base = Path(tempfile.mkdtemp(prefix="maestro-sock-t1-", dir=os.path.expanduser("~")))
    old = os.environ.get("MAESTRO_HOME")
    os.environ["MAESTRO_HOME"] = str(base)  # default_home() → base; wrap mascara <base>/ask-bus/box
    try:
        _run_t1(base)
    finally:
        if old is None:
            os.environ.pop("MAESTRO_HOME", None)
        else:
            os.environ["MAESTRO_HOME"] = old
        shutil.rmtree(base, ignore_errors=True)


def _run_t1(base):
    bus = base / "ask-bus"  # = default_home()/ask-bus → wrap mascara bus/box
    (bus / "box" / "victim").mkdir(parents=True)
    (bus / "box" / "attacker").mkdir(parents=True)
    victim_sock = str(bus / "box" / "victim" / "sock")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(victim_sock)
    srv.listen(1)
    try:
        prof = load_profiles()["claude"]
        ws = base / "ws"
        ws.mkdir()
        probe = (
            "import os, socket, json\n"
            f"box=os.path.join({str(bus)!r}, 'box')\n"
            "try:\n"
            "    siblings=sorted(os.listdir(box))\n"
            "except OSError:\n"
            "    siblings=['<box inacessivel>']\n"
            "ok=False\n"
            "try:\n"
            "    s=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)\n"
            "    s.connect(os.path.join(box,'victim','sock'))\n"
            "    ok=True\n"
            "except OSError:\n"
            "    ok=False\n"
            "print(json.dumps({'siblings': siblings, 'connected': ok}))\n"
        )
        argv = agent_argv(prof, str(ws), node="attacker", ask_bus_dir=str(bus))
        i = argv.index("--")
        wrapped = argv[:i + 1] + ["python3", "-c", probe]
        import subprocess
        out = subprocess.run(wrapped, capture_output=True, text=True, timeout=30)
        import json
        res = json.loads(out.stdout.strip().splitlines()[-1])
        assert "victim" not in res["siblings"], f"box irmã VISÍVEL: {res['siblings']}"
        assert res["connected"] is False, "CONECTOU no socket da vítima — spoof ainda possível"
    finally:
        srv.close()
