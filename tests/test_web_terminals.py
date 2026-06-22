"""Testes dos terminais ao vivo no canvas (V5-S4): assets + fluxo de output SSE."""

import asyncio

from aiohttp.test_utils import TestClient, TestServer

from maestro.engine.orchestrator import OutputBus
from maestro.web.runs import RunManager
from maestro.web.server import make_app


def test_canvas_tem_terminais_e_output():
    async def go():
        app = make_app(None, host="127.0.0.1", port=8765, token="t")
        async with TestClient(TestServer(app)) as c:
            js = await (await c.get("/static/canvas.js")).text()
            css = await (await c.get("/static/style.css")).text()
            appjs = await (await c.get("/static/app.js")).text()
            return js, css, appjs

    js, css, appjs = asyncio.run(go())
    assert "foreignObject" in js and "onOutput" in js and "term-body" in js
    assert ".term-body" in css
    assert 'e.type === "output"' in appjs  # app encaminha output ao canvas


def test_output_flui_para_assinante_sse(tmp_path):
    """Simula o stdout ao vivo do agente chegando como evento SSE output."""

    class Ctrl:
        output_bus = OutputBus()

    rm = RunManager(Ctrl())
    eventos = []
    rm.subscribe(eventos.append)
    Ctrl.output_bus.emit("claude", "olá ")
    Ctrl.output_bus.emit("claude", "mundo")
    outs = [e for e in eventos if e["type"] == "output"]
    assert [o["chunk"] for o in outs] == ["olá ", "mundo"]
    assert all(o["agent"] == "claude" for o in outs)
