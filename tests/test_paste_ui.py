"""Probes gi do paste/drop (docs/32/ADR-29) — roteamento real, fronteira mockada.

Roda no python do SISTEMA (o .venv é gi-free). Padrão canvas_harness: métodos REAIS de
`_smart_paste`/`_on_node_drop`/`_ingest_drop_path` sob teste; mocka só clipboard/texture/
widget (fronteiras). Cobre: imagem→salva+injeta sem \\r; texto/falha→paste normal (E5);
cap anti-bomba (E4); descarregado no-op ANTES de salvar (E2); drop com cópia (E1/E3).
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from maestro.engine.state.store import Store

pytest.importorskip("gi")  # canvas usa PyGObject; o .venv é gi-free → python do sistema
from canvas_harness import win  # noqa: E402

from maestro.native import paste  # noqa: E402


class _Term(SimpleNamespace):
    def __init__(self):
        super().__init__(_destroyed=False, fed=[], pasted=[], screen=[])

    def paste_clipboard(self):
        self.pasted.append(True)

    def feed(self, data):
        self.screen.append(data)


class _Formats:
    def __init__(self, has_img):
        self._img = has_img

    def contain_gtype(self, _g):
        return self._img

    def get_mime_types(self):
        return ["image/png"] if self._img else ["text/plain"]


class _Texture(SimpleNamespace):
    def __init__(self, w=1280, h=720, fail_save=False):
        super().__init__(_w=w, _h=h, _fail=fail_save)

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h

    def save_to_png(self, path):
        if self._fail:
            raise OSError("disco cheio")
        Path(path).write_bytes(b"\x89PNG fake")


class _Clipboard:
    def __init__(self, has_img, texture=None):
        self._fmts = _Formats(has_img)
        self._tex = texture

    def get_formats(self):
        return self._fmts

    def read_texture_async(self, _cancellable, cb):
        cb(self, object())  # síncrono no teste (fronteira)

    def read_texture_finish(self, _res):
        if self._tex is None:
            raise RuntimeError("clipboard mudou")
        return self._tex


def _w(tmp_path, has_img, texture=None, nid="claude-2"):
    s = Store(tmp_path / "t.db")
    term = _Term()
    w = win(s, tmp_path, nid, term_=None)
    w.frames = {nid: SimpleNamespace(_term=term)}
    w.win = SimpleNamespace(get_clipboard=lambda: _Clipboard(has_img, texture))
    w._feed_child = lambda t, text: t.fed.append(text)
    w._audit = lambda *a, **k: None
    return w, term


def test_imagem_salva_e_injeta_sem_enter(tmp_path):
    w, term = _w(tmp_path, has_img=True, texture=_Texture())
    w._smart_paste("claude-2", term)
    assert term.pasted == []  # não caiu no paste de texto
    assert len(term.fed) == 1
    txt = term.fed[0]
    assert "\r" not in txt and "\n" not in txt  # D4: humano dá o Enter
    assert "/pastes/paste-" in txt and txt.endswith(" ")
    saved = list((Path(w._node_ws("claude-2")) / "pastes").glob("*.png"))
    assert len(saved) == 1  # PNG estável no workspace


def test_texto_segue_paste_normal(tmp_path):
    w, term = _w(tmp_path, has_img=False)
    w._smart_paste("claude-2", term)
    assert term.pasted == [True] and term.fed == []


def test_falha_no_read_degrada_pra_texto(tmp_path):
    # E5: clipboard mudou entre o check e a leitura → nunca perder o gesto
    w, term = _w(tmp_path, has_img=True, texture=None)
    w._smart_paste("claude-2", term)
    assert term.pasted == [True] and term.fed == []


def test_imagem_bomba_recusada(tmp_path):
    # E4: textura gigante não vai pro disco nem pro prompt; hint na TELA (feed, não stdin)
    w, term = _w(tmp_path, has_img=True, texture=_Texture(w=20000, h=20000))
    w._smart_paste("claude-2", term)
    assert term.fed == [] and term.pasted == []
    assert any(b"recusada" in scr for scr in term.screen)


def test_descarregado_no_op_antes_de_salvar(tmp_path):
    # E2: nó dormindo não ganha PNG órfão
    w, term = _w(tmp_path, has_img=True, texture=_Texture())
    w.model.set_node_cfg("claude-2", "unloaded", "1")
    w._smart_paste("claude-2", term)
    assert term.fed == [] and term.pasted == []
    assert not (Path(w._node_ws("claude-2")) / "pastes").exists()


def test_falha_ao_salvar_avisa_na_tela(tmp_path):
    # E8: erro de disco → hint via feed, stdin intocado
    w, term = _w(tmp_path, has_img=True, texture=_Texture(fail_save=True))
    w._smart_paste("claude-2", term)
    assert term.fed == []
    assert any(b"falha ao salvar" in scr for scr in term.screen)


# --- drop --------------------------------------------------------------------


class _File(SimpleNamespace):
    def get_path(self):
        return self.p


class _FileList(SimpleNamespace):
    def get_files(self):
        return [_File(p=p) for p in self.paths]


def test_drop_injeta_caminho_quoted(tmp_path, monkeypatch):
    # tmp_path do pytest vive em /tmp (prefixo invisível REAL) — neutraliza pra testar
    # a rota "injeta o ORIGINAL quoted" isoladamente
    import maestro.native.canvas as canvas_mod
    monkeypatch.setattr(canvas_mod, "invisible_prefixes", lambda: [])
    w, term = _w(tmp_path, has_img=False)
    f = tmp_path / "o meu arquivo.png"
    f.write_bytes(b"x")
    ok = w._on_node_drop(None, _FileList(paths=[str(f)]), 0, 0, "claude-2")
    assert ok is True and len(term.fed) == 1
    assert "'" in term.fed[0] and "\r" not in term.fed[0]  # quoted, sem Enter


def test_drop_de_tmp_copia_pro_workspace(tmp_path, monkeypatch):
    # E3: prefixo invisível no sandbox → injeta a CÓPIA em <ws>/pastes/
    import maestro.native.canvas as canvas_mod
    monkeypatch.setattr(canvas_mod, "invisible_prefixes", lambda: [str(tmp_path / "vol")])
    w, term = _w(tmp_path, has_img=False)
    vol = tmp_path / "vol"
    vol.mkdir()
    f = vol / "shot.png"
    f.write_bytes(b"img")
    assert w._on_node_drop(None, _FileList(paths=[str(f)]), 0, 0, "claude-2") is True
    assert "/pastes/drop-" in term.fed[0]
    copied = list((Path(w._node_ws("claude-2")) / "pastes").glob("drop-*"))
    assert len(copied) == 1 and copied[0].read_bytes() == b"img"


def test_drop_nome_hostil_vira_copia(tmp_path):
    # E1: control char no nome NUNCA é injetado — cópia com nome seguro
    w, term = _w(tmp_path, has_img=False)
    f = tmp_path / "a\rb.png"
    f.write_bytes(b"img")
    assert w._on_node_drop(None, _FileList(paths=[str(f)]), 0, 0, "claude-2") is True
    assert "\r" not in term.fed[0] and "/pastes/drop-" in term.fed[0]


def test_drop_em_no_descarregado_recusa(tmp_path):
    w, term = _w(tmp_path, has_img=False)
    w.model.set_node_cfg("claude-2", "unloaded", "1")
    f = tmp_path / "x.png"
    f.write_bytes(b"x")
    assert w._on_node_drop(None, _FileList(paths=[str(f)]), 0, 0, "claude-2") is False
    assert term.fed == []
