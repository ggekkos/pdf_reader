"""Color themes and the stylesheet generated from them."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor


@dataclass(frozen=True)
class Theme:
    name: str
    background: str  # window and text background
    surface: str  # cards and panels
    border: str
    text: str
    text_strong: str  # current line in focus mode
    text_muted: str  # captions and secondary information
    highlight: str  # word marker
    text_on_highlight: str
    primary: str  # main button and progress bars
    text_on_primary: str


THEMES: dict[str, Theme] = {
    "dark": Theme(
        "Dark", "#151515", "#1e1e1e", "#2c2c2c", "#d6d6d6", "#ffffff", "#858585",
        "#c9a227", "#111111", "#c9a227", "#111111",
    ),
    "light": Theme(
        "Light", "#f5f5f3", "#ffffff", "#e3e3e0", "#2b2b2b", "#000000", "#7c7c7c",
        "#ffd54f", "#000000", "#2b2b2b", "#ffffff",
    ),
    "sepia": Theme(
        "Sepia", "#f1e7d3", "#f8f1e3", "#dccfb4", "#4b3c2b", "#24180c", "#8d7b62",
        "#e2a84b", "#24180c", "#7a5b3a", "#f8f1e3",
    ),
    "black": Theme(
        "Black", "#000000", "#0d0d0d", "#222222", "#b8b8b8", "#ffffff", "#6b6b6b",
        "#ffb300", "#000000", "#ffb300", "#000000",
    ),
}
DEFAULT_THEME = "dark"

# Fonts offered for the text (only the ones installed on the system show up).
READING_FONTS = ["Georgia", "Cambria", "Palatino Linotype", "Segoe UI", "Verdana", "Calibri"]

# Maximum width of the text column, in pixels (0 = no limit).
WIDTHS = {"narrow": ("Narrow", 600), "medium": ("Medium", 780),
          "wide": ("Wide", 1000), "full": ("Full screen", 0)}


def theme(key: str) -> Theme:
    return THEMES.get(key, THEMES[DEFAULT_THEME])


def mix(background: str, foreground: str, ratio: float) -> QColor:
    """Color between ``background`` (0.0) and ``foreground`` (1.0)."""
    a, b = QColor(background), QColor(foreground)
    p = min(max(ratio, 0.0), 1.0)
    return QColor(
        round(a.red() + (b.red() - a.red()) * p),
        round(a.green() + (b.green() - a.green()) * p),
        round(a.blue() + (b.blue() - a.blue()) * p),
    )


def build_stylesheet(t: Theme) -> str:
    """Stylesheet for the whole app with theme ``t``."""
    hover = mix(t.surface, t.text, 0.08).name()
    return f"""
    QMainWindow, QDialog, QMessageBox, QWidget#root {{ background: {t.background}; }}
    QWidget {{ background: transparent; color: {t.text};
               font-family: "Segoe UI"; font-size: 10pt; }}
    QToolTip {{ background: {t.surface}; color: {t.text};
                border: 1px solid {t.border}; padding: 4px; }}

    QTextEdit {{ background: {t.background}; border: none; }}

    QFrame#appearancePanel {{ background: {t.surface}; border-left: 1px solid {t.border}; }}
    QFrame#tocPanel {{ background: {t.surface}; border-right: 1px solid {t.border}; }}
    QFrame#searchBar {{ background: {t.surface}; border-bottom: 1px solid {t.border}; }}

    QTreeWidget {{ background: transparent; border: none; outline: none;
                   selection-background-color: {hover}; selection-color: {t.text_strong}; }}
    QTreeWidget::item {{ padding: 5px 2px; border-radius: 4px; }}
    QTreeWidget::item:hover {{ background: {hover}; }}
    QTreeWidget::item:selected {{ background: {hover}; color: {t.text_strong}; }}
    QTreeWidget::branch {{ background: transparent; }}
    QTreeWidget::branch:selected {{ background: {hover}; }}

    QLineEdit {{ background: {t.background}; border: 1px solid {t.border}; border-radius: 6px;
                 padding: 5px 8px; selection-background-color: {t.highlight};
                 selection-color: {t.text_on_highlight}; }}
    QLineEdit:focus {{ border-color: {t.text_muted}; }}
    QSplitter::handle {{ background: {t.border}; }}
    QFrame#topBar {{ border-bottom: 1px solid {t.border}; }}
    QFrame#footer {{ border-top: 1px solid {t.border}; }}
    QFrame[card="true"] {{ background: {t.surface}; border: 1px solid {t.border};
                           border-radius: 10px; }}
    QFrame[card="true"]:hover {{ border-color: {t.text_muted}; }}

    QLabel[role="title"] {{ font-size: 26pt; font-weight: 600; color: {t.text_strong}; }}
    QLabel[role="name"] {{ font-size: 11pt; font-weight: 600; color: {t.text_strong}; }}
    QLabel[role="highlight"] {{ font-size: 14pt; font-weight: 600; color: {t.text_strong}; }}
    QLabel[role="section"] {{ font-size: 8pt; font-weight: 700; color: {t.text_muted}; }}
    QLabel[role="muted"] {{ color: {t.text_muted}; }}

    QPushButton {{ background: transparent; border: 1px solid {t.border};
                   border-radius: 6px; padding: 6px 14px; }}
    QPushButton:hover {{ background: {hover}; }}
    QPushButton:checked {{ background: {hover}; border-color: {t.text_muted}; }}
    QPushButton:disabled {{ color: {t.border}; }}
    QPushButton#primary {{ background: {t.primary}; color: {t.text_on_primary};
                           border: none; font-weight: 600; padding: 8px 20px; }}
    QPushButton#primary:hover {{ background: {mix(t.primary, t.background, 0.15).name()}; }}
    QPushButton[plain="true"] {{ border: none; padding: 6px 10px; }}

    QSpinBox, QComboBox {{ background: {t.surface}; border: 1px solid {t.border};
                           border-radius: 6px; padding: 4px 8px; }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox QAbstractItemView {{ background: {t.surface}; border: 1px solid {t.border};
                                   selection-background-color: {hover};
                                   selection-color: {t.text_strong}; }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}

    QSlider::groove:horizontal {{ background: {t.border}; height: 4px; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {t.primary}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {t.text_strong}; width: 14px; height: 14px;
                                  margin: -5px 0; border-radius: 7px; }}
    QSlider::groove:horizontal:disabled, QSlider::sub-page:horizontal:disabled {{
        background: {t.border}; }}

    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {t.text_muted};
                            border-radius: 4px; }}
    QCheckBox::indicator:checked {{ background: {t.primary}; border-color: {t.primary}; }}

    QProgressBar {{ background: {t.border}; border: none; border-radius: 2px;
                    max-height: 4px; min-height: 4px; }}
    QProgressBar::chunk {{ background: {t.primary}; border-radius: 2px; }}

    QScrollArea {{ border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {t.border}; border-radius: 3px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {t.text_muted}; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {t.border}; border-radius: 3px; min-width: 30px; }}
    QScrollBar::handle:horizontal:hover {{ background: {t.text_muted}; }}
    QScrollBar::add-line, QScrollBar::sub-line,
    QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; width: 0; background: none; }}
    """
