"""Testes das posições dos nós do canvas (V4-S5): store + API + asset servido."""

import asyncio

from aiohttp.test_utils import TestClient, TestServer

from maestro.engine.orchestrator import Orchestrator
from maestro.engine.registry import Registry
from maestro.engine.state.store import Store
from maestro.tui.controller import TUIController
from maestro.web.server import make_app


def test_store_node_positions(tmp_path):
    with Store(tmp_path / "m.db") as s:
        assert s.get_node_positions() == {}
        s.set_node_position("claude", 100.0, 160.0)
        s.set_node_position("codex", 300.5, 200.0)
        s.set_node_position("claude", 120.0, 170.0)  # upsert
        pos = s.get_node_positions()
        assert pos["claude"] == {"x": 120.0, "y": 170.0}
        assert pos["codex"] == {"x": 300.5, "y": 200.0}


def test_positions_api(tmp_path):
    async def ask(a, p):
        return ""

    async def main():
        s = Store(tmp_path / "m.db")
        app = make_app(
            TUIController(Registry(s), s, Orchestrator(ask, store=s)),
            host="127.0.0.1",
            port=8765,
            token="t",
        )
        try:
            async with TestClient(TestServer(app), headers={"X-Maestro-Token": "t"}) as c:
                r = await c.post("/api/positions", json={"agent_id": "claude", "x": 50, "y": 60})
                assert r.status == 200
                pos = await (await c.get("/api/positions")).json()
                assert pos["claude"] == {"x": 50.0, "y": 60.0}
                # invalido -> 400
                bad = await c.post("/api/positions", json={"agent_id": "x"})
                assert bad.status == 400
        finally:
            s.close()

    asyncio.run(main())


def test_canvas_js_servido():
    async def go():
        app = make_app(None, host="127.0.0.1", port=8765, token="t")
        async with TestClient(TestServer(app), headers={"X-Maestro-Token": "t"}) as c:
            r = await c.get("/static/canvas.js")
            return r.status, await r.text()

    status, body = asyncio.run(go())
    assert status == 200
    assert "MaestroCanvas" in body and "handoffs" in body
