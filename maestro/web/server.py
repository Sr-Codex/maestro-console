"""Servidor aiohttp (V4-S1+). Frontend sobre a engine; sem duplicar regras.

A app roda no mesmo loop asyncio da engine (os handlers chamam o
TUIController/Orchestrator async diretamente).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from aiohttp import web

from .. import __version__
from ..engine import history
from .runs import AlreadyRunning, RunManager
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
    # Proteção aplica-se à superfície de DADOS/CONTROLE (/api/). O shell estático
    # (HTML/JS/CSS) é servido livremente (sem segredos); token via header nas APIs.
    if request.path.startswith("/api/"):
        # CORS fechado: valida Origin (rejeita cross-origin não autorizado)
        if not origin_allowed(request.headers.get("Origin"), app["allowed_origins"]):
            return web.json_response({"error": "origin_not_allowed"}, status=403)
        # S4 (review docs/33): endpoints MUTADORES (control-plane: execute/cancel/resume,
        # teams POST/DELETE, positions/viewport POST) exigem token SEMPRE — inclusive em
        # localhost. Um agente co-local (netns compartilhado, sem --unshare-net) alcança o
        # loopback e forjaria autoridade. Leitura (GET) mantém a isenção de localhost (só
        # disclosure). O token do arquivo é escondido do agente no sandbox (secret_files).
        mutating = request.method not in ("GET", "HEAD", "OPTIONS")
        if (mutating or app["require_token"]) and not token_ok(
            request.headers.get(TOKEN_HEADER), app["token"]
        ):
            return web.json_response({"error": "unauthorized"}, status=401)
    return await handler(request)


STATIC_DIR = Path(__file__).parent / "static"


async def _index(request):
    return web.FileResponse(STATIC_DIR / "index.html")


async def _health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "version": __version__})


def _ctrl(request):
    return request.app["controller"]


async def _agents(request):
    return web.json_response(
        [{"id": a.id, "type": a.type, "state": str(a.state)} for a in _ctrl(request).list_agents()]
    )


async def _teams(request):
    c = _ctrl(request)
    out = []
    for name in c.list_teams():
        t = c.get_team(name)
        out.append(
            {
                "name": name,
                "route": t.route,
                "roles": [
                    {"name": r.name, "agent": r.agent, "instruction": r.instruction}
                    for r in t.roles
                ],
            }
        )
    return web.json_response(out)


async def _save_team(request):
    data = await request.json()
    roles = [(r["name"], r["agent"], r["instruction"]) for r in data.get("roles", [])]
    try:
        t = _ctrl(request).save_team(data["name"], roles)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)
    return web.json_response({"name": t.name, "route": t.route})


async def _delete_team(request):
    _ctrl(request).delete_team(request.match_info["name"])
    return web.json_response({"ok": True})


async def _history(request):
    c = _ctrl(request)
    return web.json_response(history.recent(c._store, limit=int(request.query.get("limit", 20))))


async def _run_detail(request):
    c = _ctrl(request)
    rid = request.match_info["run_id"]
    chain = c._store.get_chain(rid)
    if chain is None:
        return web.json_response({"error": "not_found"}, status=404)
    return web.json_response({"chain": chain, "steps": c._store.get_steps(rid)})


async def _execute(request):
    data = await request.json()
    runs: RunManager = request.app["runs"]
    try:
        run_id = await runs.start(data["team"], data.get("intent", ""))
    except AlreadyRunning:
        return web.json_response({"error": "already_running"}, status=409)
    except LookupError as e:
        return web.json_response({"error": str(e)}, status=404)
    return web.json_response({"run_id": run_id})


async def _cancel(request):
    return web.json_response({"cancelled": request.app["runs"].cancel()})


async def _get_viewport(request):
    return web.json_response(_ctrl(request)._store.get_ui("viewport") or {})


async def _set_viewport(request):
    data = await request.json()
    _ctrl(request)._store.set_ui("viewport", data)
    return web.json_response({"ok": True})


async def _get_positions(request):
    return web.json_response(_ctrl(request)._store.get_node_positions())


async def _set_position(request):
    data = await request.json()
    try:
        _ctrl(request)._store.set_node_position(
            data["agent_id"], float(data["x"]), float(data["y"])
        )
    except (KeyError, TypeError, ValueError) as e:
        return web.json_response({"error": str(e)}, status=400)
    return web.json_response({"ok": True})


async def _events(request):
    """SSE: progresso por etapa e estados ao vivo (não é caminho de dados)."""
    runs: RunManager = request.app["runs"]
    queue: asyncio.Queue = asyncio.Queue()
    runs.subscribe(queue.put_nowait)
    resp = web.StreamResponse(
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
    await resp.prepare(request)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15)
                await resp.write(f"data: {json.dumps(event)}\n\n".encode())
            except TimeoutError:
                await resp.write(b": keep-alive\n\n")  # heartbeat
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        runs.unsubscribe(queue.put_nowait)
    return resp


async def _resume(request):
    data = await request.json() if request.can_read_body else {}
    runs: RunManager = request.app["runs"]
    try:
        run_id = await runs.resume(swap_agent=data.get("swap_agent"), reprompt=data.get("reprompt"))
    except AlreadyRunning:
        return web.json_response({"error": "already_running"}, status=409)
    except LookupError as e:
        return web.json_response({"error": str(e)}, status=404)
    return web.json_response({"run_id": run_id})


def make_app(controller, *, host: str, port: int, token: str) -> web.Application:
    app = web.Application(middlewares=[security_mw])
    app["controller"] = controller
    app["runs"] = RunManager(controller) if controller is not None else None
    app["token"] = token
    app["require_token"] = not is_local(host)
    app["allowed_origins"] = allowed_origins_for(host, port)
    app.router.add_get("/api/health", _health)
    app.router.add_get("/api/agents", _agents)
    app.router.add_get("/api/teams", _teams)
    app.router.add_post("/api/teams", _save_team)
    app.router.add_delete("/api/teams/{name}", _delete_team)
    app.router.add_get("/api/history", _history)
    app.router.add_get("/api/runs/{run_id}", _run_detail)
    app.router.add_post("/api/execute", _execute)
    app.router.add_post("/api/cancel", _cancel)
    app.router.add_post("/api/resume", _resume)
    app.router.add_get("/api/events", _events)
    app.router.add_get("/api/positions", _get_positions)
    app.router.add_post("/api/positions", _set_position)
    app.router.add_get("/api/viewport", _get_viewport)
    app.router.add_post("/api/viewport", _set_viewport)
    app.router.add_get("/", _index)
    if STATIC_DIR.is_dir():
        app.router.add_static("/static/", STATIC_DIR)
    return app


def serve(*, host: str = "127.0.0.1", port: int = 8765, home=None) -> None:  # pragma: no cover
    """Sobe o servidor reusando a engine (bootstrap). Bind padrão localhost."""
    from ..bootstrap import build_controller, default_home
    from .security import ensure_token, is_local, web_token_path

    base = default_home() if home is None else home
    controller, store = build_controller(home=base)
    token = ensure_token(web_token_path(base))
    app = make_app(controller, host=host, port=port, token=token)
    # S4: ações de controle exigem token MESMO em localhost — imprime sempre p/ o humano
    # colar no campo "token" da UI (persiste no localStorage; cola 1x).
    print(f"token (header {TOKEN_HEADER}): {token}")
    if not is_local(host):
        print("⚠️ exposto na LAN — prefira SSH port forwarding p/ acesso remoto seguro")
    print(f"maestro web em http://{host}:{port}")
    try:
        web.run_app(app, host=host, port=port, print=None)
    finally:
        store.close()
