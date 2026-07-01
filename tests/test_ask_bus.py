"""Testes do AskBus — caixa-postal de arquivos do modo interativo (ADR-11, Fase 1)."""

import json

import pytest

from maestro.engine.ask_bus import (
    AskBus,
    AskBusError,
    AskRequest,
    AskResponse,
    new_id,
)


def test_request_roundtrip_e_pending(tmp_path):
    bus = AskBus(tmp_path / "bus")
    rid = new_id()
    bus.write_request(AskRequest(id=rid, frm="A", to="B", prompt="oi"))
    pend = bus.pending_requests()
    assert len(pend) == 1
    assert (pend[0].frm, pend[0].to, pend[0].prompt) == ("A", "B", "oi")


def test_pending_exclui_ja_respondido(tmp_path):
    bus = AskBus(tmp_path / "bus")
    rid = new_id()
    bus.write_request(AskRequest(id=rid, frm="A", to="B", prompt="oi"))
    bus.write_response(AskResponse(id=rid, ok=True, answer="pronto"))
    assert bus.pending_requests() == []  # tem resp -> não está pendente


def test_response_roundtrip_atomico(tmp_path):
    bus = AskBus(tmp_path / "bus")
    rid = new_id()
    bus.write_response(AskResponse(id=rid, ok=True, answer="42"))
    resp = bus.read_response(rid)
    assert resp is not None and resp.ok and resp.answer == "42"
    assert not list((tmp_path / "bus").glob("*.tmp"))  # sem temporário vazado


def test_read_response_inexistente_eh_none(tmp_path):
    assert AskBus(tmp_path / "bus").read_response(new_id()) is None


def test_json_malformado_eh_ignorado_em_pending(tmp_path):
    bus = AskBus(tmp_path / "bus")
    bus.ensure()
    (bus.base / f"req-{new_id()}.json").write_text("{nao eh json", encoding="utf-8")
    assert bus.pending_requests() == []  # não derruba o host


def test_prompt_grande_demais_rejeitado(tmp_path):
    bus = AskBus(tmp_path / "bus")
    with pytest.raises(AskBusError):
        bus.write_request(AskRequest(id=new_id(), frm="A", to="B", prompt="x" * 9000))


def test_id_inseguro_rejeitado(tmp_path):
    bus = AskBus(tmp_path / "bus")
    for bad in ("../etc/passwd", "req x", "AABB", ""):
        with pytest.raises(AskBusError):
            bus.write_request(AskRequest(id=bad, frm="A", to="B", prompt="oi"))


def test_frm_to_invalidos_rejeitados(tmp_path):
    bus = AskBus(tmp_path / "bus")
    with pytest.raises(AskBusError):
        bus.write_request(AskRequest(id=new_id(), frm="", to="B", prompt="oi"))


def test_cleanup_remove_velhos(tmp_path):
    bus = AskBus(tmp_path / "bus")
    rid = new_id()
    bus.write_request(AskRequest(id=rid, frm="A", to="B", prompt="oi"))
    # com now bem no futuro, o arquivo é "velho" -> removido
    futuro = (bus.base / f"req-{rid}.json").stat().st_mtime + 10_000
    assert bus.cleanup(max_age_seconds=3600, now=futuro) == 1
    assert bus.pending_requests() == []


def test_request_data_no_disco_eh_json_valido(tmp_path):
    bus = AskBus(tmp_path / "bus")
    rid = new_id()
    p = bus.write_request(AskRequest(id=rid, frm="A", to="B", prompt="oi", depth=2))
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data == {"id": rid, "frm": "A", "to": "B", "prompt": "oi", "depth": 2,
                    "cmd": "", "args": []}  # +campos de Maestro mode (Fase 6)
