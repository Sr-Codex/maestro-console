"""Sandbox de SO via bwrap (bubblewrap) — confinamento estrito (E2-S2 / ADR-6).

Envelopa o comando do agente para garantir, no nível do SO:
- **workspace**: leitura/escrita;
- **/tmp**: privado por execução (tmpfs), NÃO o /tmp compartilhado do host;
- **resto do sistema**: somente leitura;
- **rede**: mantida (agentes dependem de API);
- config do CLI (~/.claude, ~/.codex): FOTOCÓPIA descartável + credencial sem token de
  renovação (ADR-31, `agent_home`); sockets da sessão do usuário (D-Bus, ssh-agent) escondidos;
- **sem flags de bypass**.

Se o bwrap não existir, **falha de forma segura** (não roda sem sandbox).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path


class SandboxUnavailable(RuntimeError):
    """Sandbox não pode ser montado por inteiro — recusamos executar (fail-safe)."""


def bwrap_available() -> bool:
    return shutil.which("bwrap") is not None


_OVERLAY_MIN = (0, 11)  # `--overlay-src`/`--tmp-overlay` entraram no bubblewrap 0.11.0 (NEWS)
_bwrap_version_cache: tuple[int, ...] | None = None


def bwrap_version() -> tuple[int, ...]:
    """Versão do bwrap instalado (cache). () = não deu pra ler."""
    global _bwrap_version_cache
    if _bwrap_version_cache is None:
        try:
            out = subprocess.run(["bwrap", "--version"], capture_output=True, text=True,
                                 timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            out = ""
        m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", out)
        _bwrap_version_cache = tuple(int(g) for g in m.groups() if g) if m else ()
    return _bwrap_version_cache


def _ask_bus_box_dir() -> str | None:
    """Diretório-pai das boxes de socket dos agentes (`<home>/ask-bus/box`) — mascarado em
    TODO spawn (S1). Import local de `default_home` evita ciclo em import-time (bootstrap
    importa a engine). `None` se nem existe (nenhuma box criada ainda → nada a esconder)."""
    from ..bootstrap import default_home  # import local: evita ciclo
    box = default_home() / "ask-bus" / "box"
    return str(box) if box.exists() else None


def _host_secret_files() -> list[str]:
    """Arquivos host-only a ESCONDER do agente em TODO spawn (S4): o token do web, que o
    `--ro-bind / /` reexporia (o agente co-local o leria e forjaria autoridade no control-plane
    mesmo com o token exigido). Import local evita ciclo (bootstrap importa a engine)."""
    from ..bootstrap import default_home  # import local: evita ciclo
    from ..web.security import web_token_path
    return [str(web_token_path(default_home()))]


def invisible_prefixes() -> list[str]:
    """Prefixos do HOST que NÃO existem (ou são outros) dentro do sandbox de um nó —
    fonte única pro `needs_copy` do paste/drop (docs/32 E3): `--tmpfs /tmp` (privado),
    a máscara tmpfs da raiz das contas (ADR-28), `/dev`/`/proc` remontados e o
    runtime-dir do usuário (sockets/portais FUSE, acesso frágil no userns). Mudou um
    mount do `wrap()`? Atualize AQUI junto."""
    from . import agent_home  # import local: evita ciclo em import-time
    from .accounts import accounts_root
    return ["/tmp", str(accounts_root()), "/dev", "/proc", *agent_home.hidden_system_dirs(),
            str(agent_home.state_root())]


def wrap(
    inner_argv: Sequence[str],
    *,
    workspace: str | Path,
    rw_paths: Sequence[str] = (),
    shared_paths: Sequence[str] = (),
    setenv: Mapping[str, str] | None = None,
    allow_network: bool = True,
    mask_paths: Sequence[str] = (),
    ro_paths: Sequence[str] = (),
    node: str | None = None,
) -> list[str]:
    """Retorna o argv do agente envelopado em bwrap. Levanta se bwrap ausente.

    rw_paths: dirs extras rw. Um que seja (ou caia dentro de) config de CLI protegida
        (`agent_home.is_protected`, ex.: ~/.claude) é IGNORADO — vira a camada descartável.
    node: id do nó dono do spawn (ADR-31) — dá a ele a credencial sem refresh token, o
        `~/.claude.json` e as sessões do Codex DELE. None (ex.: nó de conta, que usa o
        config-dir da conta) = camada descartável sem credencial do dono.
    shared_paths: diretórios de artefatos compartilhados entre agentes (rw).
    setenv: variáveis de ambiente a injetar no sandbox (ex.: MAESTRO_NODE).
    ro_paths: travados em somente-leitura POR CIMA de todo bind rw (ADR-30, ex.: `.git` do
        floor) — proteção positiva, não por ausência de bind (a lição do S1). Ausente = FALHA:
        seguir sem a trava rodaria o agente desprotegido.
    mask_paths: diretórios ESCONDIDOS do agente via tmpfs (docs/31 §5.3: a raiz das
    contas — credencial de outra conta some da vista). A ORDEM importa (bwrap monta
    em sequência): o tmpfs entra ANTES dos binds de rw_paths/shared_paths, pra um
    bind dentro da raiz mascarada (a PRÓPRIA conta do nó) reaparecer por cima.

    Esconde AUTOMATICAMENTE (todo spawn, na CAMADA de sandbox — não no chamador) os
    ARQUIVOS host-only que o `--ro-bind / /` reexporia legíveis: o **token do web**
    (`<home>/web_token`, S4 do review docs/33) via `--ro-bind /dev/null` (o agente lê
    "inacessível", nunca o segredo; tmpfs não serve p/ arquivo). Cobre interativo E
    headless/floor (`run_agent`).
    """
    if not bwrap_available():
        raise SandboxUnavailable("bwrap não encontrado; recusando rodar sem sandbox")
    if bwrap_version() < _OVERLAY_MIN:  # sem overlay a config do dono ficaria exposta
        raise SandboxUnavailable("bubblewrap >= 0.11 necessário (camada descartável da config)")
    from . import agent_home  # import local: evita ciclo em import-time
    ws = str(Path(workspace).resolve())
    try:
        state = agent_home.prepare(node, ws) if node else None
    except (agent_home.AgentHomeError, OSError) as exc:
        raise SandboxUnavailable(f"estado do agente indisponível: {exc}") from exc
    args: list[str] = [
        "bwrap",
        "--ro-bind",
        "/",
        "/",  # sistema inteiro: somente leitura
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--tmpfs",
        "/tmp",  # /tmp privado (tmpfs), some ao terminar
        "--bind",
        ws,
        ws,  # workspace: leitura/escrita
        "--chdir",
        ws,
        # --unshare-pid: bwrap vira PID 1 do namespace → SIGKILL nele colapsa TODA a árvore
        # interna (codex/bash). Sem isso, --die-with-parent sozinho VAZA netos (bubblewrap#529).
        "--unshare-pid",
        "--die-with-parent",  # rede de segurança: filhos morrem se o app morre
        # ADR-17: dropar TODAS as capabilities fecha o remount-rw (bubblewrap#287) — o
        # agente não consegue remontar o `--ro-bind /` nem o `bin/` para escrever.
        "--cap-drop",
        "ALL",
    ]
    if not allow_network:
        args += ["--unshare-net"]
    # S1 (review docs/33): esconde as boxes IRMÃS do ask-bus de TODO agente — o `--ro-bind / /`
    # reexpõe `<bus>/box/<todos>` (sob $HOME) e um agente conectaria no socket de outro → o host
    # carimba `frm=vítima` (spoof de identidade; colapsa o invariante-mãe do ADR-17). A PRÓPRIA
    # box reaparece pelo `--bind` de shared_paths (que vem DEPOIS). Fica AQUI, na camada de
    # sandbox — não no chamador — pra cobrir interativo E headless/floor (run_agent), senão o
    # spoof continua pelo caminho que não replicar a máscara.
    bus_box = _ask_bus_box_dir()
    mask_all = [*mask_paths, bus_box] if bus_box else list(mask_paths)
    # ADR-31: sockets da sessão do usuário (D-Bus → `systemd-run --user` roda NO HOST;
    # ssh-agent, gpg, chaveiro) e o estado por nó das cópias de config (um nó não lê o de outro)
    mask_all += [*agent_home.hidden_system_dirs(), str(agent_home.state_root())]
    for p in mask_all:  # ANTES dos binds rw/shared (ordem de mount — ver docstring)
        mp = str(Path(p).expanduser())
        if Path(mp).exists():
            args += ["--tmpfs", mp]  # esconde (ex.: contas alheias, boxes irmãs); vazio e volátil
    for sf in _host_secret_files():  # arquivos host-only: overlay /dev/null → inacessível
        if Path(sf).exists():
            args += ["--ro-bind", "/dev/null", sf]
    for p in rw_paths:
        rp = str(Path(p).expanduser())
        if Path(rp).exists() and not agent_home.is_protected(rp):
            args += ["--bind", rp, rp]  # extra rw; config de CLI protegida NUNCA (ADR-31)
    for p in shared_paths:
        sp = str(Path(p).resolve())
        if Path(sp).exists():
            args += ["--bind", sp, sp]  # artefatos compartilhados: rw
    # ADR-31: config dos CLIs = fotocópia descartável. DEPOIS dos binds rw/shared/workspace —
    # vence qualquer um que a cubra (ex.: um rw_path = $HOME) — e ANTES das travas ro.
    args += agent_home.mounts(state)
    for p in ro_paths:  # por ÚLTIMO entre os mounts: vence workspace/rw/shared
        lp = str(Path(p))
        # bwrap segue symlink no DESTINO: a trava cairia noutro arquivo
        if Path(lp).is_symlink() or not Path(lp).exists():
            raise SandboxUnavailable(f"caminho a proteger ausente ou symlink: {lp}")
        args += ["--ro-bind", lp, lp]
    for k, v in (setenv or {}).items():
        args += ["--setenv", str(k), str(v)]  # ex.: MAESTRO_NODE / MAESTRO_ASK_BUS
    args.append("--")
    args.extend(inner_argv)
    return args
