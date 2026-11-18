"""Voices for reading aloud: which ones exist, where they live and how to download them.

There are two engines, both running on your own computer, offline:

- **Piper**: fast, one voice per file (~63 MB each). Voices from the
  official catalog (rhasspy) and from the OpenVoiceOS project, which use
  the same format.
- **Kokoro**: newer and slower; a single model (~116 MB including the
  voices file) serves several voices.

Voices don't ship with the app: they are downloaded once to the data folder.
"""

from __future__ import annotations

import os
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

PIPER, KOKORO = "piper", "kokoro"
FEMALE, MALE = "female", "male"

_HF = "https://huggingface.co/{repository}/resolve/main/{path}{extension}?download=true"
_KOKORO = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
# Compact (int8) version of the model: sounds practically the same, 220 MB smaller.
_KOKORO_FILES = ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")


PT_BR, EN_US, EN_GB = "pt-BR", "en-US", "en-GB"
# Voice categories, in the order they are shown.
LANGUAGES = {PT_BR: "Português (Brasil)", EN_US: "English (US)", EN_GB: "English (UK)"}


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    gender: str  # FEMALE or MALE (judged by the voice's pitch)
    description: str
    size_mb: int
    engine: str = PIPER
    repository: str = ""  # Piper: repository on Hugging Face
    path: str = ""  # Piper: file in the repository, without the extension
    language: str = PT_BR  # the language of the text the voice reads well

    @property
    def label(self) -> str:
        return f"{self.name} ({self.gender})"

    def files(self) -> list[tuple[str, str]]:
        """(url, local file name) of everything the voice needs."""
        if self.engine == KOKORO:
            return [(_KOKORO + name, name) for name in _KOKORO_FILES]
        return [
            (_HF.format(repository=self.repository, path=self.path, extension=extension),
             f"{self.id}{extension}")
            for extension in (".onnx.json", ".onnx")
        ]

    def is_downloaded(self, folder: Path) -> bool:
        return all((Path(folder) / name).exists() for _, name in self.files())


def _official(name: str, quality: str, gender: str, license: str, extra: str = "",
              language: str = PT_BR, file: str = "") -> Voice:
    """A voice from the official Piper catalog (``file`` when it isn't just the name)."""
    code = language.replace("-", "_")
    file = file or name.lower()
    voice_id = f"{code}-{file}-{quality}"
    return Voice(voice_id, name, gender, f"Piper, official catalog. License {license}.{extra}", 63,
                 PIPER, "rhasspy/piper-voices",
                 f"{code[:2]}/{code}/{file}/{quality}/{voice_id}", language)


def _openvoiceos(name: str, gender: str) -> Voice:
    file = f"{name.lower()}_pt-BR"
    return Voice(f"ovos-{file}", name, gender,
                 "Piper, OpenVoiceOS project. License CC BY-NC-ND 4.0: free for personal use, "
                 "no commercial use.", 64, PIPER, f"OpenVoiceOS/pipertts_pt-BR_{name.lower()}",
                 file)


# Kokoro names its voices by language and gender: "pf_dora" = Portuguese, female.
_KOKORO_PREFIX = {PT_BR: "p", EN_US: "a", EN_GB: "b"}
_KOKORO_LANG = {PT_BR: "pt-br", EN_US: "en-us", EN_GB: "en-gb"}


def _kokoro(name: str, gender: str, language: str = PT_BR) -> Voice:
    prefix = _KOKORO_PREFIX[language] + ("f" if gender == FEMALE else "m")
    return Voice(f"kokoro-{prefix}_{name.lower()}", name, gender,
                 "Kokoro. License Apache 2.0. Takes a little longer to start speaking. "
                 "The same download serves all Kokoro voices.", 116, KOKORO,
                 language=language)


