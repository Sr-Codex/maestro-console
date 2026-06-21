"""Testes do State Store (E1-S3): WAL, CRUD transacional e escrita concorrente."""

from concurrent.futures import ThreadPoolExecutor

from maestro.engine.state.store import Store


def test_wal_ativo(tmp_path):
    with Store(tmp_path / "m.db") as s:
        assert s.journal_mode().lower() == "wal"


def test_sessao_roundtrip(tmp_path):
    with Store(tmp_path / "m.db") as s:
        assert s.get_session("claude") is None
        s.set_session("claude", "sid-1")
        assert s.get_session("claude") == "sid-1"
        s.set_session("claude", "sid-2")  # upsert
        assert s.get_session("claude") == "sid-2"


def test_task_lifecycle(tmp_path):
    with Store(tmp_path / "m.db") as s:
        s.create_task("t1", intent="somar", target="claude")
        t = s.get_task("t1")
        assert t["status"] == "queued"
        assert t["attempts"] == 0
        s.update_task("t1", status="running", bump_attempts=True)
        s.update_task("t1", status="done", result={"out": 42})
        t = s.get_task("t1")
        assert t["status"] == "done"
        assert t["attempts"] == 1
        assert t["result"] == {"out": 42}


def test_get_task_inexistente(tmp_path):
    with Store(tmp_path / "m.db") as s:
        assert s.get_task("nope") is None


def test_escrita_concorrente_sem_corrupcao(tmp_path):
    """N threads inserindo tarefas distintas + logando envelopes: nada se perde."""
    n = 50
    with Store(tmp_path / "m.db") as s:

        def work(i: int):
            s.create_task(f"t{i}", intent=f"job {i}")
            s.log_envelope(
                message_id=f"m{i}",
                task_id=f"t{i}",
                sender="orchestrator",
                recipient="claude",
                state="DONE",
                payload={"i": i},
            )

        with ThreadPoolExecutor(max_workers=16) as ex:
            list(ex.map(work, range(n)))

        assert s.count_tasks() == n
        assert s.count_envelopes() == n
        # cada tarefa é recuperável e íntegra
        for i in range(n):
            t = s.get_task(f"t{i}")
            assert t is not None and t["intent"] == f"job {i}"


def test_update_concorrente_mesma_tarefa(tmp_path):
    """Incrementos concorrentes de attempts não se perdem (transacional)."""
    with Store(tmp_path / "m.db") as s:
        s.create_task("t", intent="x")
        with ThreadPoolExecutor(max_workers=16) as ex:
            list(ex.map(lambda _: s.update_task("t", bump_attempts=True), range(100)))
        assert s.get_task("t")["attempts"] == 100
