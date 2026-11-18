"""Preferences and reading progress, kept in a JSON file."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, TypeVar

_VERSION = 2
_T = TypeVar("_T")


def _from_dict(cls: type[_T], data: Any) -> _T:
    """Build the dataclass from known fields of the right type only.

    Any missing, unknown or wrongly typed value falls back to the default,
    so an old or hand-edited JSON never breaks the app.
    """
    default = cls()
    if not isinstance(data, dict):
        return default
    return cls(
        **{
            field.name: data[field.name]
            for field in fields(cls)
            if type(data.get(field.name)) is type(getattr(default, field.name))
        }
    )


@dataclass
class Settings:
    # Reading
    words_per_minute: int = 240
    highlight_word: bool = True
    focus_mode: bool = True
    focus_visibility: int = 30  # 0–100: how much the text outside the line shows
    skip_margins: bool = True  # skip headers, footers and page numbers
    # Appearance
    theme: str = "dark"
    font: str = "Georgia"
    font_size: int = 18
    line_spacing: int = 150  # line height, in %
    width: str = "medium"  # width of the text column
    # Original PDF next to the text
    show_original: bool = False
    original_split: int = 50  # % of the width taken by the text
    original_zoom: int = 100  # %, 100 = page fits the panel width
    # Voice
    voice: str = "pt_BR-faber-medium"
    voice_speed: int = 100  # %
    # Window
    geometry: str = ""  # size and position (Qt saveGeometry, in base64)

    @classmethod
    def from_dict(cls, data: Any) -> Settings:
        return _from_dict(cls, data)


@dataclass
class Progress:
    page: int = 0
    index: int = 0
    name: str = ""
    path: str = ""
    page_count: int = 0
    last_read: float = 0.0  # timestamp

    @property
    def percent(self) -> int:
        if self.page_count <= 0:
            return 0
        return round(100 * (self.page + 1) / self.page_count)


class Repository:
    """Reads and writes the app's data file.

    A corrupted file doesn't crash the app: it is renamed to ``*.corrupt``
    and the app starts from scratch. Writes are atomic (temporary file +
    swap), so closing midway never corrupts anything.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._data = self._read()

    # --- settings ---
    def settings(self) -> Settings:
        return Settings.from_dict(self._data["settings"])

    def save_settings(self, settings: Settings) -> None:
        self._data["settings"] = asdict(settings)
        self._write()

    # --- progress ---
    def progress(self, document_id: str) -> Progress:
        return _from_dict(Progress, self._data["progress"].get(document_id))

    def save_progress(self, document_id: str, progress: Progress) -> None:
        self._data["progress"][document_id] = asdict(progress)
        self._write()

    def recent(self, limit: int = 30) -> list[tuple[str, Progress]]:
        """Documents read, most recent first."""
        items = [
            (document_id, _from_dict(Progress, data))
            for document_id, data in self._data["progress"].items()
        ]
        items = [(i, p) for i, p in items if p.path]
        items.sort(key=lambda item: item[1].last_read, reverse=True)
        return items[:limit]

    def remove(self, document_id: str) -> None:
        if self._data["progress"].pop(document_id, None) is not None:
            self._write()

    # --- file ---
    def _read(self) -> dict[str, Any]:
        empty: dict[str, Any] = {"version": _VERSION, "settings": {}, "progress": {}}
        if not self.path.exists():
            return empty
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("unexpected format")
        except (OSError, ValueError):
            try:
                self.path.replace(self.path.with_suffix(".corrupt"))
            except OSError:
                pass
            return empty
        data = _upgrade(data)
        for key in ("settings", "progress"):
            if not isinstance(data.get(key), dict):
                data[key] = {}
        return {**empty, **data, "version": _VERSION}

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temporary, self.path)


# ----------------------------------------------------------------------
# Data from version 1, when the app was called "LeitorPDF" (Portuguese names)
# ----------------------------------------------------------------------
LEGACY_FOLDER = "LeitorPDF"

_LEGACY_SETTINGS = {
    "palavras_por_minuto": "words_per_minute", "destacar_palavra": "highlight_word",
    "modo_foco": "focus_mode", "visibilidade_foco": "focus_visibility",
    "ignorar_margens": "skip_margins", "tema": "theme", "fonte": "font",
    "tamanho_fonte": "font_size", "espacamento": "line_spacing", "largura": "width",
    "mostrar_original": "show_original", "divisao_original": "original_split",
    "zoom_original": "original_zoom", "voz": "voice", "velocidade_voz": "voice_speed",
    "geometria": "geometry",
}
_LEGACY_VALUES = {
    "theme": {"escuro": "dark", "claro": "light", "sepia": "sepia", "preto": "black"},
    "width": {"estreita": "narrow", "media": "medium", "larga": "wide", "total": "full"},
}
_LEGACY_PROGRESS = {
    "pagina": "page", "indice": "index", "nome": "name", "caminho": "path",
    "total_paginas": "page_count", "ultima_leitura": "last_read",
}


def _renamed(data: Any, names: dict[str, str]) -> Any:
    if not isinstance(data, dict):
        return data
    return {names.get(key, key): value for key, value in data.items()}


def _upgrade(data: dict[str, Any]) -> dict[str, Any]:
    """Translate a version 1 file (Portuguese keys) into the current format."""
    if "configuracao" not in data and "progresso" not in data:
        return data
    settings = _renamed(data.get("configuracao"), _LEGACY_SETTINGS)
    if isinstance(settings, dict):
        for key, values in _LEGACY_VALUES.items():
            if settings.get(key) in values:
                settings[key] = values[settings[key]]
    progress = data.get("progresso")
    if isinstance(progress, dict):
        progress = {doc: _renamed(p, _LEGACY_PROGRESS) for doc, p in progress.items()}
    return {"version": _VERSION, "settings": settings, "progress": progress}


def migrate_legacy_folder(data_folder: Path) -> None:
    """Move data and voices from the old "LeitorPDF" folder, if there is one."""
    data_folder = Path(data_folder)
    legacy = data_folder.parent / LEGACY_FOLDER
    if data_folder.exists() or not legacy.is_dir():
        return
    try:
        legacy.rename(data_folder)
        for old, new in (("dados.json", "data.json"), ("vozes", "voices")):
            if (data_folder / old).exists() and not (data_folder / new).exists():
                (data_folder / old).rename(data_folder / new)
    except OSError:
        pass  # in use or no permission: start fresh, nothing is lost
