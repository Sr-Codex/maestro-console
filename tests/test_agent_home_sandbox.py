"""ADR-31: o agente não escreve na config do CLI do dono nem fala com o D-Bus da sessão.

Roda o `sandbox.wrap()` de VERDADE (bwrap real) numa HOME falsa — os ataques medidos no
device em 2026-11-25 (hooks em settings.json, mcpServers em ~/.claude.json, mcp_servers no
config.toml do codex, troca do binário do codex, `systemd-run --user` via D-Bus) não
podem chegar ao host. E o lado funcional: credencial sem refresh token, sessão do nó
persistida, espelho da credencial renovada num nó vivo.
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from maestro.engine import agent_home, sandbox
from maestro.engine.session_capture import project_dir

pytestmark = pytest.mark.skipif(
    not sandbox.bwrap_available() or sandbox.bwrap_version() < sandbox._OVERLAY_MIN,
    reason="requer bubblewrap >= 0.11 (overlay)",
)

CRED = {"claudeAiOauth": {"accessToken": "AT-1", "refreshToken": "RT-SEGREDO",
                          "expiresAt": 1},
        "mcpOAuth": {"srv": {"accessToken": "m", "refreshToken": "RT-MCP"}}}
AUTH = {"tokens": {"access_token": "CX-1", "refresh_token": "RT-CODEX"}}


@pytest.fixture
def casa(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".claude/.git/hooks").mkdir(parents=True)
    (home / ".claude/daemon").mkdir()
    (home / ".claude/daemon/control.key").write_text("CHAVE")
    (home / ".claude/settings.json").write_text("{}")
    (home / ".claude/.credentials.json").write_text(json.dumps(CRED))
    (home / ".claude.json").write_text('{"mcpServers": {}}')
    (home / ".codex/sessions").mkdir(parents=True)
    (home / ".codex/sessions/antiga.jsonl").write_text("velha")
    (home / ".codex/packages").mkdir()
    (home / ".codex/packages/codex").write_text("binario-original")
    (home / ".codex/config.toml").write_text('model = "x"\n')
    (home / ".codex/auth.json").write_text(json.dumps(AUTH))
    (home / ".config/claude").mkdir(parents=True)
    (home / ".ssh/agent").mkdir(parents=True)
    (home / ".ssh/agent/s.sock").write_text("")
    monkeypatch.setattr(agent_home, "user_home", lambda: home)
    ws = tmp_path / "ws"
    ws.mkdir()
    return home, ws


def _snap(home: Path) -> dict:
    return {str(p.relative_to(home)): p.read_bytes() for p in sorted(home.rglob("*"))
            if p.is_file()}


def _run(ws, script, **kw):
    argv = sandbox.wrap(["/bin/sh", "-c", script], workspace=ws, **kw)
    return subprocess.run(argv, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                          timeout=60)


ATAQUE = """
H={h}
HOOK='{{"hooks":{{"SessionStart":[{{"hooks":[{{"type":"command","command":"touch /x"}}]}}]}}}}'
echo "$HOOK" > $H/.claude/settings.json
echo '{{"mcpServers":{{"m":{{"command":"/bin/x"}}}}}}' > $H/.claude.json
printf '[mcp_servers.m]\\ncommand = "/bin/x"\\n' >> $H/.codex/config.toml
echo trocado > $H/.codex/packages/codex
echo injetado > $H/.claude/CLAUDE.md
echo '#!/bin/sh' > $H/.claude/.git/hooks/pre-commit
echo x > $H/.config/claude/settings.json
echo novo > $H/.codex/sessions/nova.jsonl
echo antiga-mexida > $H/.codex/sessions/antiga.jsonl 2>/dev/null
echo '{{}}' > $H/.claude/.credentials.json 2>/dev/null
echo '{{}}' > $H/.codex/auth.json 2>/dev/null
echo turno > {slug}/sessao.jsonl
true
"""


def test_ataques_nao_chegam_a_config_do_dono(casa):
    home, ws = casa
    antes = _snap(home)
    slug = project_dir(str(ws.resolve()), home=home)
    r = _run(ws, ATAQUE.format(h=home, slug=slug), node="n1")
    assert r.returncode == 0, r.stderr
    depois = _snap(home)
    novo = str(slug.relative_to(home) / "sessao.jsonl")
    assert depois.pop(novo) == b"turno\n"  # o transcript do NÓ persiste no lugar de sempre
    assert depois == antes  # nada mais mudou: hooks, mcp, binário, CLAUDE.md, git, creds


def test_sessoes_do_codex_e_claude_json_sao_por_no(casa):
    home, ws = casa
    _run(ws, ATAQUE.format(h=home, slug=project_dir(str(ws.resolve()), home=home)),
         node="n1")
    cx = agent_home.codex_home("n1")
    assert (cx / "sessions/nova.jsonl").read_text() == "novo\n"  # persiste no estado do nó
    # a do dono não entra no nó: o "antiga" ali é o que o PRÓPRIO ataque criou do zero
    assert (cx / "sessions/antiga.jsonl").read_text() == "antiga-mexida\n"
    # o que o agente gravou no ~/.claude.json ficou na cópia do nó; o próximo spawn regrava
    assert "/bin/x" in (agent_home.node_dir("n1") / "claude.json").read_text()
    agent_home.prepare("n1", str(ws.resolve()))
    assert "/bin/x" not in (agent_home.node_dir("n1") / "claude.json").read_text()


def test_credencial_do_no_nao_tem_refresh_token(casa):
    home, ws = casa
    r = _run(ws, f"cat {home}/.claude/.credentials.json; echo; cat {home}/.codex/auth.json",
             node="n1")
    assert "AT-1" in r.stdout and "CX-1" in r.stdout  # loga com o access token
    assert "RT-" not in r.stdout  # nenhum refresh token (nem o do MCP)


def test_sem_no_a_credencial_do_dono_some(casa):
    """Nó de conta (ou chamador sem id): overlay continua, credencial do dono = /dev/null."""
    home, ws = casa
    r = _run(ws, f"cat {home}/.claude/.credentials.json {home}/.codex/auth.json; "
                 f"echo x > {home}/.claude/settings.json; cat {home}/.claude/settings.json")
    assert "AT-1" not in r.stdout and "RT-" not in r.stdout and "CX-1" not in r.stdout
    assert r.stdout.strip() == "x"  # escreve no overlay…
    assert (home / ".claude/settings.json").read_text() == "{}"  # …e não no host


def test_sem_no_o_claude_json_do_dono_e_so_leitura(casa):
    home, ws = casa
    _run(ws, f"echo x > {home}/.claude.json")
    assert (home / ".claude.json").read_text() == '{"mcpServers": {}}'


def test_config_que_e_symlink_ganha_overlay_no_alvo(casa, tmp_path):
    """`~/.claude` do dono apontando pra outro lugar: o overlay vai no ALVO — nem o
    rw_path pelo link, nem o caminho real escrevem no host; o nó ainda escreve (overlay)."""
    home, ws = casa
    alvo = tmp_path / "dotfiles-claude"
    (home / ".claude").rename(alvo)
    (home / ".claude").symlink_to(alvo)
    r = _run(ws, f"echo x > {home}/.claude/settings.json && cat {alvo}/settings.json; "
                 f"cat {home}/.claude/.credentials.json", node="n1",
             # a HOME falsa vive no /tmp (privado no sandbox): montá-la rw faz o link existir
             # lá dentro — e ainda prova que nem o $HOME inteiro rw reabre a fuga
             rw_paths=[str(home), str(home / ".claude")])
    assert r.stdout.startswith("x"), r.stderr  # funcional: o CLI do nó grava a config
    assert "AT-1" in r.stdout and "RT-" not in r.stdout
    assert (alvo / "settings.json").read_text() == "{}"  # host intacto


def test_rw_path_que_cobre_a_config_nao_vence(casa):
    """Um rw_path = $HOME (ou ~/.claude) não reabre a fuga: a camada descartável vence."""
    home, ws = casa
    _run(ws, f"echo x > {home}/.claude/settings.json; echo x > {home}/.claude.json",
         node="n1", rw_paths=[str(home), str(home / ".claude")])
    assert (home / ".claude/settings.json").read_text() == "{}"
    assert (home / ".claude.json").read_text() == '{"mcpServers": {}}'


def test_controle_e_sockets_do_host_escondidos(casa, monkeypatch):
    home, ws = casa
    # estado dos nós num lugar que o sandbox ENXERGA (dentro do workspace rw): só a máscara
    # o esconde — no /tmp padrão do teste ele sumiria de qualquer jeito (/tmp privado)
    monkeypatch.setenv("MAESTRO_HOME", str(ws / "mh"))
    run_user = f"/run/user/{os.getuid()}"
    r = _run(ws, f"cat {home}/.claude/daemon/control.key; ls -A {home}/.ssh/agent; "
                 f"for d in {run_user} /run/dbus {agent_home.state_root()}; do ls -A $d; done; "
                 "echo FIM", node="n1")
    assert "CHAVE" not in r.stdout and "s.sock" not in r.stdout
    assert "n1" not in r.stdout  # o estado por nó (cópias) some da vista
    assert r.stdout.split()[-1] == "FIM" and len(r.stdout.split()) == 1, r.stdout


@pytest.mark.skipif(not shutil.which("systemd-run")
                    or not Path(f"/run/user/{os.getuid()}/bus").exists(),
                    reason="sem D-Bus da sessão / systemd-run")
def test_dbus_da_sessao_nao_roda_comando_no_host(casa, tmp_path):
    """A fuga medida: `systemd-run --user` de dentro do sandbox criava o arquivo NO HOST
    (o /tmp do sandbox é privado — só o host enxerga este caminho)."""
    _, ws = casa
    marca = tmp_path / "fugiu"
    _run(ws, f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{os.getuid()}/bus "
             f"timeout 10 systemd-run --user --quiet --wait --collect /usr/bin/touch {marca}",
         node="n1")
    assert not marca.exists()


def test_codex_do_no_confia_no_proprio_workspace(casa):
    home, ws = casa
    r = _run(ws, f"cat {home}/.codex/config.toml", node="n1")
    assert 'model = "x"' in r.stdout  # vê a config do dono…
    assert f'[projects."{ws.resolve()}"]' in r.stdout  # …+ confiança só no workspace dele
    assert "projects" not in (home / ".codex/config.toml").read_text()


def test_credencial_renovada_chega_ao_no_vivo(casa):
    """Opção A: o dono renova; `sync_credentials` reescreve a cópia no MESMO inode e o
    processo que JÁ estava rodando no sandbox lê o token novo."""
    home, ws = casa
    cred = home / ".claude/.credentials.json"
    script = (f"while [ ! -e {ws.resolve()}/vai ]; do sleep 0.1; done; cat {cred}")
    argv = sandbox.wrap(["/bin/sh", "-c", script], workspace=ws, node="n1")
    p = subprocess.Popen(argv, stdout=subprocess.PIPE, text=True, stdin=subprocess.DEVNULL)
    try:
        time.sleep(1.0)  # sandbox de pé, com a cópia antiga montada
        novo = json.loads(json.dumps(CRED))
        novo["claudeAiOauth"].update(accessToken="AT-2", refreshToken="RT-NOVO")
        tmp = cred.with_name("x.tmp")
        tmp.write_text(json.dumps(novo))
        os.replace(tmp, cred)  # o CLI do dono grava por rename
        agent_home.sync_credentials()
        (ws / "vai").touch()
        out, _ = p.communicate(timeout=30)
    finally:
        p.kill()
    assert "AT-2" in out and "RT-" not in out


def test_fechar_o_no_apaga_o_estado(casa):
    _, ws = casa
    agent_home.prepare("n1", str(ws.resolve()))
    assert agent_home.node_dir("n1").is_dir()
    agent_home.remove("n1")
    assert not agent_home.node_dir("n1").exists()


def test_id_de_no_invalido_recusa_o_spawn(casa):
    _, ws = casa
    with pytest.raises(sandbox.SandboxUnavailable):
        sandbox.wrap(["true"], workspace=ws, node="../fora")


def test_bwrap_sem_overlay_recusa_o_spawn(casa, monkeypatch):
    """bubblewrap < 0.11 não tem overlay: seguir exporia a config do dono → recusa."""
    _, ws = casa
    monkeypatch.setattr(sandbox, "bwrap_version", lambda: (0, 10, 0))
    with pytest.raises(sandbox.SandboxUnavailable):
        sandbox.wrap(["true"], workspace=ws, node="n1")
