"""S1 (review docs/33): isolamento das boxes de socket entre agentes.

O `--ro-bind / /` do sandbox reexpõe `<bus>/box/<todos>` (o ask-bus vive sob $HOME). Sem
mascarar, um agente hostil conecta no socket de OUTRO e o host carimba `frm=vítima` (spoof
total de identidade — quebra o invariante-mãe do ADR-17). O fix: tmpfs em `<bus>/box` esconde
as irmãs; a PRÓPRIA box reaparece pelo bind (ordem tmpfs→bind no wrap).

Dois níveis: unit gi-free (o argv esconde+re-expõe na ordem certa, roda no CI) e o teste T1 —
o isolamento sob bwrap REAL, que FALTAVA e deixou o S1 passar (gated por MAESTRO_LIVE).
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


def test_agent_argv_mascara_boxes_irmas_antes_de_bindar_a_propria(tmp_path, monkeypatch):
    """Unit (CI): o argv põe `--tmpfs <bus>/box` ANTES de `--bind <bus>/box/<nó>` — as irmãs
    somem, a própria reaparece por cima."""
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    prof = load_profiles()["claude"]
    ws = tmp_path / "ws"
    ws.mkdir()
    bus = tmp_path / "bus"
    args = agent_argv(prof, str(ws), node="claude-2", ask_bus_dir=str(bus))
    box_parent = str(bus / "box")
    own_box = str(bus / "box" / "claude-2")
    i_mask = _pair_index(args, "--tmpfs", box_parent)
    i_bind = _pair_index(args, "--bind", own_box)
    assert i_mask != -1, "as boxes irmãs NÃO foram mascaradas (--tmpfs <bus>/box ausente)"
    assert i_bind != -1, "a própria box não foi re-bindada"
    assert i_mask < i_bind, "ordem errada: o tmpfs tem de vir ANTES do bind da própria box"


@pytest.mark.skipif(not os.environ.get("MAESTRO_LIVE"),
                    reason="T1: isolamento sob bwrap REAL — MAESTRO_LIVE=1 pra rodar")
def test_t1_box_irma_invisivel_sob_bwrap_real():
    """T1 (o teste que faltava, review docs/33 Fase 4): sob bwrap REAL com os flags de
    produção, um agente NÃO enxerga nem conecta na box de outro. Espelha a prova da Fase 3,
    mas asserta o FIX. Prova as duas pontas: `listdir(<bus>/box)` não lista a vítima e
    `connect(<bus>/box/victim/sock)` falha.

    CRÍTICO: o bus fica FORA de /tmp — senão o `--tmpfs /tmp` do sandbox mascara o bus por
    acidente e o teste passa VÁCUO (a armadilha que a investigação da Fase 3 flagou: a 1ª
    prova pôs o bus em /tmp e "refutou" o achado por artefato de teste)."""
    if not sandbox.bwrap_available():
        pytest.skip("bwrap ausente")
    import shutil
    import tempfile
    from pathlib import Path
    base = Path(tempfile.mkdtemp(prefix="maestro-sock-t1-", dir=os.path.expanduser("~")))
    try:
        _run_t1(base)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _run_t1(base):
    bus = base / "bus"
    (bus / "box" / "victim").mkdir(parents=True)
    (bus / "box" / "attacker").mkdir(parents=True)
    # socket VIVO da vítima (o alvo do spoof)
    victim_sock = str(bus / "box" / "victim" / "sock")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(victim_sock)
    srv.listen(1)
    try:
        prof = load_profiles()["claude"]
        ws = base / "ws"
        ws.mkdir()
        # de DENTRO do sandbox do atacante: tenta enumerar as irmãs e conectar na vítima
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
            f"    s.connect(os.path.join(box,'victim','sock'))\n"
            "    ok=True\n"
            "except OSError:\n"
            "    ok=False\n"
            "print(json.dumps({'siblings': siblings, 'connected': ok}))\n"
        )
        argv = agent_argv(prof, str(ws), node="attacker", ask_bus_dir=str(bus))
        # troca o launch interativo pelo probe: roda o python do probe DENTRO do mesmo bwrap
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
