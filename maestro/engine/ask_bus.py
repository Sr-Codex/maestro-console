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
from dataclasses import asdict, dataclass
from pathlib import Path

ASK_MAX_PROMPT_BYTES = 8192  # teto do prompt cruzado (entrada não-confiável)
_SAFE_ID = re.compile(r"^[0-9a-f]{8,}$")  # uuid4().hex


class AskBusError(Exception):
    """Pedido/resposta malformado ou inválido (entrada não-confiável)."""


@dataclass
class AskRequest:
    id: str
    frm: str  # nó remetente (MAESTRO_NODE)
    to: str  # nó destino
    prompt: str
    depth: int = 0  # profundidade da cadeia A->B->A (anti-loop; setada pelo host)


@dataclass
class AskResponse:
    id: str
    ok: bool
    answer: str = ""
    error: str | None = None


def new_id() -> str:
    return uuid.uuid4().hex


def _check_id(rid: object) -> str:
    if not isinstance(rid, str) or not _SAFE_ID.match(rid):
        raise AskBusError(f"id inválido: {rid!r}")
    return rid


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
            req = AskRequest(
                id=_check_id(str(data["id"])),
                frm=str(data["frm"]),
                to=str(data["to"]),
                prompt=str(data["prompt"]),
                depth=int(data.get("depth", 0)),
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
        _check_id(req.id)
        for f in (req.frm, req.to):
            if not f or not isinstance(f, str) or len(f) > 200:
                raise AskBusError("frm/to inválidos")
        if len(req.prompt.encode("utf-8")) > ASK_MAX_PROMPT_BYTES:
            raise AskBusError(f"prompt excede {ASK_MAX_PROMPT_BYTES} bytes")
        if req.depth < 0 or req.depth > 100:
            raise AskBusError("depth inválido")

    def _parse_resp(self, s: str) -> AskResponse:
        data = json.loads(s)
        return AskResponse(
            id=_check_id(str(data["id"])),
            ok=bool(data["ok"]),
            answer=str(data.get("answer", "")),
            error=(None if data.get("error") is None else str(data["error"])),
        )
