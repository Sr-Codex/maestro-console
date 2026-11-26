"""Config do CLI do agente em camada DESCARTÁVEL + sockets do host escondidos (ADR-31).

Problema (medido no device em 2026-11-25): o perfil do claude/codex montava `~/.claude`,
`~/.claude.json` e `~/.codex` em leitura/ESCRITA dentro do sandbox. Um agente gravava ali
hooks/`apiKeyHelper`/`mcpServers`/`mcp_servers` e o CLI do DONO os executava depois, FORA
do sandbox. E o D-Bus da sessão (`/run/user/<uid>/bus`) deixava o agente pedir ao
`systemd --user` um comando no host. As duas portas fecham AQUI, chamadas pelo `wrap()`
(camada compartilhada: interativo, headless e floors — a lição do S1/S4).

Desenho (o agente trabalha com uma FOTOCÓPIA da config do dono):

- `~/.claude`, `~/.codex`, `~/.config/{claude,codex}` → overlay descartável (`--overlay-src
  D --tmp-overlay D`): o agente lê a config real e o que escreve some ao sair.
- Credencial (`.credentials.json`, `auth.json`) → cópia POR NÓ, somente-leitura, SEM o
  token de renovação. O refresh token é de uso único: se o nó o gastasse, o login do dono
  cairia. Sem estado de nó (ou nó de conta), a credencial real some (`/dev/null`).
- `~/.claude.json` → cópia por nó, regravada a cada spawn (vê as mudanças do dono).
- `~/.claude/projects/<slug do workspace>` → o dir REAL, só o do nó: transcript, custo,
  retomada e recuperação pós-crash continuam lendo do lugar de sempre. ATENÇÃO: é gravável
  pelo agente por inteiro, inclusive `memory/` (carregada como instrução por um Claude que
  rode COM ESTE workspace como cwd) — mesma classe do `CLAUDE.md`/`.claude/settings.json` que
  ele já escreve no próprio workspace: o dono não deve rodar o CLI do host ali sem revisar.
- `~/.codex/sessions` e `~/.codex/config.toml` → por nó (`<estado>/codex/`); o config é a
  cópia do real + confiança no workspace do nó (senão o Codex perguntaria a cada spawn).
- Sockets do host escondidos (tmpfs): `/run/user/<uid>` (D-Bus da sessão, ssh-agent, gpg,
  chaveiro), `/run/dbus` (bus do sistema), `~/.ssh/agent`, `~/.claude/daemon`.

Renovação (decisão do usuário, opção A): o CLI do dono renova a credencial real; o app
espelha o access token novo nas cópias (`sync_credentials`, no spawn e num timer do
canvas), escrevendo NO MESMO inode — o nó vivo vê a troca. Gi-free (testável no .venv).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .session_capture import project_slug

# dirs de config dos CLIs: viram overlay descartável em TODO spawn
CONFIG_DIRS = (".claude", ".codex", ".config/claude", ".config/codex")
CLAUDE_JSON = ".claude.json"
CLAUDE_CRED = ".claude/.credentials.json"
CODEX_AUTH = ".codex/auth.json"
# dentro do $HOME: sockets/segredos de controle que o agente alcançaria por leitura+connect
HIDDEN_HOME_DIRS = (".claude/daemon", ".ssh/agent")

_NODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_REFRESH_RE = re.compile(r"^refresh_?token$", re.IGNORECASE)


class AgentHomeError(RuntimeError):
    """Estado do nó não pôde ser preparado com segurança — o spawn deve ser recusado."""


def user_home() -> Path:
    """$HOME do dono (ponto único — os testes trocam por uma HOME falsa)."""
    return Path.home()


def state_root() -> Path:
    """Raiz do estado POR NÓ (mascarada em todo spawn: um nó não lê a cópia de outro)."""
    from ..bootstrap import default_home  # import local: evita ciclo (bootstrap → engine)
    return default_home() / "agent-state"


def node_dir(node: str) -> Path:
    if not _NODE_RE.match(node or ""):
        raise AgentHomeError(f"id de nó inválido para estado do agente: {node!r}")
    return state_root() / node


def codex_home(node: str) -> Path:
    """Onde ficam as sessões do Codex do nó (`<este>/sessions`) — o leitor de custo usa."""
    return node_dir(node) / "codex"


def hidden_system_dirs() -> list[str]:
    """Dirs do SISTEMA com sockets do usuário/sessão (tmpfs por cima em todo spawn)."""
    return [f"/run/user/{os.getuid()}", "/run/dbus"]


# -- escrita ------------------------------------------------------------------


def _write_inplace(path: Path, data: bytes) -> None:
    """Regrava NO MESMO inode (o bind de um nó vivo continua apontando pra ele)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, data)
    finally:
        os.close(fd)


