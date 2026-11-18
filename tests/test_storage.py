import json

from pdf_reader.core.pacing import delay_ms
from pdf_reader.storage import Progress, Repository, Settings, migrate_legacy_folder


def test_saves_and_reloads(tmp_path):
    file = tmp_path / "data.json"
    repo = Repository(file)
    repo.save_settings(Settings(font_size=22))
    repo.save_progress("abc", Progress(page=3, index=7, name="book"))

    fresh = Repository(file)
    assert fresh.settings().font_size == 22
    assert fresh.progress("abc") == Progress(3, 7, "book")


def test_corrupted_file_does_not_crash(tmp_path):
    file = tmp_path / "data.json"
    file.write_text("{this is not json", encoding="utf-8")
    repo = Repository(file)
    assert repo.settings() == Settings()
    assert (tmp_path / "data.corrupt").exists()


def test_wrongly_typed_values_become_default():
    settings = Settings.from_dict({"font_size": "big", "focus_mode": False, "x": 1})
    assert settings.font_size == Settings().font_size
    assert settings.focus_mode is False


def test_pacing_pauses_at_punctuation():
    base = delay_ms("casa", 240)
    assert base == 250
    assert delay_ms("fim.", 240) == 500
    assert delay_ms("vírgula,", 240) == 375
    assert delay_ms("disse.”", 240) == 500


def test_recent_sorted_and_removal(tmp_path):
    repo = Repository(tmp_path / "data.json")
    repo.save_progress("old", Progress(path="a.pdf", last_read=1.0))
    repo.save_progress("new", Progress(path="b.pdf", last_read=2.0))
    repo.save_progress("no_path", Progress(last_read=3.0))
    assert [i for i, _ in repo.recent()] == ["new", "old"]
    repo.remove("new")
    assert [i for i, _ in Repository(tmp_path / "data.json").recent()] == ["old"]


def test_percent():
    assert Progress(page=4, page_count=10).percent == 50
    assert Progress().percent == 0


def test_reads_version_1_file(tmp_path):
    legacy = {
        "versao": 1,
        "configuracao": {"tamanho_fonte": 22, "tema": "sepia", "largura": "estreita",
                         "modo_foco": False, "voz": "kokoro-pf_dora"},
        "progresso": {"abc": {"pagina": 3, "indice": 7, "nome": "livro",
                              "caminho": "a.pdf", "total_paginas": 10, "ultima_leitura": 5.0}},
    }

    file = tmp_path / "data.json"
    file.write_text(json.dumps(legacy), encoding="utf-8")
    repo = Repository(file)
    settings = repo.settings()
    assert (settings.font_size, settings.theme, settings.width) == (22, "sepia", "narrow")
    assert settings.focus_mode is False
    assert settings.voice == "kokoro-pf_dora"
    assert repo.progress("abc") == Progress(3, 7, "livro", "a.pdf", 10, 5.0)


def test_migrates_legacy_folder(tmp_path):
    legacy = tmp_path / "LeitorPDF"
    (legacy / "vozes").mkdir(parents=True)
    (legacy / "vozes" / "voice.onnx").write_bytes(b"x")
    (legacy / "dados.json").write_text("{}", encoding="utf-8")

    migrate_legacy_folder(tmp_path / "PDFReader")
    assert not legacy.exists()
    assert (tmp_path / "PDFReader" / "data.json").exists()
    assert (tmp_path / "PDFReader" / "voices" / "voice.onnx").exists()


def test_does_not_touch_existing_folder(tmp_path):
    (tmp_path / "LeitorPDF").mkdir()
    (tmp_path / "PDFReader").mkdir()
    migrate_legacy_folder(tmp_path / "PDFReader")
    assert (tmp_path / "LeitorPDF").exists()
