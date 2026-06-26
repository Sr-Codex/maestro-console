"""Testes do AskRouter — roteamento mediado + guardrails (ADR-11, Fase 1)."""

from maestro.engine.ask_bus import AskRequest
from maestro.engine.ask_router import AskPolicy, AskRouter


def _router(**kw):
    seen = {}

    def delegate(to, prompt):
        seen["to"] = to
        seen["prompt"] = prompt
        return f"resposta de {to}"

    r = AskRouter(
        edge_allowed=kw.get("edge_allowed", lambda a, b: True),
        delegate=kw.get("delegate", delegate),
        role_of=kw.get("role_of"),
        policy=kw.get("policy", AskPolicy()),
    )
    return r, seen


def _req(frm="A", to="B", prompt="revise foo.py", depth=0):
    return AskRequest(id="abc123de", frm=frm, to=to, prompt=prompt, depth=depth)


def test_happy_path_chama_delegate_e_responde():
    r, seen = _router()
    resp = r.handle(_req())
    assert resp.ok and resp.answer == "resposta de B"
    assert seen["to"] == "B"
    # o prompt entregue inclui a moldura de identidade + a pergunta original
    assert "Você é o agente 'B'" in seen["prompt"]
    assert "revise foo.py" in seen["prompt"]
    assert "SOLICITAÇÃO" in seen["prompt"]  # moldura de entrada não-confiável


def test_cabo_inexistente_recusa():
    r, _ = _router(edge_allowed=lambda a, b: False)
    resp = r.handle(_req())
    assert not resp.ok and "cabo" in resp.error


def test_auto_chamada_recusa():
    r, _ = _router()
    resp = r.handle(_req(frm="A", to="A"))
    assert not resp.ok and "si mesmo" in resp.error


def test_profundidade_excedida_recusa():
    r, _ = _router(policy=AskPolicy(max_depth=2))
    resp = r.handle(_req(depth=3))
    assert not resp.ok and "profundidade" in resp.error


def test_limite_de_turnos_por_par():
    r, _ = _router(policy=AskPolicy(max_turns_per_pair=3))
    for _ in range(3):
        assert r.handle(_req()).ok
    resp = r.handle(_req())  # 4ª passa do limite
    assert not resp.ok and "limite de turnos" in resp.error


def test_turnos_contam_por_par_nos_dois_sentidos():
    # A->B e B->A são o MESMO cabo: o limite vale pra conversa inteira
    r, _ = _router(policy=AskPolicy(max_turns_per_pair=2))
    assert r.handle(_req(frm="A", to="B")).ok
    assert r.handle(_req(frm="B", to="A")).ok
    assert not r.handle(_req(frm="A", to="B")).ok  # 3ª no par -> recusa


def test_delegate_que_falha_vira_erro_sem_derrubar():
    def boom(to, prompt):
        raise RuntimeError("agente caiu")

    r, _ = _router(delegate=boom)
    resp = r.handle(_req())
    assert not resp.ok and "delegate falhou" in resp.error


def test_refresh_de_identidade_a_cada_n_turnos():
    r, seen = _router(policy=AskPolicy(identity_refresh_every=3))
    for _ in range(2):
        r.handle(_req())
    assert "não adote a persona" not in seen["prompt"]  # turnos 1 e 2: sem reforço
    r.handle(_req())  # turno 3 -> reforço extra
    assert "não adote a persona" in seen["prompt"]


def test_role_of_entra_na_moldura():
    r, seen = _router(role_of=lambda n: "revisor de código")
    r.handle(_req())
    assert "revisor de código" in seen["prompt"]