def _write_atomic(path: Path, data: bytes) -> None:
    """Arquivo NOVO + rename: o nó vivo segue com a versão dele; o próximo spawn pega esta."""
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    os.replace(tmp, path)


# -- credencial sem token de renovação ----------------------------------------


def _scrub(obj, blank):
    if isinstance(obj, dict):
        return {k: (blank if _REFRESH_RE.match(str(k)) else _scrub(v, blank))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub(v, blank) for v in obj]
    return obj


def scrubbed_credential(src: Path, blank) -> bytes | None:
    """Conteúdo da cópia do nó: a credencial real SEM nenhum refresh token. None = não dá
    pra montar com segurança (ausente, symlink, ilegível ou JSON inválido)."""
    if not src.is_file():  # segue symlink do PRÓPRIO dono ($HOME é ro pro agente)
        return None
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return json.dumps(_scrub(data, blank)).encode()


_CREDS = (  # (origem relativa ao $HOME, arquivo da cópia no estado do nó, valor do token)
    (CLAUDE_CRED, "claude-credentials.json", None),  # medido: claude aceita null
    (CODEX_AUTH, "codex-auth.json", ""),  # medido: codex aceita ""
)


def sync_credentials(node: str | None = None) -> None:
    """Espelha a credencial real (sem refresh token) nas cópias dos nós — `node` ou todos.

    In-place e só quando mudou. Origem ilegível/no meio de uma regravação → mantém a cópia
    (o access token nela vence sozinho; regravar vazio derrubaria o nó à toa)."""
    home = user_home()
    if node is not None:
        dirs = [node_dir(node)]
    else:
        root = state_root()
        dirs = [d for d in root.iterdir() if d.is_dir() and not d.is_symlink()] \
            if root.is_dir() else []
    for rel, name, blank in _CREDS:
        data = scrubbed_credential(home / rel, blank)
        if data is None:
            continue
        for d in dirs:
            dst = d / name
            try:
                if dst.is_symlink():
                    dst.unlink()
                if not dst.exists() or dst.read_bytes() != data:
                    _write_inplace(dst, data)
            except OSError:
                continue  # um nó com problema não impede os outros


# -- preparo por spawn --------------------------------------------------------


@dataclass(frozen=True)
class NodeState:
    node: str
    dir: Path
    workspace: str


