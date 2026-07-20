"""Helpers de agentes p/ o canvas nativo (V6-S3), sem GTK (testável).

Monta o comando do agente INTERATIVO confinado por bwrap (você digita no
terminal real). Reusa adapters + sandbox da engine — mesmo confinamento (ADR-6),
nenhum bypass.
"""

from __future__ import annotations

import os
import shlex
import shutil

from ..engine.accounts import Account, ensure_config_dir, mask_paths
from ..engine.adapters.base import AgentProfile, load_profiles
from ..engine.sandbox import wrap as sandbox_wrap

# cores por estado (mesma paleta da Web)
STATE_COLORS = {
    "idle": "#6b7280",
    "busy": "#3b82f6",
    "waiting": "#f59e0b",  # "é sua vez": agente parou esperando seu input (âmbar)
    "blocked": "#f38ba8",  # bloqueado por dependência: Mocha red (distinto do âmbar "é sua vez")
    "failed": "#ef4444",
    "done": "#22c55e",
}


def installed_agents() -> dict[str, AgentProfile]:
    """Perfis cujo CLI está instalado (binário no PATH)."""
    return {n: p for n, p in load_profiles().items() if shutil.which(p.cmd[0])}


def agent_argv(
    profile: AgentProfile,
    workspace: str,
    *,
    node: str | None = None,
    ask_bus_dir: str | None = None,
    auto_approve: bool = False,
    resume_session: str | None = None,
    account: Account | None = None,
    node_env_keys: frozenset[str] = frozenset(),
) -> list[str]:
    """argv do agente INTERATIVO (binário sem -p) confinado por bwrap.

    A IA roda DENTRO de um shell: ao sair da IA (ex.: ``/exit``), o card vira um
    terminal normal (shell) no mesmo sandbox — comportamento do Maestri. Reabrir a
    IA é só digitar o comando dela de novo.

    Se ``node`` e ``ask_bus_dir`` forem dados, monta **só a box do agente** (ADR-17:
    ``<bus>/box/<nó>``, bind RW isolado — identidade por canal) e injeta
    MAESTRO_NODE/MAESTRO_ASK_BUS/MAESTRO_BIN — habilita ``maestro-ask``/``maestri``
    de dentro do sandbox. **NUNCA** montar o ``<bus>`` inteiro (conteria as boxes
    irmãs → spoofing); a segurança vem da AUSÊNCIA do mount das outras boxes.

    ``resume_session`` (unload — Bloco C): argv ONE-SHOT de retomada — o chamador NÃO
    deve persisti-lo como argv base (docs/21 §3.6). Modo "flag" (claude): anexa os
    flags de resume do adapter com o id capturado (``--resume <id>``). Modo
    "subcommand" (codex): ``<cli> resume`` abre o PICKER do CLI (não há captura
    por-workspace; o humano escolhe) e NÃO anexa flags de permissão — o subcomando
    resume não os aceita (mesmo precedente do headless em ``adapters/base.py``).

    ``account`` (docs/31/ADR-28): conta isolada do nó — SUBSTITUI (não acrescenta —
    emenda E1 do Fable: acrescentar deixaria o ~/.claude do dono RW dentro do nó) os
    rw_paths de config do adapter pelo config-dir da conta e seta a var oficial
    (CLAUDE_CONFIG_DIR/CODEX_HOME) via --setenv. ``node_env_keys`` = chaves que o env
    POR NÓ define (nó vence conta — E6). A raiz das contas é SEMPRE mascarada
    (tmpfs), inclusive em nó default (E5) — nó não lê credencial de outra conta.
    """
    shared = []
    setenv = {}
    if node and ask_bus_dir:
        bus = str(ask_bus_dir)
        box = os.path.join(bus, "box", node)  # caixa privada deste agente (RW)
        os.makedirs(box, mode=0o700, exist_ok=True)  # existe antes do bind do bwrap
        bin_dir = os.path.join(bus, "bin")  # shims (RO via --ro-bind / /), na PATH
        shared = [box]  # bind RW SÓ da própria box — não o <bus> pai
        base_path = os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
        setenv = {
            "MAESTRO_NODE": node,
            "MAESTRO_ASK_BUS": box,  # a box (contém o socket 'sock')
            "MAESTRO_BIN": bin_dir,  # caminho absoluto dos shims (imune ao reset de PATH)
            "PATH": f"{bin_dir}:{base_path}",
        }
    # roda a IA dentro de um shell e, ao sair dela, mantém um shell interativo.
    # auto_approve: anexa as flags de "sem prompt" do CLI (só quando o nó pede; o
    # confinamento real é o bwrap — ADR-6). Flags declaradas no [interactive] do TOML.
    launch = profile.cmd[0]
    resume_subcmd = resume_session is not None and profile.session_mode == "subcommand"
    if resume_subcmd:
        launch += " resume"  # picker do CLI (codex); sem flags de permissão (não aceita)
    elif resume_session and profile.session_resume:
        flags = [a.replace("{id}", resume_session) for a in profile.session_resume]
        launch += " " + " ".join(shlex.quote(a) for a in flags)
    if auto_approve and profile.interactive_auto_approve and not resume_subcmd:
        launch += " " + " ".join(shlex.quote(a) for a in profile.interactive_auto_approve)
    inner = ["/bin/bash", "-c", f"{launch}; exec /bin/bash -i"]
    rw = profile.rw_paths
    if account is not None:  # conta isolada: config-dir SUBSTITUI os paths default (E1)
        rw = [ensure_config_dir(account)]
        setenv.update(account.sandbox_env(skip=node_env_keys))
    return sandbox_wrap(
        inner,
        workspace=workspace,
        rw_paths=rw,
        shared_paths=shared,
        setenv=setenv,
        # some a raiz das contas de TODO nó, inclusive default (E5); root injetável (teste).
        # As máscaras das boxes IRMÃS do ask-bus (S1) e do token do web (S4) moram no PRÓPRIO
        # wrap() — cobrem TODO spawn (interativo + headless/floor), não só este caminho; a
        # própria box reaparece por `shared_paths=[box]` (ordem tmpfs→bind no wrap).
        mask_paths=mask_paths(account.root if account is not None else None),
    )
