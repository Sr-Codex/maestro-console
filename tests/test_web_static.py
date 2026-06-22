"""Testes do shell estático servido (V4-S4)."""

import asyncio

from aiohttp.test_utils import TestClient, TestServer

from maestro.web.server import make_app


def _get_text(path):
    async def go():
        app = make_app(None, host="127.0.0.1", port=8765, token="t")
        async with TestClient(TestServer(app)) as c:
            r = await c.get(path)
            return r.status, await r.text()

    return asyncio.run(go())


def test_index_servido():
    status, body = _get_text("/")
    assert status == 200
    assert "maestro console" in body
    assert "/static/app.js" in body
    assert 'id="canvas"' in body  # container do canvas


def test_static_assets_servidos():
    s_css, css = _get_text("/static/style.css")
    assert s_css == 200 and "--busy" in css
    s_js, js = _get_text("/static/app.js")
    assert s_js == 200 and "EventSource" in js


def test_shell_estatico_sem_token_mesmo_em_lan():
    """O shell (não-/api) é servido sem token (dados/controle ficam atrás de token)."""

    async def go():
        app = make_app(None, host="0.0.0.0", port=8765, token="seg")
        async with TestClient(TestServer(app)) as c:
            r = await c.get("/")  # LAN, sem token -> shell ainda serve
            return r.status

    assert asyncio.run(go()) == 200
