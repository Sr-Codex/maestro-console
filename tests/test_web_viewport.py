"""Testes do viewport do canvas infinito (V5-S3): store kv + API."""

import asyncio

from aiohttp.test_utils import TestClient, TestServer

from maestro.engine.orchestrator import Orchestrator
from maestro.engine.registry import Registry
from maestro.engine.state.store import Store
from maestro.tui.controller import TUIController
from maestro.web.server import make_app


def test_store_ui_kv(tmp_path):
    with Store(tmp_path / "m.db") as s:
        assert s.get_ui("viewport") is None
        s.set_ui("viewport", {"x": 10, "y": 20, "w": 800, "h": 320})
        assert s.get_ui("viewport") == {"x": 10, "y": 20, "w": 800, "h": 320}
        s.set_ui("viewport", {"x": 0, "y": 0, "w": 400, "h": 160})  # upsert
        assert s.get_ui("viewport")["w"] == 400


def test_viewport_api(tmp_path):
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
            async with TestClient(TestServer(app)) as c:
                assert await (await c.get("/api/viewport")).json() == {}
                r = await c.post("/api/viewport", json={"x": 5, "y": 6, "w": 800, "h": 320})
                assert r.status == 200
                vp = await (await c.get("/api/viewport")).json()
                assert vp == {"x": 5, "y": 6, "w": 800, "h": 320}
        finally:
            s.close()

    asyncio.run(main())


def test_canvas_js_tem_pan_zoom():
    async def go():
        app = make_app(None, host="127.0.0.1", port=8765, token="t")
        async with TestClient(TestServer(app)) as c:
            return await (await c.get("/static/canvas.js")).text()

    js = asyncio.run(go())
    assert "viewBox" in js and "wheel" in js  # pan/zoom presentes
