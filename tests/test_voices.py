from pdf_reader.core.voices import DEFAULT_VOICE, VOICES, voice


def test_urls_follow_the_piper_repository():
    urls = voice("pt_BR-faber-medium").files()
    assert urls[1] == (
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
        "pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx?download=true",
        "pt_BR-faber-medium.onnx",
    )


def test_openvoiceos_urls():
    urls = voice("ovos-dii_pt-BR").files()
    assert urls[1] == (
        "https://huggingface.co/OpenVoiceOS/pipertts_pt-BR_dii/resolve/main/"
        "dii_pt-BR.onnx?download=true",
        "ovos-dii_pt-BR.onnx",
    )


def test_ids_are_unique():
    assert len({v.id for v in VOICES}) == len(VOICES)


def test_unknown_voice_falls_back_to_default():
    assert voice("does-not-exist").id == DEFAULT_VOICE


def test_is_downloaded(tmp_path):
    v = VOICES[0]
    assert not v.is_downloaded(tmp_path)
    for _, name in v.files():
        (tmp_path / name).write_bytes(b"x")
    assert v.is_downloaded(tmp_path)


def test_kokoro_voices_share_the_download(tmp_path):
    dora, alex = voice("kokoro-pf_dora"), voice("kokoro-pm_alex")
    assert dora.files() == alex.files()
    for _, name in dora.files():
        (tmp_path / name).write_bytes(b"x")
    assert alex.is_downloaded(tmp_path)
