"""Testes do SSE ao vivo (V4-S3)."""

import asyncio
import json

from aiohttp.test_utils import TestClient, TestServer

from maestro.engine.orchestrator import Orchestrator
from maestro.engine.registry import Registry
from maestro.engine.state.store import Store
from maestro.tui.controller import TUIController
from maestro.web.runs import RunManager
from maestro.web.server import make_app


def test_runmanager_broadcast_step_e_run_end(tmp_path):
    eventos = []

    async def ask(agent_id, prompt):
        return json.dumps({"state": "DONE", "result": "ok"})

    async def main():
        with Store(tmp_path / "m.db") as s:
            ctrl = TUIController(Registry(s), s, Orchestrator(ask, store=s))
            rm = RunManager(ctrl)
            rm.subscribe(eventos.append)
            await rm.start("coder-reviewer", "x")
            await rm.wait()
            await asyncio.sleep(0)  # deixa o done_callback rodar

    asyncio.run(main())
    tipos = [e["type"] for e in eventos]
    assert tipos.count("step") == 4  # start+done de 2 papéis
    assert eventos[-1]["type"] == "run_end" and eventos[-1]["outcome"] == "done"


def test_sse_endpoint_entrega_eventos(tmp_path):
    async def ask(agent_id, prompt):
        await asyncio.sleep(0.05)
        return json.dumps({"state": "DONE", "result": "ok"})

    async def main():
        s = Store(tmp_path / "m.db")
        reg = Registry(s)
        reg.register("claude", "claude-code")
        reg.register("codex", "codex")
        app = make_app(
            TUIController(reg, s, Orchestrator(ask, store=s)),
            host="127.0.0.1",
            port=8765,
            token="t",
        )
        try:
            async with TestClient(TestServer(app)) as c:
                resp = await c.get("/api/events")
                await c.post("/api/execute", json={"team": "coder-reviewer", "intent": "x"})
                vistos = []
                # le ate o run_end (eventos ficam na fila mesmo se a run termina antes)
                for _ in range(20):
                    line = await asyncio.wait_for(resp.content.readline(), timeout=5)
                    txt = line.decode().strip()
                    if txt.startswith("data:"):
                        ev = json.loads(txt[5:])
                        vistos.append(ev)
                        if ev["type"] == "run_end":
                            break
                resp.close()
                assert any(e["type"] == "step" for e in vistos)
                assert vistos[-1]["type"] == "run_end"
        finally:
            s.close()

    asyncio.run(main())
