"""Unload — Bloco D: medição de RAM da árvore (`proc_ram`) + limiar com histerese.

A medição é provada contra uma ÁRVORE REAL de processos spawnada no teste (bash com
filhos sleep) — provar a fonte, não um /proc sintético. Sem GTK → roda no .venv.
"""

import os
import signal
import subprocess
import time

from maestro.engine.proc_ram import (
    alert_step,
    parse_limit_mb,
    tree_pids,
    tree_ram_mb,
)


def _spawn_tree():
    """bash com 2 filhos sleep — árvore real de 3+ processos."""
    p = subprocess.Popen(["/bin/bash", "-c", "sleep 60 & sleep 60 & wait"])
    deadline = time.time() + 5
    while time.time() < deadline:  # espera os filhos nascerem (via /proc real)
        if len(tree_pids(p.pid)) >= 3:
            break
        time.sleep(0.05)
    return p


def test_tree_pids_desce_a_arvore_real():
    p = _spawn_tree()
    try:
        pids = tree_pids(p.pid)
        assert p.pid in pids
        assert len(pids) >= 3  # bash + 2 sleeps
    finally:
        os.killpg(os.getpgid(p.pid), signal.SIGKILL) if False else p.kill()
        subprocess.run(["pkill", "-KILL", "-P", str(p.pid)], check=False)
        p.wait(timeout=5)


def test_tree_ram_mb_soma_a_arvore_e_e_positiva():
    p = _spawn_tree()
    try:
        rss, pss, private = tree_ram_mb(p.pid)
        assert rss > 0 and pss > 0 and private >= 0
        assert rss >= pss  # RSS conta compartilhado inteiro; PSS divide
        one = tree_ram_mb(tree_pids(p.pid)[-1])  # 1 processo só ≤ árvore inteira
        assert one[1] <= pss
    finally:
        subprocess.run(["pkill", "-KILL", "-P", str(p.pid)], check=False)
        p.kill()
        p.wait(timeout=5)


def test_pid_morto_e_invalido_sao_silenciosos():
    """Contrato best-effort: morto/0/None → vazio/(0,0,0), nunca levanta."""
    p = subprocess.Popen(["sleep", "0.01"])
    p.wait()
    assert tree_pids(p.pid) == []
    assert tree_ram_mb(p.pid) == (0.0, 0.0, 0.0)
    assert tree_pids(0) == []
    assert tree_ram_mb(0) == (0.0, 0.0, 0.0)


def test_alert_step_histerese_anti_flapping():
    """Notifica 1x ao cruzar; oscilar em volta do limiar NÃO re-notifica; re-arma só
    abaixo de 0.9×X (furo de flapping achado na revisão do Fable — docs/21 §8.5)."""
    # desligado: nunca alerta
    assert alert_step(False, 999.0, 0) == (False, False)
    assert alert_step(True, 999.0, 0) == (False, False)
    # cruzou pra cima: notifica UMA vez
    assert alert_step(False, 500.0, 500) == (True, True)
    # segue acima: não re-notifica
    assert alert_step(True, 510.0, 500) == (True, False)
    # oscila logo abaixo do limiar (±5%): AINDA armado, sem notificar (histerese)
    assert alert_step(True, 480.0, 500) == (True, False)  # 480 > 450 (0.9×500)
    # caiu abaixo de 0.9×X: re-arma (sem notificar)
    assert alert_step(True, 440.0, 500) == (False, False)
    # cruzou de novo: notifica de novo (1 notificação por cruzamento)
    assert alert_step(False, 505.0, 500) == (True, True)


def test_parse_limit_mb_nunca_crasha():
    assert parse_limit_mb("500") == 500
    assert parse_limit_mb(" 512 ") == 512
    assert parse_limit_mb("") == 0
    assert parse_limit_mb(None) == 0
    assert parse_limit_mb("abc") == 0
    assert parse_limit_mb("-5") == 0
    assert parse_limit_mb("0") == 0
