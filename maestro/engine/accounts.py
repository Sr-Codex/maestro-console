"""Contas por nó — config-dir isolado por terminal (docs/31 / ADR-28).

Uma **conta** = nome + diretório de config isolado do CLI (`CLAUDE_CONFIG_DIR` pro
claude, `CODEX_HOME` pro codex) + env extra. Escolhida SÓ pelo humano na UI (host-only,
ADR-17); NUNCA rotação automática nem fallback silencioso pro `~/.claude` (docs/31 §5).

Este módulo é o **resolvedor único** (docs/31 §4.3, emenda E4 do Fable): engine
(delegate/ask/chain/routine) e canvas consomem a MESMA resolução `agent_id → conta`,
lendo o Store (`ui_state`: registro em `accounts`, associação em `nodecfg_<nid>_account`).
Gi-free (testável no .venv).

O config-dir é DERIVADO do nome (slug congelado na criação) sob a raiz única
`~/.maestro-accounts/<agent>/<slug>/` — a raiz única viabiliza a máscara tmpfs no
sandbox (§5.3: um nó não enxerga credencial das outras contas).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ACCOUNTS_KEY = "accounts"  # ui_state: JSON [{name, agent, slug, env}]
_NODE_KEY = "nodecfg_{nid}_account"  # associação por nó (mesmo trilho do node_cfg)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def accounts_root() -> Path:
    """Raiz única de TODOS os config-dirs de conta (docs/31 D2)."""
    return Path.home() / ".maestro-accounts"


def env_var_for(agent: str) -> str:
    """Variável oficial de config-dir do CLI: CODEX_HOME (codex) / CLAUDE_CONFIG_DIR."""
    return "CODEX_HOME" if "codex" in (agent or "").lower() else "CLAUDE_CONFIG_DIR"


def slugify(name: str) -> str:
    """Slug do config-dir (congela na criação; renomear NÃO move dir — docs/31 §4.1)."""
    s = _SLUG_RE.sub("-", (name or "").strip().lower()).strip("-")
    return s or "conta"


def parse_env(text: str) -> dict[str, str]:
    """Linhas KEY=VALUE → dict (mesmo formato do env por nó; '#' comenta)."""
    out: dict[str, str] = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


@dataclass(frozen=True)
class Account:
    name: str
    agent: str  # base do CLI ("claude" | "codex")
    slug: str
    env: str = ""  # env extra (texto KEY=VALUE por linha)
    root: Path | None = field(default=None, compare=False)  # injetável p/ teste

    def config_dir(self) -> Path:
        return (self.root or accounts_root()) / self.agent / self.slug

    def sandbox_env(self, skip: frozenset[str] = frozenset()) -> dict[str, str]:
        """setenv da conta: var oficial do config-dir + env extra. `skip` = chaves que o
        env POR NÓ define (nó vence conta — docs/31 E6: o --setenv do bwrap sobrescreve
        o env herdado, então a conta precisa OMITIR o que o nó já setou)."""
        out = {k: v for k, v in parse_env(self.env).items() if k not in skip}
        out[env_var_for(self.agent)] = str(self.config_dir())
        return out


def ensure_config_dir(account: Account) -> str:
    """Cria o config-dir ANTES do spawn (o guard `exists()` do sandbox descarta path
    inexistente em silêncio — docs/31 §2) e devolve o caminho como str."""
    d = account.config_dir()
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    return str(d)


def mask_paths(root: Path | None = None) -> list[str]:
    """Paths a MASCARAR (tmpfs) em TODO spawn de agente — inclusive nós default (E5):
    sem isso, qualquer nó lê ro as credenciais de todas as contas via `--ro-bind / /`."""
    return [str(root or accounts_root())]


# -- registro (ui_state, host-only) -----------------------------------------


def list_accounts(store, *, root: Path | None = None) -> list[Account]:
    raw = store.get_ui(ACCOUNTS_KEY)
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except (ValueError, TypeError):
        return []
    out = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict) or not it.get("name") or not it.get("agent"):
            continue
        out.append(Account(name=str(it["name"]), agent=str(it["agent"]),
                           slug=str(it.get("slug") or slugify(str(it["name"]))),
                           env=str(it.get("env") or ""), root=root))
    return out


def save_accounts(store, accounts: list[Account]) -> None:
    store.set_ui(ACCOUNTS_KEY, json.dumps(
        [{"name": a.name, "agent": a.agent, "slug": a.slug, "env": a.env}
         for a in accounts]))


def find_account(store, name: str, agent: str | None = None,
                 *, root: Path | None = None) -> Account | None:
    """Conta por nome (e agente, se dado). None = não registrada."""
    for a in list_accounts(store, root=root):
        if a.name == name and (agent is None or a.agent == agent):
            return a
    return None


def add_account(store, name: str, agent: str, env: str = "",
                *, root: Path | None = None) -> Account | None:
    """Registra + cria o config-dir. None se nome vazio/duplicado (mesmo agente)."""
    name = (name or "").strip()
    if not name or find_account(store, name, agent, root=root) is not None:
        return None
    accts = list_accounts(store, root=root)
    slug = slugify(name)
    while any(a.agent == agent and a.slug == slug for a in accts):
        slug += "-2"  # colisão de slug (nomes distintos, mesmo slug) → sufixo
    acct = Account(name=name, agent=agent, slug=slug, env=env, root=root)
    accts.append(acct)
    save_accounts(store, accts)
    ensure_config_dir(acct)
    return acct


def remove_account(store, name: str, agent: str, *, root: Path | None = None) -> bool:
    """Desregistra (o dir FICA no disco — credencial não se apaga por engano, §4.1)."""
    accts = list_accounts(store, root=root)
    keep = [a for a in accts if not (a.name == name and a.agent == agent)]
    if len(keep) == len(accts):
        return False
    save_accounts(store, keep)
    return True


# -- resolução nó → conta (o invariante em todas as entradas) ----------------


def node_account_name(store, nid: str) -> str:
    """Nome da conta associada ao nó ('' = default ~/.claude|~/.codex)."""
    v = store.get_ui(_NODE_KEY.format(nid=nid))
    return str(v) if v else ""


def resolve(store, agent_id: str, agent: str | None = None,
            *, root: Path | None = None) -> Account | None:
    """agent_id (nid) → Account, ou None (= default, SÓ quando o nó não tem conta).

    Associação órfã (nó aponta conta que sumiu do registro — a UI evita, E8b): NUNCA
    cair calado pro default (§5.2 — seria vazamento de conta). Sintetiza a conta pelo
    nome (slug derivado, sem env extra) se o `agent` for conhecido; o dir renasce vazio
    e o CLI pede login. Sem `agent` não há como derivar a var/dir → None (documentado:
    só acontece pra nid fora do roster)."""
    if store is None or not agent_id:
        return None
    name = node_account_name(store, agent_id)
    if not name:
        return None
    acct = find_account(store, name, agent, root=root)
    if acct is None and agent:
        acct = Account(name=name, agent=agent, slug=slugify(name), env="", root=root)
    return acct
