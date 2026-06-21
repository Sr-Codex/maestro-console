"""Testes da Task Queue (E3-S3): teto de concorrência, callback e mutex de sessão."""

import asyncio

from maestro.engine.queue import Task, TaskQueue
from maestro.engine.runner import RunResult, RunStatus
from maestro.engine.session import SessionManager
from maestro.engine.state.store import Store


def test_ceiling_limita_concorrencia():
    active = 0
    peak = 0

    async def worker(task):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.05)
        active -= 1
        return task.id

    async def main():
        q = TaskQueue(worker, ceiling=2)
        tasks = [Task(id=f"t{i}", agent_id=f"a{i}", prompt="p") for i in range(6)]
        res = await q.submit_all(tasks)
        assert sorted(res) == sorted(t.id for t in tasks)

    asyncio.run(main())
    assert peak == 2  # nunca passou do teto


def test_callback_disparado():
    got = []

    async def worker(task):
        return f"r-{task.id}"

    async def main():
        q = TaskQueue(worker, ceiling=4)
        await q.submit(Task(id="t1", agent_id="a", prompt="p", callback=got.append))

    asyncio.run(main())
    assert got == ["r-t1"]


def test_respeita_mutex_de_sessao(tmp_path):
    """Tarefas para o MESMO agente serializam; agentes distintos concorrem."""
    per_agent_active: dict[str, int] = {}
    max_same = 0

    def _ok():
        return RunResult(RunStatus.OK, 0, "", "", 0.0, False)

    async def fake_run(profile, prompt, *, workspace, session_id, resume, timeout):
        nonlocal max_same
        per_agent_active[session_id] = per_agent_active.get(session_id, 0) + 1
        max_same = max(max_same, per_agent_active[session_id])
        await asyncio.sleep(0.05)
        per_agent_active[session_id] -= 1
        return _ok()

    async def main():
        with Store(tmp_path / "m.db") as s:
            sm = SessionManager(s)

            async def worker(task):
                return await sm.run_in_session(
                    None, task.agent_id, task.prompt, workspace="/w", timeout=1, run_fn=fake_run
                )

            q = TaskQueue(worker, ceiling=8)
            # 3 tarefas p/ "claude" (mesma sessão) + 3 p/ agentes distintos
            tasks = [Task(id=f"c{i}", agent_id="claude", prompt="p") for i in range(3)]
            tasks += [Task(id=f"x{i}", agent_id=f"ag{i}", prompt="p") for i in range(3)]
            await q.submit_all(tasks)

    asyncio.run(main())
    assert max_same == 1  # mesma sessão nunca teve 2 ativas
