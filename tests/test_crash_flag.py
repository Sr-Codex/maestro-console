"""R1 do reattach de órfãos (docs/25 §4-R1): sentinela de crash (dirty-flag).

Gi-free — roda no `.venv`. Prova o ciclo boot(arm)→shutdown(disarm) e a detecção de
crash (arm sem disarm no run anterior).
"""

from maestro.engine import crash_flag
from maestro.engine.state.store import Store


def test_primeiro_boot_nunca_e_crash(tmp_path):
    # DB novo: nada gravado → não é crash, e arma a flag pra este run.
    with Store(tmp_path / "s.db") as st:
        assert crash_flag.check_and_arm(st) is False


def test_crash_detectado_quando_run_anterior_nao_desarmou(tmp_path):
    db = tmp_path / "s.db"
    with Store(db) as st:  # run 1 "crasha": arma e fecha SEM disarm
        crash_flag.check_and_arm(st)
    with Store(db) as st2:  # run 2: a flag ainda está suja → crash
        assert crash_flag.check_and_arm(st2) is True


def test_fechamento_limpo_nao_vira_crash(tmp_path):
    db = tmp_path / "s.db"
    with Store(db) as st:  # run 1 fecha LIMPO: arma e desarma
        crash_flag.check_and_arm(st)
        crash_flag.disarm(st)
    with Store(db) as st2:  # run 2: flag limpa → não é crash
        assert crash_flag.check_and_arm(st2) is False


def test_disarm_e_idempotente(tmp_path):
    # disarm sem flag setada não deve explodir (higiene).
    with Store(tmp_path / "s.db") as st:
        crash_flag.disarm(st)
        crash_flag.disarm(st)
        assert crash_flag.check_and_arm(st) is False


def test_dois_crashes_seguidos_continuam_detectando(tmp_path):
    db = tmp_path / "s.db"
    for _ in range(2):  # dois runs que crasham em sequência
        with Store(db) as st:
            crash_flag.check_and_arm(st)  # arma, nunca desarma
    with Store(db) as st2:
        assert crash_flag.check_and_arm(st2) is True  # ainda detecta
