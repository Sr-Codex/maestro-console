"""Testes do Agent Adapter (E2-S1): carga de perfis TOML e montagem de comando."""

from maestro.engine.adapters.base import AgentProfile, load_profile, load_profiles


def test_carrega_perfis_bundled():
    profs = load_profiles()
    assert "claude" in profs
    assert "codex" in profs
    assert profs["claude"].cmd == ["claude", "-p"]


def test_build_claude_simples():
    p = load_profiles()["claude"]
    assert p.build_command("ola") == ["claude", "-p", "ola"]


def test_build_claude_sessao_e_resume():
    p = load_profiles()["claude"]
    assert p.build_command("oi", session_id="sid") == [
        "claude",
        "-p",
        "--session-id",
        "sid",
        "oi",
    ]
    assert p.build_command("oi", session_id="sid", resume=True) == [
        "claude",
        "-p",
        "--resume",
        "sid",
        "oi",
    ]


def test_build_claude_com_workspace_aplica_permissoes():
    p = load_profiles()["claude"]
    argv = p.build_command("oi", workspace="/ws")
    assert "--permission-mode" in argv and "acceptEdits" in argv
    assert "--add-dir" in argv and "/ws" in argv
    assert "--allowedTools" in argv
    assert "--dangerously-skip-permissions" not in argv  # ADR-6
    assert argv[-1] == "oi"  # prompt por último


def test_build_codex_simples_e_resume():
    p = load_profiles()["codex"]
    assert p.build_command("oi") == ["codex", "exec", "--skip-git-repo-check", "oi"]
    assert p.build_command("oi", session_id="S1", resume=True) == [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "resume",
        "S1",
        "oi",
    ]


def test_codex_sem_bypass():
    p = load_profiles()["codex"]
    argv = p.build_command("oi", workspace="/ws")
    assert "--dangerously-bypass-approvals-and-sandbox" not in argv
    assert "--sandbox" in argv and "workspace-write" in argv


def test_adicionar_agente_sem_mudar_core(tmp_path):
    """Um novo agente é só um .toml — load_profile o entende sem tocar no core."""
    toml = tmp_path / "gemini.toml"
    toml.write_text(
        'name = "gemini"\n'
        "[headless]\n"
        'cmd = ["gemini", "-p"]\n'
        "[headless.session]\n"
        'mode = "flag"\n'
        'set = ["--sid", "{id}"]\n'
        'resume = ["--resume", "{id}"]\n'
    )
    prof = load_profile(toml)
    assert isinstance(prof, AgentProfile)
    assert prof.name == "gemini"
    assert prof.build_command("hi", session_id="z") == ["gemini", "-p", "--sid", "z", "hi"]
