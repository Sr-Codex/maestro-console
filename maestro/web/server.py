"""Servidor aiohttp (V4-S1+). Frontend sobre a engine; sem duplicar regras.

A app roda no mesmo loop asyncio da engine (os handlers chamam o
TUIController/Orchestrator async diretamente).
"""

from __future__ import annotations

from aiohttp import web

from .. import __version__
from .security import (
    TOKEN_HEADER,
    allowed_origins_for,
    is_local,
    origin_allowed,
    token_ok,
)


@web.middleware
async def security_mw(request: web.Request, handler):
    app = request.app
    # CORS fechado: valida Origin (rejeita cross-origin não autorizado)
    if not origin_allowed(request.headers.get("Origin"), app["allowed_origins"]):
        return web.json_response({"error": "origin_not_allowed"}, status=403)
    # token obrigatório fora de localhost (header, nunca query)
    if app["require_token"] and not token_ok(request.headers.get(TOKEN_HEADER), app["token"]):
        return web.json_response({"error": "unauthorized"}, status=401)
    return await handler(request)


async def _health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "version": __version__})


def make_app(controller, *, host: str, port: int, token: str) -> web.Application:
    app = web.Application(middlewares=[security_mw])
    app["controller"] = controller
    app["token"] = token
    app["require_token"] = not is_local(host)
    app["allowed_origins"] = allowed_origins_for(host, port)
    app.router.add_get("/api/health", _health)
    return app