VOICES = [
    # Português (Brasil)
    _openvoiceos("Dii", FEMALE),
    _kokoro("Dora", FEMALE),
    _official("Faber", "medium", MALE, "CC0"),
    _official("Cadu", "medium", MALE, "CC0"),
    _official("Jeff", "medium", MALE, "CC0"),
    _openvoiceos("Miro", MALE),
    _kokoro("Alex", MALE),
    _kokoro("Santa", MALE),
    _official("Edresson", "low", MALE, "CC BY 4.0", " Lower quality."),
    # English (US)
    _kokoro("Heart", FEMALE, EN_US),
    _kokoro("Bella", FEMALE, EN_US),
    _official("Kristin", "medium", FEMALE, "public domain", language=EN_US),
    _official("Linda", "medium", FEMALE, "public domain (LJ Speech)", language=EN_US,
              file="ljspeech"),
    _kokoro("Michael", MALE, EN_US),
    _kokoro("Fenrir", MALE, EN_US),
    _official("Joe", "medium", MALE, "CC0", language=EN_US),
    _official("John", "medium", MALE, "public domain", language=EN_US),
    _official("Norman", "medium", MALE, "public domain", language=EN_US),
    # English (UK)
    _kokoro("Emma", FEMALE, EN_GB),
    _official("Cori", "medium", FEMALE, "CC BY 4.0", language=EN_GB),
    _official("Alba", "medium", FEMALE, "CC BY 4.0", " Scottish accent.", language=EN_GB),
    _kokoro("George", MALE, EN_GB),
    _official("Northern", "medium", MALE, "CC BY-SA 4.0", " Northern English accent.",
              language=EN_GB, file="northern_english_male"),
]
DEFAULT_VOICE = "pt_BR-faber-medium"
_BY_ID = {v.id: v for v in VOICES}


def voice(voice_id: str) -> Voice:
    return _BY_ID.get(voice_id) or _BY_ID[DEFAULT_VOICE]


class DownloadCancelled(Exception):
    pass


def download(v: Voice, folder: Path, progress: Callable[[int, int], bool] | None = None) -> None:
    """Download the voice's files still missing from ``folder``.

    ``progress(downloaded, total)`` is called for every chunk, summing all
    files; if it returns False, the download is cancelled. Half-downloaded
    files never get their final name, so an interrupted voice doesn't look downloaded.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    missing = [(url, name) for url, name in v.files() if not (folder / name).exists()]
    estimated_total = v.size_mb * 1_000_000
    received = 0
    for url, name in missing:
        target = folder / name
        temporary = target.with_name(name + ".part")
        try:
            with urllib.request.urlopen(url, timeout=30) as response, temporary.open("wb") as out:
                while chunk := response.read(256 * 1024):
                    out.write(chunk)
                    received += len(chunk)
                    estimated_total = max(estimated_total, received)
                    if progress and progress(received, estimated_total) is False:
                        raise DownloadCancelled
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)


# ----------------------------------------------------------------------
# Synthesis
# ----------------------------------------------------------------------
class Synthesizer:
    """A loaded voice, turning text into 16-bit mono PCM audio."""

    rate: int

    def synthesize(self, text: str, speed: float = 1.0) -> bytes:
        raise NotImplementedError


class _PiperSynthesizer(Synthesizer):
    def __init__(self, model: Path) -> None:
        from piper import PiperVoice  # heavy import: only when it's time to speak

        self._voice = PiperVoice.load(str(model))
        self.rate = self._voice.config.sample_rate

    def synthesize(self, text: str, speed: float = 1.0) -> bytes:
        from piper import SynthesisConfig

        config = SynthesisConfig(length_scale=1 / max(speed, 0.1))
        return b"".join(part.audio_int16_bytes for part in self._voice.synthesize(text, config))


_KOKORO_MODELS: dict[Path, object] = {}  # one model shared by all voices


class _KokoroSynthesizer(Synthesizer):
    def __init__(self, folder: Path, voice_name: str, lang: str) -> None:
        from kokoro_onnx import Kokoro  # heavy import: only when it's time to speak

        folder = Path(folder)
        if folder not in _KOKORO_MODELS:
            _KOKORO_MODELS[folder] = Kokoro(str(folder / _KOKORO_FILES[0]),
                                            str(folder / _KOKORO_FILES[1]))
        self._kokoro = _KOKORO_MODELS[folder]
        self._voice_name = voice_name
        self._lang = lang
        self.rate = 24_000

    def synthesize(self, text: str, speed: float = 1.0) -> bytes:
        import numpy as np

        audio, self.rate = self._kokoro.create(
            text, voice=self._voice_name, speed=min(max(speed, 0.5), 2.0), lang=self._lang)
        return (np.clip(audio, -1, 1) * 32_767).astype(np.int16).tobytes()


def create_synthesizer(v: Voice, folder: Path) -> Synthesizer:
    if v.engine == KOKORO:
        return _KokoroSynthesizer(folder, v.id.removeprefix("kokoro-"), _KOKORO_LANG[v.language])
    return _PiperSynthesizer(Path(folder) / f"{v.id}.onnx")