def _toml_key(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def codex_config_for(real: Path, workspace: str) -> bytes:
    """config.toml do nó = o real + confiança no workspace do nó (se o real já não tiver).
    Se o acréscimo quebrar o TOML (ex.: tabela já existe noutra grafia), fica só o real."""
    base = real.read_text(encoding="utf-8") if real.is_file() and not real.is_symlink() else ""
    header = f"[projects.{_toml_key(workspace)}]"
    if header in base:
        return base.encode()
    out = f"{base.rstrip()}\n\n{header}\ntrust_level = \"trusted\"\n".lstrip()
    try:
        tomllib.loads(out)
    except tomllib.TOMLDecodeError:
        return base.encode()
    return out.encode()


def prepare(node: str, workspace: str) -> NodeState:
    """Cria/atualiza o estado do nó ANTES do spawn (o bwrap não monta o que não existe)."""
    d = node_dir(node)
    for p in (state_root(), d):
        if p.is_symlink():
            raise AgentHomeError(f"estado do agente é symlink: {p}")
        p.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(p, 0o700)
    sync_credentials(node)
    cj = _real(CLAUDE_JSON)
    if cj is not None and cj.is_file():
        _write_atomic(d / "claude.json", cj.read_bytes())
    claude = _real(".claude")
    if claude is not None and claude.is_dir():  # o bwrap não monta destino inexistente
        (claude / "projects" / project_slug(workspace)).mkdir(
            mode=0o700, parents=True, exist_ok=True)
    codex = _real(".codex")
    if codex is not None and codex.is_dir():
        cx = d / "codex"
        (cx / "sessions").mkdir(mode=0o700, parents=True, exist_ok=True)
        _write_atomic(cx / "config.toml", codex_config_for(codex / "config.toml", workspace))
    return NodeState(node=node, dir=d, workspace=workspace)


def remove(node: str) -> None:
    """Apaga o estado do nó (✕ fechar = de vez): id reciclado não herda sessões/credencial."""
    try:
        d = node_dir(node)
    except AgentHomeError:
        return
    if d.is_symlink():
        d.unlink()
    elif d.is_dir():
        shutil.rmtree(d, ignore_errors=True)


# -- mounts -------------------------------------------------------------------


def _real(rel: str) -> Path | None:
    """Caminho REAL de um item do $HOME do dono (segue symlink: um `~/.claude` que aponta
    pra outro lugar ganha o overlay no ALVO). O $HOME é ro no sandbox, então o agente não
    troca o link. None = não existe."""
    p = user_home() / rel
    if not (p.exists() or p.is_symlink()):
        return None
    return p.resolve() if p.exists() else None


def mounts(state: NodeState | None) -> list[str]:
    """Args do bwrap da camada descartável. Entram DEPOIS dos binds rw/shared (vencem um
    rw_path que cubra a config) e ANTES dos ro_paths. `state=None` (nó de conta, ou um
    chamador sem id) = overlay + credencial real escondida: fecha a fuga e não loga."""
    args: list[str] = []
    for rel in CONFIG_DIRS:
        d = _real(rel)
        if d is not None and d.is_dir():
            args += ["--overlay-src", str(d), "--tmp-overlay", str(d)]
    cj = _real(CLAUDE_JSON)
    if cj is not None and cj.is_file():
        copy = state.dir / "claude.json" if state is not None else None
        if copy is not None and copy.is_file():
            args += ["--bind", str(copy), str(cj)]
        else:
            args += ["--ro-bind", str(cj), str(cj)]
    for rel, name, _ in _CREDS:
        dst = _real(rel)
        if dst is None:
            continue
        copy = state.dir / name if state is not None else None
        src = str(copy) if copy is not None and copy.is_file() else "/dev/null"
        args += ["--ro-bind", src, str(dst)]
    if state is not None:
        claude = _real(".claude")
        if claude is not None and claude.is_dir():
            slug = str(claude / "projects" / project_slug(state.workspace))
            args += ["--bind", slug, slug]
        codex, cx = _real(".codex"), state.dir / "codex"
        if codex is not None and codex.is_dir() and cx.is_dir():
            args += ["--bind", str(cx / "sessions"), str(codex / "sessions"),
                     "--bind", str(cx / "config.toml"), str(codex / "config.toml")]
    for rel in HIDDEN_HOME_DIRS:
        d = _real(rel)
        if d is not None and d.is_dir():
            args += ["--tmpfs", str(d)]
    return args


def is_protected(path: str | Path) -> bool:
    """True se `path` é (ou fica dentro de) um dir de config protegido ou o ~/.claude.json —
    um rw_path assim seria a fuga; o `wrap()` o ignora (a camada descartável já cobre)."""
    real = Path(path).expanduser().resolve()
    home = user_home()
    roots = [(home / r).resolve() for r in (*CONFIG_DIRS, CLAUDE_JSON)]
    return any(real == r or r in real.parents for r in roots)


def protected_roots() -> list[Path]:
    """Dirs de config protegidos (o `floors` recusa projeto dentro deles)."""
    home = user_home()
    return [(home / r).resolve() for r in CONFIG_DIRS]
