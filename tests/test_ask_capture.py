"""Testes da heurística de captura do terminal vivo (modo 'live' do cabo, variante b)."""

from maestro.native.ask_capture import clean_capture, tui_busy


def test_tui_busy_detecta_indicador_de_ocupado():
    assert tui_busy("digitando... (esc to interrupt)")
    assert tui_busy("ESC TO INTERRUPT")  # case-insensitive
    assert not tui_busy("Aniversário do Codex: 16 de maio de 2025")


def test_clean_capture_extrai_resposta_sem_eco_nem_chrome():
    before = "┌────────┐\n│ codex  │\n└────────┘\n> "
    prompt = "quanto é 7+8?"
    after = (
        "┌────────┐\n│ codex  │\n└────────┘\n"
        "> quanto é 7+8?\n"  # eco do prompt -> removido
        "15\n"  # a resposta de verdade
        "> \n"  # prompt vazio (chrome/seen)
        "(esc to interrupt)"  # indicador de ocupado -> removido
    )
    assert clean_capture(before, after, prompt) == "15"


def test_clean_capture_resposta_multilinha():
    before = ""
    prompt = "liste 2 frutas"
    after = "liste 2 frutas\nmaçã\nbanana\n"
    assert clean_capture(before, after, prompt) == "maçã\nbanana"


def test_clean_capture_vazio_quando_so_chrome():
    # sem resposta real -> string vazia (o canvas cai no fallback headless)
    assert clean_capture("", "──────\n> \n(esc to interrupt)", "oi") == ""


def test_clean_capture_resposta_substring_do_prompt():
    # resposta curta que é substring do prompt NÃO pode ser filtrada (bug pego no probe real)
    before = "> "
    prompt = "echo MAESTROCAP_OK_42"
    after = "> echo MAESTROCAP_OK_42\nMAESTROCAP_OK_42\n> "
    assert clean_capture(before, after, prompt) == "MAESTROCAP_OK_42"


def test_clean_capture_ignora_o_que_ja_estava_na_tela():
    before = "conversa antiga\noutra linha"
    after = "conversa antiga\noutra linha\nresposta nova"
    assert clean_capture(before, after, "pergunta") == "resposta nova"
