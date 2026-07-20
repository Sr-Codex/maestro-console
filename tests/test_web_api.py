"""Testes da API REST web (V4-S2) — reuso da engine + guard anti-duplicação."""

import asyncio
import json

from aiohttp.test_utils import TestClient, TestServer

from maestro.engine.orchestrator import Orchestrator
from maestro.engine.registry import Registry
from maestro.engine.state.store import Store
from maestro.tui.controller import TUIController
from maestro.web.server import make_app


def _build(tmp_path, ask):
    s = Store(tmp_path / "m.db")
    reg = Registry(s)
    reg.register("claude", "claude-code")
    reg.register("codex", "codex")
    ctrl = TUIController(reg, s, Orchestrator(ask, store=s))
    return s, make_app(ctrl, host="127.0.0.1", port=8765, token="t"), ctrl


async def _client(app):
    return TestClient(TestServer(app), headers={"X-Maestro-Token": "t"})


def test_agents_e_teams(tmp_path):
    async def ask(a, p):
        return ""

    async def main():
        s, app, _ = _build(tmp_path, ask)
        try:
            async with await _client(app) as c:
                ag = await (await c.get("/api/agents")).json()
                assert {a["id"] for a in ag} == {"claude", "codex"}
                tms = await (await c.get("/api/teams")).json()
                names = {t["name"] for t in tms}
                assert "coder-reviewer" in names  # built-in
        finally:
            s.close()

    asyncio.run(main())


def test_crud_team_via_api(tmp_path):
    async def ask(a, p):
        return ""

    async def main():
        s, app, ctrl = _build(tmp_path, ask)
        try:
            async with await _client(app) as c:
                body = {
                    "name": "api-team",
                    "roles": [{"name": "coder", "agent": "claude", "instruction": "impl"}],
                }
                r = await c.post("/api/teams", json=body)
                assert r.status == 200
                assert ctrl.team_exists("api-team")
                r2 = await c.delete("/api/teams/api-team")
                assert r2.status == 200 and not ctrl.team_exists("api-team")
                # invalido -> 400
                r3 = await c.post(
                    "/api/teams",
                    json={"name": "x", "roles": [{"name": "c", "agent": "", "instruction": "i"}]},
                )
                assert r3.status == 400
        finally:
            s.close()

    asyncio.run(main())


def test_execute_history_run_detail(tmp_path):
    async def ask(agent_id, prompt):
        return json.dumps({"state": "DONE", "result": "ok"})

    async def main():
        s, app, _ = _build(tmp_path, ask)
        try:
            async with await _client(app) as c:
                r = await c.post("/api/execute", json={"team": "coder-reviewer", "intent": "x"})
                assert r.status == 200
                run_id = (await r.json())["run_id"]
                await app["runs"].wait()  # espera terminar
                det = await (await c.get(f"/api/runs/{run_id}")).json()
                assert det["chain"]["status"] == "done"
                assert len(det["steps"]) == 2
                hist = await (await c.get("/api/history")).json()
                assert any(e["task_id"] == run_id for e in hist)
        finally:
            s.close()

    asyncio.run(main())


def test_guard_anti_duplicacao(tmp_path):
    async def ask(agent_id, prompt):
        await asyncio.sleep(0.2)
        return json.dumps({"state": "DONE", "result": "ok"})

    async def main():
        s, app, _ = _build(tmp_path, ask)
        try:
            async with await _client(app) as c:
                r1 = await c.post("/api/execute", json={"team": "coder-reviewer", "intent": "x"})
                assert r1.status == 200
                # clique repetido enquanto roda -> 409
                r2 = await c.post("/api/execute", json={"team": "coder-reviewer", "intent": "x"})
                assert r2.status == 409
                await app["runs"].wait()
        finally:
            s.close()

    asyncio.run(main())


def test_team_inexistente_404(tmp_path):
    async def ask(a, p):
        return ""

    async def main():
        s, app, _ = _build(tmp_path, ask)
        try:
            async with await _client(app) as c:
                r = await c.post("/api/execute", json={"team": "nao-existe", "intent": "x"})
                assert r.status == 404
        finally:
            s.close()

    asyncio.run(main())
