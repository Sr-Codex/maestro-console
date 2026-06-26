"""Testes da composição do menu de ações da toolbar (P3) — sem GTK."""

from maestro.native.toolbar import action_menu_items


def test_completo_inclui_todos_na_ordem():
    items = action_menu_items(
        has_controller=True,
        has_edges=True,
        has_notes=True,
        has_floors=True,
        has_routines=True,
        team_name="coder-reviewer",
    )
    keys = [k for _, k in items]
    assert keys == ["newterm", "filetree", "run_team", "handoff", "note", "floors", "routines"]
    assert items[0] == ("➕ novo terminal", "newterm")  # sempre disponível
    assert ("📁 árvore de arquivos", "filetree") in items


def test_sempre_presentes_sem_nada():
    # ➕ novo terminal e 📁 árvore não dependem de nada (funcionam sem controller)
    items = action_menu_items(
        has_controller=False,
        has_edges=False,
        has_notes=False,
        has_floors=False,
        has_routines=False,
    )
    assert items == [("➕ novo terminal", "newterm"), ("📁 árvore de arquivos", "filetree")]


def test_sem_controller_some_run_handoff_routines():
    items = action_menu_items(
        has_controller=False, has_edges=True, has_notes=True, has_floors=True, has_routines=True
    )
    keys = [k for _, k in items]
    assert keys == ["newterm", "filetree", "note", "floors"]  # run/handoff/routines exigem ctrl


def test_handoff_exige_controller_e_edges():
    items = action_menu_items(
        has_controller=True, has_edges=False, has_notes=False, has_floors=False, has_routines=False
    )
    assert [k for _, k in items] == ["newterm", "filetree", "run_team"]  # sem edges, sem handoff


def test_team_name_no_label():
    items = action_menu_items(
        has_controller=True,
        has_edges=False,
        has_notes=False,
        has_floors=False,
        has_routines=False,
        team_name="meu-time",
    )
    label = next(lbl for lbl, k in items if k == "run_team")
    assert label == "▶ rodar time (meu-time)"
