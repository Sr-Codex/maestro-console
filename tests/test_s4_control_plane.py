"""S4 (review docs/33): control-plane web exige token nos MUTADORES mesmo em localhost, e o
token do arquivo é escondido do sandbox do agente (senão o agente co-local o lê e forja).

gi-free → roda no CI. Dois lados: o middleware (mutador sem token = 401; leitura aberta) e o
mecanismo genérico `secret_files` do sandbox (o token vira `--ro-bind /dev/null`).
"""

import asyncio

from aiohttp.test_utils import TestClient, TestServer

from maestro.engine import sandbox
from maestro.engine.adapters.base import load_profiles
from maestro.native.agents import agent_argv
from maestro.web.server import make_app


def _call(method, path, headers=None):
    """App FRESCO por chamada — um Application do aiohttp não pode ir a 2 TestServer."""
    async def go():
        app = make_app(None, host="127.0.0.1", port=8765, token="segredo")
        async with TestClient(TestServer(app)) as c:
            r = await c.request(method, path, headers=headers or {})
            return r.status

    return asyncio.run(go())


# --- middleware: mutador exige token em localhost (decisão B) -----------------


def test_mutador_localhost_sem_token_401():
    # POST /api/execute (control-plane) SEM token em localhost → recusado
    assert _call("POST", "/api/execute") == 401
    assert _call("POST", "/api/cancel") == 401
    assert _call("DELETE", "/api/teams/x") == 401


def test_mutador_localhost_com_token_passa_do_middleware():
    # com o token certo o middleware libera (o handler pode dar 400/500 por corpo, mas NÃO 401)
    assert _call("POST", "/api/execute", {"X-Maestro-Token": "segredo"}) != 401


def test_leitura_localhost_sem_token_ok():
    # decisão B: GET (só disclosure) mantém a isenção de localhost — sem atrito p/ ver a UI
    assert _call("GET", "/api/health") == 200


def test_token_errado_no_mutador_401():
    assert _call("POST", "/api/execute", {"X-Maestro-Token": "errado"}) == 401


# --- sandbox: o token do web é escondido do agente (secret_files) -------------


def test_agent_argv_esconde_o_web_token(tmp_path, monkeypatch):
    """O `{base}/web_token` (irmão do ask-bus) vira `--ro-bind /dev/null` → o agente lê
    inacessível, nunca o segredo. Sem isto o `--ro-bind / /` o exporia e o require-token
    do control-plane seria contornável (o agente lê o token e o apresenta)."""
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    base = tmp_path
    (base / "web_token").write_text("SEGREDO")  # precisa existir p/ o wrap montar
    bus = base / "ask-bus"
    bus.mkdir()
    prof = load_profiles()["claude"]
    ws = tmp_path / "ws"
    ws.mkdir()
    args = agent_argv(prof, str(ws), node="claude-2", ask_bus_dir=str(bus))
    tok = str(base / "web_token")
    # existe o par --ro-bind /dev/null <token>?
    hit = any(args[i] == "--ro-bind" and args[i + 1] == "/dev/null" and args[i + 2] == tok
              for i in range(len(args) - 2))
    assert hit, "web_token NÃO escondido do sandbox (secret_files ausente)"


def test_wrap_secret_files_pula_inexistente(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "bwrap_available", lambda: True)
    ws = tmp_path / "ws"
    ws.mkdir()
    args = sandbox.wrap(["cli"], workspace=ws, secret_files=[str(tmp_path / "nao-existe")])
    assert "/dev/null" not in args  # arquivo ausente → não monta (idempotente)
