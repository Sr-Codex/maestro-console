"""Testes da vigilância pura (ADR-17, Etapa 4): ciclo de cabos + anomalia de spawn."""

from maestro.engine.maestro_guard import has_cycle, spawn_anomaly


def test_sem_ciclo_em_arvore():
    assert not has_cycle([("a", "b"), ("b", "c"), ("a", "d")])  # árvore: sem ciclo


def test_ciclo_simples():
    assert has_cycle([("a", "b"), ("b", "c"), ("c", "a")])  # triângulo


def test_self_loop_e_ciclo():
    assert has_cycle([("a", "a")])


def test_grafo_vazio_e_par_unico():
    assert not has_cycle([])
    assert not has_cycle([("a", "b")])


def test_anomalia_dispara_no_burst():
    evs = [{"event": "recruit_blocked", "ts": 100.0 + i} for i in range(8)]
    assert spawn_anomaly(evs, now=110.0, window=30.0, blocked_threshold=8)


def test_anomalia_ignora_fora_da_janela():
    evs = [{"event": "recruit_blocked", "ts": 10.0 + i} for i in range(8)]
    assert not spawn_anomaly(evs, now=200.0, window=30.0, blocked_threshold=8)  # velhos demais


def test_anomalia_ignora_outros_eventos():
    evs = [{"event": "recruit", "ts": 100.0 + i} for i in range(20)]
    assert not spawn_anomaly(evs, now=110.0, window=30.0, blocked_threshold=8)  # não são blocked


def test_anomalia_abaixo_do_limiar():
    evs = [{"event": "recruit_blocked", "ts": 100.0 + i} for i in range(5)]
    assert not spawn_anomaly(evs, now=110.0, blocked_threshold=8)
