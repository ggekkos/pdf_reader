"""Side panel with the appearance and reading options."""

from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from pdf_reader.core.voices import VOICES
from pdf_reader.storage import Settings
from pdf_reader.ui.theme import READING_FONTS, THEMES, WIDTHS
from pdf_reader.ui.widgets import label, no_focus

_SHORTCUTS = (
    "Space  read / pause\n"
    "V  read aloud / stop\n"
    "↑ ↓  previous / next line\n"
    "← →  previous / next word\n"
    "PgUp PgDn  page\n"
    "P  show / hide the original PDF\n"
    "Ctrl + wheel  zoom the original PDF\n"
    "S  table of contents\n"
    "Ctrl+F  search  (F3 next)\n"
    "Ctrl+O  open PDF\n"
    "Esc  back to home"
)


class AppearancePanel(QFrame):
    """Edits the :class:`Settings` directly and signals when something changes."""

    changed = Signal()
    theme_changed = Signal()

    def __init__(self, settings: Settings, voices_folder: Path | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("appearancePanel")
        self.setFixedWidth(300)
        self._settings = settings
        self._voices_folder = voices_folder

        # The content scrolls when the window is short.
        content = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)

        layout.addWidget(label("THEME", "section"))
        layout.addLayout(self._theme_picker())

        layout.addSpacing(10)
        layout.addWidget(label("TEXT", "section"))
        layout.addWidget(self._font_picker())
        layout.addLayout(self._slider(
            "Size", 12, 40, settings.font_size, "{} pt", "font_size"))
        layout.addLayout(self._slider(
            "Spacing", 110, 220, settings.line_spacing, None, "line_spacing",
            fmt=lambda v: f"{v / 100:.1f}×"))
        layout.addWidget(self._width_picker())

        layout.addSpacing(10)
        layout.addWidget(label("READING", "section"))
        self._word_check = self._checkbox("Highlight word", "highlight_word")
        self._focus_check = self._checkbox("Focus mode", "focus_mode")
        layout.addWidget(self._word_check)
        layout.addWidget(self._focus_check)
        visibility_row, self._visibility_slider = self._slider_with_widget(
            "Surrounding text", 0, 100, settings.focus_visibility, "{}%", "focus_visibility")
        layout.addLayout(visibility_row)
        self._visibility_slider.setEnabled(settings.focus_mode)
        margins = self._checkbox("Skip header and footer", "skip_margins")
        margins.setToolTip("Don't read titles repeated at the top of pages, or page numbers")
        layout.addWidget(margins)

        layout.addSpacing(10)
        layout.addWidget(label("VOICE", "section"))
        self._voice_combo = self._voice_picker()
        layout.addWidget(self._voice_combo)
        layout.addLayout(self._slider(
            "Speed", 50, 200, settings.voice_speed, "{}%", "voice_speed"))

        layout.addStretch()
        layout.addWidget(label("SHORTCUTS", "section"))
        layout.addWidget(label(_SHORTCUTS, "muted"))

    # --- construction ---
    def _theme_picker(self) -> QHBoxLayout:
        row = QHBoxLayout()
        group = QButtonGroup(self)
        self._theme_buttons: dict[str, QPushButton] = {}
        for key, theme in THEMES.items():
            b = no_focus(QPushButton("Aa"))
            b.setCheckable(True)
            b.setChecked(key == self._settings.theme)
            b.setFixedSize(54, 42)
            b.setToolTip(theme.name)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            # Each swatch is painted with its own theme's colors.
            b.setStyleSheet(
                f"QPushButton {{ background: {theme.background}; color: {theme.text};"
                f" border: 2px solid {theme.border}; border-radius: 8px;"
                f" font-family: Georgia; font-size: 13pt; padding: 0; }}"
                f"QPushButton:checked {{ border-color: {theme.highlight}; }}"
            )
            b.clicked.connect(partial(self._choose_theme, key))
            group.addButton(b)
            row.addWidget(b)
            self._theme_buttons[key] = b
        return row

    def _font_picker(self) -> QComboBox:
        combo = no_focus(QComboBox())
        installed = set(QFontDatabase.families())
        fonts = [f for f in READING_FONTS if f in installed] or [self._settings.font]
        if self._settings.font not in fonts:
            fonts.insert(0, self._settings.font)
        for font in fonts:
            combo.addItem(font)
            combo.setItemData(combo.count() - 1, QFont(font, 11), Qt.ItemDataRole.FontRole)
        combo.setCurrentText(self._settings.font)
        combo.currentTextChanged.connect(partial(self._set, "font"))
        return combo

    def _width_picker(self) -> QComboBox:
        combo = no_focus(QComboBox())
        for key, (name, _) in WIDTHS.items():
            combo.addItem(f"Width: {name}", key)
        index = combo.findData(self._settings.width)
        combo.setCurrentIndex(max(index, 0))
        combo.currentIndexChanged.connect(
            lambda i: self._set("width", combo.itemData(i)))
        return combo

    def _voice_picker(self) -> QComboBox:
        combo = no_focus(QComboBox())
        combo.setToolTip("Voice for reading aloud (V key)")
        for voice in VOICES:
            combo.addItem("", voice.id)
        self.refresh_voices(combo)
        index = combo.findData(self._settings.voice)
        combo.setCurrentIndex(max(index, 0))
        combo.currentIndexChanged.connect(lambda i: self._set("voice", combo.itemData(i)))
        return combo

    def refresh_voices(self, combo: QComboBox | None = None) -> None:
        """Show which voices still need to be downloaded."""
        combo = combo or self._voice_combo
        for i, voice in enumerate(VOICES):
            downloaded = self._voices_folder is None or voice.is_downloaded(self._voices_folder)
            suffix = "" if downloaded else f"  (download {voice.size_mb} MB)"
            combo.setItemText(i, f"Voice: {voice.label}{suffix}")
            combo.setItemData(i, voice.description, Qt.ItemDataRole.ToolTipRole)

    def _checkbox(self, text: str, field: str) -> QCheckBox:
        box = no_focus(QCheckBox(text))
        box.setChecked(getattr(self._settings, field))
        box.toggled.connect(partial(self._set, field))
        return box

    def _slider(self, title, minimum, maximum, value, template, field, fmt=None):
        row, _ = self._slider_with_widget(title, minimum, maximum, value, template, field, fmt)
        return row

    def _slider_with_widget(self, title, minimum, maximum, value, template, field, fmt=None):
        fmt = fmt or template.format
        slider = no_focus(QSlider(Qt.Orientation.Horizontal))
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        caption = label(fmt(value), "muted")
        caption.setMinimumWidth(44)
        caption.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        def moved(v: int) -> None:
            caption.setText(fmt(v))
            self._set(field, v)

        slider.valueChanged.connect(moved)
        row = QHBoxLayout()
        name = label(title)
        name.setMinimumWidth(96)
        row.addWidget(name)
        row.addWidget(slider, stretch=1)
        row.addWidget(caption)
        return row, slider

    # --- reactions ---
    def _set(self, field: str, value) -> None:
        setattr(self._settings, field, value)
        if field == "focus_mode":
            self._visibility_slider.setEnabled(value)
        self.changed.emit()

    def _choose_theme(self, key: str) -> None:
        self._theme_buttons[key].setChecked(True)
        if key != self._settings.theme:
            self._settings.theme = key
            self.theme_changed.emit()
            self.changed.emit()
