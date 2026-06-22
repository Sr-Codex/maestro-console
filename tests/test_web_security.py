"""Testes de segurança do servidor web (V4-S1)."""

import asyncio
import os
import stat

from aiohttp.test_utils import TestClient, TestServer

from maestro.web import security
from maestro.web.server import make_app


def test_ensure_token_0600_e_idempotente(tmp_path):
    p = tmp_path / "web_token"
    t1 = security.ensure_token(p)
    assert t1 and len(t1) > 20
    mode = stat.S_IMODE(os.stat(p).st_mode)
    assert mode == 0o600  # credencial protegida
    assert security.ensure_token(p) == t1  # idempotente


def test_origin_e_token_puros():
    allowed = {"http://localhost:8765"}
    assert security.origin_allowed(None, allowed) is True
    assert security.origin_allowed("http://localhost:8765", allowed) is True
    assert security.origin_allowed("http://evil.com", allowed) is False
    assert security.token_ok("abc", "abc") is True
    assert security.token_ok("x", "abc") is False
    assert security.token_ok(None, "abc") is False


def _req(app, path, headers=None):
    async def go():
        async with TestClient(TestServer(app)) as c:
            r = await c.get(path, headers=headers or {})
            return r.status, await r.json()

    return asyncio.run(go())


def test_health_localhost_sem_token():
    app = make_app(None, host="127.0.0.1", port=8765, token="tok")
    status, body = _req(app, "/api/health")
    assert status == 200 and body["status"] == "ok"


def test_origin_invalida_rejeitada():
    app = make_app(None, host="127.0.0.1", port=8765, token="tok")
    status, _ = _req(app, "/api/health", {"Origin": "http://evil.com"})
    assert status == 403


def _lan_app():
    return make_app(None, host="0.0.0.0", port=8765, token="segredo")


def test_lan_exige_token():
    # sem token -> 401 (app nova por request: aiohttp congela a app ao iniciar)
    s1, _ = _req(_lan_app(), "/api/health")
    assert s1 == 401
    # com token correto no header -> 200
    s2, _ = _req(_lan_app(), "/api/health", {security.TOKEN_HEADER: "segredo"})
    assert s2 == 200
