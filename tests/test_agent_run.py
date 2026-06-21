"""Testes do plano de execução isolado (E2-S2): permissões aplicadas + cwd."""

from maestro.engine.adapters.base import load_profiles
from maestro.engine.agent_run import plan_run


def test_plan_claude_isola_e_aplica_permissoes(tmp_path):
    p = load_profiles()["claude"]
    plan = plan_run(p, "oi", workspace=tmp_path)
    assert plan.cwd == str(tmp_path)
    assert "--permission-mode" in plan.argv and "acceptEdits" in plan.argv
    assert "--add-dir" in plan.argv and str(tmp_path) in plan.argv
    assert "--allowedTools" in plan.argv
    assert "--dangerously-skip-permissions" not in plan.argv  # ADR-6
    # prompt antes de --allowedTools (nargs) para não ser engolido
    assert plan.argv.index("oi") < plan.argv.index("--allowedTools")


def test_plan_codex_sandbox_sem_bypass(tmp_path):
    p = load_profiles()["codex"]
    plan = plan_run(p, "oi", workspace=tmp_path)
    assert plan.cwd == str(tmp_path)
    assert "--sandbox" in plan.argv and "workspace-write" in plan.argv
    assert "-C" in plan.argv and str(tmp_path) in plan.argv
    assert "--dangerously-bypass-approvals-and-sandbox" not in plan.argv


def test_plan_resume(tmp_path):
    p = load_profiles()["claude"]
    plan = plan_run(p, "oi", workspace=tmp_path, session_id="sid", resume=True)
    assert "--resume" in plan.argv and "sid" in plan.argv
