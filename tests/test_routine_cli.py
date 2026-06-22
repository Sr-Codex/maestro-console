"""Testes da CLI maestro routine (V10-S3)."""

from maestro.cli_routine import routine_cli
from maestro.engine.envelope import Envelope, EnvelopeState
from maestro.engine.routines import Routines
from maestro.engine.state.store import Store


class _Ctrl:
    def __init__(self, state=EnvelopeState.DONE):
        self._state = state
        self.calls = []

    async def delegate(self, agent_id, task):
        self.calls.append((agent_id, task))
        return Envelope(
            sender=agent_id, recipient="orchestrator", message_id="m", state=self._state
        )


def _list_names(home):
    store = Store(home / "maestro.db")
    names = [r.name for r in Routines(store).list()]
    store.close()
    return names


def test_add_multistep_e_list(tmp_path, capsys):
    home = str(tmp_path)
    rc = routine_cli(
        ["add", "ci", "claude", "rode testes && reporte", "--interval", "30"], home=home
    )
    assert rc == 0 and "2 passo" in capsys.readouterr().out
    routine_cli(["list"], home=home)
    out = capsys.readouterr().out
    assert "ci" in out and "claude" in out and "[on]" in out
    # passos guardados corretamente
    store = Store(tmp_path / "maestro.db")
    r = Routines(store).list()[0]
    assert r.steps == ["rode testes", "reporte"] and r.interval_s == 30
    store.close()


def test_enable_disable_por_nome(tmp_path, capsys):
    home = str(tmp_path)
    routine_cli(["add", "r1", "claude", "p", "--interval", "60"], home=home)
    capsys.readouterr()
    routine_cli(["disable", "r1"], home=home)
    assert "pausada" in capsys.readouterr().out
    store = Store(tmp_path / "maestro.db")
    assert Routines(store).list()[0].enabled is False
    store.close()
    routine_cli(["enable", "r1"], home=home)
    assert "habilitada" in capsys.readouterr().out


def test_rm(tmp_path, capsys):
    home = str(tmp_path)
    routine_cli(["add", "r1", "claude", "p"], home=home)
    capsys.readouterr()
    assert routine_cli(["rm", "r1"], home=home) == 0
    assert _list_names(tmp_path) == []


def test_ref_inexistente(tmp_path, capsys):
    assert routine_cli(["run", "nao-existe"], home=str(tmp_path), controller=_Ctrl()) == 1
    assert "não encontrada" in capsys.readouterr().out


def test_run_com_controller(tmp_path, capsys):
    home = str(tmp_path)
    routine_cli(["add", "r1", "claude", "p1 && p2", "--interval", "10"], home=home)
    capsys.readouterr()
    ctrl = _Ctrl(EnvelopeState.DONE)
    rc = routine_cli(["run", "r1"], home=home, controller=ctrl)
    assert rc == 0 and "OK" in capsys.readouterr().out
    assert [c[1] for c in ctrl.calls] == ["p1", "p2"]
    store = Store(tmp_path / "maestro.db")
    assert Routines(store).list()[0].run_count == 1
    store.close()


def test_run_para_no_nao_done(tmp_path, capsys):
    home = str(tmp_path)
    routine_cli(["add", "r1", "claude", "p1 && p2"], home=home)
    capsys.readouterr()
    rc = routine_cli(["run", "r1"], home=home, controller=_Ctrl(EnvelopeState.BLOCKED))
    assert rc == 1 and "parou no passo 0" in capsys.readouterr().out


def test_serve_max_ticks(tmp_path, capsys):
    home = str(tmp_path)
    routine_cli(["add", "r1", "claude", "p", "--interval", "1"], home=home)
    capsys.readouterr()
    ctrl = _Ctrl(EnvelopeState.DONE)
    rc = routine_cli(["serve", "--interval", "0", "--ticks", "2"], home=home, controller=ctrl)
    assert rc == 0 and "2 tick" in capsys.readouterr().out
    store = Store(tmp_path / "maestro.db")
    assert Routines(store).list()[0].run_count >= 1
    store.close()
