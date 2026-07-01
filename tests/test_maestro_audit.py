"""Testes da trilha de auditoria append-only (ADR-17, Etapa 2)."""

import pytest

from maestro.engine.maestro_audit import append_event, audit_path, read_events


def test_append_e_read_roundtrip(tmp_path):
    bus = tmp_path / "bus"
    append_event(bus, "recruit", now=1.0, manager="mgr", node="codex-1", role="coder")
    append_event(bus, "dismiss", now=2.0, manager="mgr", node="codex-1")
    evs = read_events(bus)
    assert [e["event"] for e in evs] == ["recruit", "dismiss"]
    assert evs[0]["manager"] == "mgr" and evs[0]["node"] == "codex-1"
    assert evs[0]["ts"] == pytest.approx(1.0)  # float: sem == exato (Sonar S1244)
    assert evs[1]["event"] == "dismiss"


def test_append_only(tmp_path):
    bus = tmp_path / "bus"
    append_event(bus, "a", now=1.0)
    append_event(bus, "b", now=2.0)
    # a 2ª escrita NÃO sobrescreve a 1ª (append)
    assert len(read_events(bus)) == 2


def test_read_inexistente_eh_vazio(tmp_path):
    assert read_events(tmp_path / "nada") == []


def test_linha_corrompida_eh_ignorada(tmp_path):
    bus = tmp_path / "bus"
    append_event(bus, "ok", now=1.0)
    with open(audit_path(bus), "a", encoding="utf-8") as f:
        f.write("{lixo não-json\n")
    append_event(bus, "ok2", now=2.0)
    evs = read_events(bus)
    assert [e["event"] for e in evs] == ["ok", "ok2"]  # pula a linha corrompida


def test_append_nao_levanta_em_caminho_ruim():
    # bus_dir impossível de criar não pode derrubar o fluxo
    append_event("/proc/nao/da/pra/criar", "x")  # não levanta
