"""Prompt-wrapper de envelope + retry limitado (E3-S2 / FR15).

Instrui o agente a responder SOMENTE com o JSON do envelope e valida a resposta;
em formato inválido, re-pergunta um número limitado de vezes. Esgotado o retry,
retorna um envelope **FAILED** (falha explícita, nunca sucesso parcial).

A engine é a autoridade de roteamento (from/to/message_id) — o agente fornece só
a semântica (state/result/artifacts/note).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from .envelope import Envelope, EnvelopeError, EnvelopeState, encode

ORCHESTRATOR = "orchestrator"
_STATES = {s.value for s in EnvelopeState}

ENVELOPE_INSTRUCTIONS = (
    "Responda APENAS com um objeto JSON (nada antes ou depois), no formato exato:\n"
    '{"state": "DONE|BLOCKED|FAILED|NEEDS_INPUT", "result": "<linha curta ou null>", '
    '"artifacts": ["<caminho>"], "note": "<curto ou null>"}\n'
    "Regras: 'state' é obrigatório e deve ser um dos quatro valores; NÃO escreva "
    "texto fora do JSON; resultados grandes salve em arquivo e cite o caminho em "
    "'artifacts' (nunca conteúdo grande inline)."
)

# Função que envia um prompt ao agente e devolve o stdout bruto.
AskFn = Callable[[str], Awaitable[str]]


def wrap_task(task: str) -> str:
    return f"{task}\n\n---\n{ENVELOPE_INSTRUCTIONS}"


def _extract_json(text: str) -> str:
    i, j = text.find("{"), text.rfind("}")
    if i == -1 or j == -1 or j < i:
        raise EnvelopeError("nenhum objeto JSON na resposta")
    return text[i : j + 1]


def parse_payload(raw: str) -> dict:
    """Extrai e valida o payload semântico do agente (state/result/artifacts/note)."""
    try:
        data = json.loads(_extract_json(raw))
    except json.JSONDecodeError as e:
        raise EnvelopeError(f"JSON inválido: {e}") from e
    if not isinstance(data, dict):
        raise EnvelopeError("payload não é objeto")
    state = data.get("state")
    if state not in _STATES:
        raise EnvelopeError(f"state inválido: {state!r}")
    result, note = data.get("result"), data.get("note")
    artifacts = data.get("artifacts", [])
    if result is not None and not isinstance(result, str):
        raise EnvelopeError("result deve ser string ou null")
    if note is not None and not isinstance(note, str):
        raise EnvelopeError("note deve ser string ou null")
    if not isinstance(artifacts, list) or not all(isinstance(a, str) for a in artifacts):
        raise EnvelopeError("artifacts deve ser lista de strings")
    return {"state": state, "result": result, "artifacts": artifacts, "note": note}


async def request_envelope(
    ask: AskFn,
    task: str,
    *,
    agent_id: str,
    message_id: str,
    task_id: str | None = None,
    max_retries: int = 2,
) -> Envelope:
    """Pede ao agente um envelope; valida; re-tenta; senão FAILED."""
    prompt = wrap_task(task)
    last: EnvelopeError | None = None
    for _ in range(max_retries + 1):
        raw = await ask(prompt)
        try:
            p = parse_payload(raw)
            env = Envelope(
                sender=agent_id,
                recipient=ORCHESTRATOR,
                message_id=message_id,
                task_id=task_id,
                state=EnvelopeState(p["state"]),
                result=p["result"],
                artifacts=p["artifacts"],
                note=p["note"],
            )
            encode(env)  # valida limite de bytes / estrito
            return env
        except EnvelopeError as e:
            last = e
            prompt = (
                wrap_task(task) + f"\n\nATENÇÃO: a resposta anterior foi inválida ({e}). "
                "Responda SOMENTE o JSON do envelope."
            )
    return Envelope(
        sender=agent_id,
        recipient=ORCHESTRATOR,
        message_id=message_id,
        task_id=task_id,
        state=EnvelopeState.FAILED,
        note=f"formato de envelope inválido após {max_retries + 1} tentativas: {last}",
    )
