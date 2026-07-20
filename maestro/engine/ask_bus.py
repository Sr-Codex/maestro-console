"""AskBus — caixa-postal de arquivos do modo interativo de cabos (ADR-11, Fase 1).

Transporte do ``maestro-ask``: o agente (dentro do sandbox bwrap) escreve um pedido
``req-<id>.json`` num diretório montado rw via ``shared_paths``; o host lê, roteia
(ver ``ask_router``) e escreve ``resp-<id>.json``; o cliente do agente lê a resposta.

Protocolo só de ARQUIVOS (stdlib) — sem dependência nova, gi-free e testável.
A entrada do outro agente é tratada como NÃO-CONFIÁVEL (ajuste 2 da pesquisa): tamanho
limitado, campos validados, ``id`` restrito a hex/uuid (sem path traversal). Arquivos
órfãos/velhos são limpos por ``cleanup`` — o host/broker deve sobreviver aos processos
que gera (ajuste 1 da pesquisa).
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .safe_fs import safe_read_text, safe_write_text

ASK_MAX_PROMPT_BYTES = 8192  # teto do prompt cruzado (entrada não-confiável)
_SAFE_ID = re.compile(r"^[0-9a-f]{8,}$")  # uuid4().hex


class AskBusError(Exception):
    """Pedido/resposta malformado ou inválido (entrada não-confiável)."""


@dataclass
class AskRequest:
    id: str
    frm: str  # nó remetente (MAESTRO_NODE)
    to: str  # nó destino (vazio quando é um comando de Maestro mode)
    prompt: str
    depth: int = 0  # profundidade da cadeia A->B->A (anti-loop; setada pelo host)
    cmd: str = ""  # Fase 6: comando Maestro (recruit/list/dismiss/wire/reassign); ""=ask normal
    args: list = field(default_factory=list)  # argumentos do comando


@dataclass
class AskResponse:
    id: str
    ok: bool
    answer: str = ""
    error: str | None = None


def new_id() -> str:
    return uuid.uuid4().hex


def bin_dir(bus_dir: str | Path) -> Path:
    """Diretório RO dos shims, compartilhado por todos os agentes: ``<bus>/bin`` (ADR-17)."""
    return Path(bus_dir) / "bin"


def install_client(bus_dir: str | Path) -> Path:
    """Copia o cliente ``ask_client.py`` como ``<bus>/bin/maestro-ask`` (executável).

    Os shims ficam num ``<bus>/bin`` visível READ-ONLY (via o ``--ro-bind / /`` do
    sandbox) e na PATH; cada agente os chama por ``"$MAESTRO_BIN/maestro-ask" ...``.
    """
    import shutil

    b = bin_dir(bus_dir)
    b.mkdir(parents=True, exist_ok=True)
    dest = b / "maestro-ask"
    shutil.copyfile(Path(__file__).with_name("ask_client.py"), dest)
    dest.chmod(0o755)
    return dest


def install_maestri_client(bus_dir: str | Path) -> Path:
    """Copia ``maestri_client.py`` como ``<bus>/bin/maestri`` (executável) — CLI de Maestro mode."""
    import shutil

    b = bin_dir(bus_dir)
    b.mkdir(parents=True, exist_ok=True)
    dest = b / "maestri"
    shutil.copyfile(Path(__file__).with_name("maestri_client.py"), dest)
    dest.chmod(0o755)
    return dest


MAESTRO_SKILL_BEGIN = "<!-- maestro-mode:begin -->"
MAESTRO_SKILL_END = "<!-- maestro-mode:end -->"


def maestro_skill_text(node: str) -> str:
    """Ensina o agente-MANAGER a orquestrar via `maestri` (Fase 6 + Fase B). Bloco reescrito
    a cada start."""
    return (
        f"{MAESTRO_SKILL_BEGIN}\n"
        "## Maestro mode (você gerencia uma equipe)\n\n"
        f"Você é o MANAGER '{node}'. Pode recrutar agentes no canvas, conectá-los e dispensá-los. "
        'Chame SEMPRE pelo caminho absoluto `"$MAESTRO_BIN/maestri"` (a PATH pode ser resetada '
        "pelo .bashrc):\n\n"
        '    "$MAESTRO_BIN/maestri" recruit <agente> [papel]  # agente conectado ABAIXO\n'
        '    "$MAESTRO_BIN/maestri" list                      # seus recrutas\n'
        '    "$MAESTRO_BIN/maestri" reassign <nó> <papel>     # troca o papel\n'
        '    "$MAESTRO_BIN/maestri" wire <a> [b]              # liga um cabo (b=você)\n'
        '    "$MAESTRO_BIN/maestri" dismiss <nó>              # dispensa um recruta\n\n'
        "Cada recruta vira um terminal de agente real; fale com ele por cabo via "
        '`"$MAESTRO_BIN/maestro-ask" <nó> "..."`. Recrute só o necessário; dispense ao fim.\n\n'
        "### Montar uma EQUIPE inteira de uma vez (`team`)\n"
        "Se o pedido pede vários agentes organizados em grupos (ex.: \"monte um time pra X\"), "
        "NÃO recrute um por um — descreva a equipe como JSON e peça UMA confirmação:\n\n"
        "    \"$MAESTRO_BIN/maestri\" team '<json>'\n\n"
        "Formato do `<json>` (aspas simples por fora, JSON válido por dentro):\n\n"
        '    {"name": "nome-curto", "description": "opcional",\n'
        '     "groups": [{"name": "Nome do grupo", "leader": null,\n'
        '                 "members": [{"name": "papel", "agent": "claude|codex",\n'
        '                              "instruction": "objetivo + saída + fronteira"}]}]}\n\n'
        "Regras: 2–5 membros por grupo (3–4 é o ideal; acima de 8 é recusado), cada papel "
        "precisa de `instruction` com objetivo claro. NÃO precisa (e não deve) incluir um campo "
        "`manager` apontando outro nó — a autoridade é sempre VOCÊ (quem chamou), o host decide "
        "isso pelo canal, um campo no JSON é ignorado. O HUMANO vê um resumo (grupos/papéis) e "
        "decide Montar/Negar — só materializa depois disso; não assuma que já foi criado até "
        "a resposta confirmar."
        f"\n{MAESTRO_SKILL_END}"
    )


def install_maestro_skill(workspace: str | Path, node: str) -> None:
    """(Re)escreve o bloco do Maestro mode no CLAUDE.md/AGENTS.md do workspace (marcado)."""
    begin, end = MAESTRO_SKILL_BEGIN, MAESTRO_SKILL_END
    block = maestro_skill_text(node)
    ws = Path(workspace)
    for fname in ("CLAUDE.md", "AGENTS.md"):
        p = ws / fname
        # S2 (review docs/33): ws é RW pro agente — safe_* não segue symlink (arquivo OU pai),
        # senão o host escreveria fora do sandbox.
        existing = safe_read_text(p, within=ws)
        if begin in existing and end in existing:
            pre = existing.split(begin, 1)[0].rstrip("\n")
            post = existing.split(end, 1)[1].lstrip("\n")
            new = f"{pre}\n\n{block}\n" + (f"\n{post}" if post else "")
        else:
            sep = "" if not existing or existing.endswith("\n") else "\n"
            new = f"{existing}{sep}\n{block}\n"
        safe_write_text(p, new, within=ws)


ASK_SKILL_MARKER = "<!-- maestro-ask -->"


def ask_skill_text(node: str) -> str:
    """Instrução que ensina o agente a USAR o maestro-ask (ADR-11, Fase 4)."""
    return (
        f"{ASK_SKILL_MARKER}\n"
        "## Ferramenta: maestro-ask (falar com agentes conectados por cabo)\n\n"
        f"Você é o agente '{node}'. Quando um terminal estiver ligado a você por um "
        "CABO, você pode CONSULTAR esse outro agente rodando, no seu shell:\n\n"
        '    "$MAESTRO_BIN/maestro-ask" <nó> "<sua pergunta>"\n\n'
        'Ele bloqueia até o outro agente responder e imprime "Answer from <nó>: ...". '
        "Use para delegar ou checar algo (ex.: pedir revisão). Use só os nós que "
        'aparecem na dica "[maestro] cabo ligado a \'X\'". Ao receber perguntas de '
        "outro agente, mantenha o SEU papel e responda objetivamente."
    )


def install_ask_skill(workspace: str | Path, node: str) -> None:
    """Acrescenta (idempotente) a instrução do maestro-ask ao CLAUDE.md/AGENTS.md do ws."""
    text = ask_skill_text(node)
    ws = Path(workspace)
    for fname in ("CLAUDE.md", "AGENTS.md"):
        p = ws / fname
        # S2: append via read+write seguro (o open("a") cru seguiria symlink → escrita no host)
        existing = safe_read_text(p, within=ws)
        if ASK_SKILL_MARKER in existing:
            continue  # já instalado
        sep = "" if not existing or existing.endswith("\n") else "\n"
        safe_write_text(p, f"{existing}{sep}\n{text}\n", within=ws)


NOTES_SKILL_BEGIN = "<!-- maestro-notes:begin -->"
NOTES_SKILL_END = "<!-- maestro-notes:end -->"


def connected_notes_skill_text(node: str, notes: list[tuple[str, str]]) -> str:
    """Bloco que lista as NOTAS ligadas a `node` por cabo. `notes` = [(título, caminho_rel)]."""
    lines = [
        NOTES_SKILL_BEGIN,
        "## Notas conectadas (cabo)",
        f"Você é '{node}'. Estas notas do canvas estão LIGADAS a você por cabo.",
        "Prefira LER e EDITAR estes arquivos markdown; suas edições voltam para a nota no canvas:",
    ]
    if notes:
        lines += [f'- "{title or "(sem título)"}" → {rel}' for title, rel in notes]
    else:
        lines.append("- (nenhuma nota conectada no momento)")
    lines.append(NOTES_SKILL_END)
    return "\n".join(lines)


def install_connected_notes_skill(
    workspace: str | Path, node: str, notes: list[tuple[str, str]]
) -> None:
    """Escreve/SUBSTITUI o bloco de notas conectadas no CLAUDE.md/AGENTS.md do workspace.
    Diferente do maestro-ask (append-once): conexões mudam, então o bloco é regravado."""
    text = connected_notes_skill_text(node, notes)
    ws = Path(workspace)
    for fname in ("CLAUDE.md", "AGENTS.md"):
        p = ws / fname
        existing = safe_read_text(p, within=ws)  # S2: não segue symlink (arquivo/pai)
        if NOTES_SKILL_BEGIN in existing and NOTES_SKILL_END in existing:
            pre = existing[: existing.index(NOTES_SKILL_BEGIN)]
            post = existing[existing.index(NOTES_SKILL_END) + len(NOTES_SKILL_END):]
            new = pre + text + post
        else:
            sep = "" if not existing or existing.endswith("\n") else "\n"
            new = existing + f"{sep}\n{text}\n"
        if new != existing:  # guard: evita churn de mtime quando nada mudou
            safe_write_text(p, new, within=ws)


def _check_id(rid: object) -> str:
    if not isinstance(rid, str) or not _SAFE_ID.match(rid):
        raise AskBusError(f"id inválido: {rid!r}")
    return rid


def validate_req(req: AskRequest) -> None:
    """Valida um pedido (entrada NÃO-confiável). Levanta AskBusError se inválido.

    Usado tanto pelo transporte de arquivos (AskBus) quanto pelo de socket (host).
    Não valida ``frm`` como identidade — no socket a identidade vem do CANAL (ADR-17);
    aqui só checa forma (tamanho, cmd/args, depth).
    """
    _check_id(req.id)
    if not req.frm or not isinstance(req.frm, str) or len(req.frm) > 200:
        raise AskBusError("frm inválido")
    if req.cmd:  # comando Maestro mode (to/prompt vazios; valida cmd/args)
        if len(req.cmd) > 64 or not re.match(r"^[a-z][a-z0-9_-]*$", req.cmd):
            raise AskBusError("cmd inválido")
        if not isinstance(req.args, list) or len(req.args) > 16:
            raise AskBusError("args inválidos")
        if sum(len(str(a).encode("utf-8")) for a in req.args) > ASK_MAX_PROMPT_BYTES:
            raise AskBusError("args excedem o limite")
    else:  # ask normal: exige destino + prompt
        if not req.to or not isinstance(req.to, str) or len(req.to) > 200:
            raise AskBusError("to inválido")
        if len(req.prompt.encode("utf-8")) > ASK_MAX_PROMPT_BYTES:
            raise AskBusError(f"prompt excede {ASK_MAX_PROMPT_BYTES} bytes")
    if req.depth < 0 or req.depth > 100:
        raise AskBusError("depth inválido")


class AskBus:
    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir)

    def ensure(self) -> Path:
        self.base.mkdir(parents=True, exist_ok=True)
        return self.base

    def _req_path(self, rid: str) -> Path:
        return self.base / f"req-{_check_id(rid)}.json"

    def _resp_path(self, rid: str) -> Path:
        return self.base / f"resp-{_check_id(rid)}.json"

    # -- lado do cliente (dentro do sandbox) --
    def write_request(self, req: AskRequest) -> Path:
        self._validate_req(req)
        self.ensure()
        p = self._req_path(req.id)
        p.write_text(json.dumps(asdict(req), ensure_ascii=False), encoding="utf-8")
        return p

    def read_response(self, rid: str) -> AskResponse | None:
        p = self._resp_path(rid)
        if not p.exists():
            return None
        return self._parse_resp(p.read_text(encoding="utf-8"))

    # -- lado do host (broker) --
    def pending_requests(self) -> list[AskRequest]:
        """Pedidos ``req-*.json`` ainda sem ``resp-*.json``. Ignora malformados."""
        if not self.base.exists():
            return []
        out: list[AskRequest] = []
        for p in sorted(self.base.glob("req-*.json")):
            rid = p.name[len("req-") : -len(".json")]
            if (self.base / f"resp-{rid}.json").exists():
                continue  # já respondido
            try:
                out.append(self.read_request(p))
            except AskBusError:
                continue  # malformado não derruba o host
        return out

    def read_request(self, path: str | Path) -> AskRequest:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise AskBusError(f"pedido ilegível: {e}") from e
        if not isinstance(data, dict):
            raise AskBusError("pedido não é objeto JSON")
        try:
            raw_args = data.get("args", [])
            req = AskRequest(
                id=_check_id(str(data["id"])),
                frm=str(data["frm"]),
                to=str(data.get("to", "")),
                prompt=str(data.get("prompt", "")),
                depth=int(data.get("depth", 0)),
                cmd=str(data.get("cmd", "")),
                args=[str(a) for a in raw_args] if isinstance(raw_args, list) else [],
            )
        except (KeyError, ValueError, TypeError) as e:
            raise AskBusError(f"pedido inválido: {e}") from e
        self._validate_req(req)
        return req

    def write_response(self, resp: AskResponse) -> Path:
        self.ensure()
        p = self._resp_path(resp.id)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(resp), ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)  # escrita atômica: o cliente nunca lê resposta parcial
        return p

    def cleanup(self, max_age_seconds: float = 3600, *, now: float | None = None) -> int:
        """Remove req/resp órfãos/velhos. Retorna quantos apagou."""
        if not self.base.exists():
            return 0
        t = time.time() if now is None else now
        n = 0
        for p in list(self.base.glob("req-*.json")) + list(self.base.glob("resp-*.json")):
            try:
                if t - p.stat().st_mtime > max_age_seconds:
                    p.unlink()
                    n += 1
            except OSError:
                pass
        return n

    # -- validação (entrada não-confiável) --
    def _validate_req(self, req: AskRequest) -> None:
        validate_req(req)

    def _parse_resp(self, s: str) -> AskResponse:
        data = json.loads(s)
        return AskResponse(
            id=_check_id(str(data["id"])),
            ok=bool(data["ok"]),
            answer=str(data.get("answer", "")),
            error=(None if data.get("error") is None else str(data["error"])),
        )
