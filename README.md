# PDF Reader

A PDF reader for guided reading: a marker moves word by word, and **focus mode**
dims the surrounding text, leaving only the current line lit.

- Home screen with "continue reading" and a list of recent PDFs (or drag a PDF onto the window)
- Themes: dark, light, sepia and black
- Adjustable font, size, line spacing and column width (**Aa** button)
- Word highlight and focus mode can each be turned on or off
- **PDF** button (or the P key): shows the original PDF page in a split view on the right,
  with the current word marked, to check for extraction errors. Drag the divider to adjust
  and use Ctrl + mouse wheel to zoom
- Skips repeated headers, footers and page numbers (can be turned off in **Aa**)
- Words hyphenated across a page turn are joined, and reading doesn't pause mid-sentence
- The PDF's table of contents (**☰** button) and search that ignores accents and case (Ctrl+F)
- Estimated time to the end of the chapter, at the chosen speed
- The window reopens with the same size and position it was closed with
- **Read aloud** (**🔊 Listen** button or the V key) with neural voices from the
  [Piper](https://github.com/OHF-Voice/piper1-gpl) and [Kokoro](https://github.com/thewh1teagle/kokoro-onnx)
  engines, which run on your own computer, offline. The sentence being spoken is highlighted
  and pages turn on their own. Voice and speed are in **Aa**

## Voices

There are voices in Brazilian Portuguese, American English and British English, grouped by
language in the **Aa** panel. Pick one in the same language as the PDF. The voices don't ship
with the app: the first time you use one, the app asks and downloads it to
`%APPDATA%\PDFReader\voices`. After that, it works offline.

### Português (Brasil)

| Voice | Gender | Engine | Download | License |
|---|---|---|---|---|
| Dii | female | Piper (OpenVoiceOS) | 64 MB | CC BY-NC-ND 4.0 (personal, non-commercial use) |
| Dora | female | Kokoro | 116 MB* | Apache 2.0 |
| Faber, Cadu, Jeff | male | Piper | 63 MB each | CC0 |
| Miro | male | Piper (OpenVoiceOS) | 64 MB | CC BY-NC-ND 4.0 (personal, non-commercial use) |
| Alex, Santa | male | Kokoro | 116 MB* | Apache 2.0 |
| Edresson | male (lower quality) | Piper | 63 MB | CC BY 4.0 |

### English (US)

| Voice | Gender | Engine | Download | License |
|---|---|---|---|---|
| Heart, Bella | female | Kokoro | 116 MB* | Apache 2.0 |
| Kristin | female | Piper | 63 MB | public domain |
| Linda | female | Piper (LJ Speech) | 63 MB | public domain |
| Michael, Fenrir | male | Kokoro | 116 MB* | Apache 2.0 |
| Joe | male | Piper | 63 MB | CC0 |
| John, Norman | male | Piper | 63 MB each | public domain |

### English (UK)

| Voice | Gender | Engine | Download | License |
|---|---|---|---|---|
| Emma | female | Kokoro | 116 MB* | Apache 2.0 |
| Cori | female | Piper | 63 MB | CC BY 4.0 |
| Alba | female (Scottish accent) | Piper | 63 MB | CC BY 4.0 |
| George | male | Kokoro | 116 MB* | Apache 2.0 |
| Northern | male (Northern English accent) | Piper | 63 MB | CC BY-SA 4.0 |

\* All Kokoro voices, in every language, share a single download: getting one unlocks all of them.
Kokoro takes a few more seconds to start speaking. Piper voices without a note come from the
[official Piper catalog](https://huggingface.co/rhasspy/piper-voices).

## Install and run

```bash
pip install -e ".[dev]"
python -m pdf_reader            # opens the home screen with recent readings
python -m pdf_reader book.pdf
```

## Shortcuts

| Key | Action |
|---|---|
| Space | read / pause (or stop the voice) |
| V | read aloud / stop |
| ↑ ↓ | previous / next line |
| ← → | previous / next word |
| PgUp PgDn | previous / next page |
| P | show / hide the original PDF |
| Ctrl + wheel, Ctrl+= / Ctrl+- / Ctrl+0 | zoom the original PDF |
| S | table of contents |
| Ctrl+F, F3 / Shift+F3 | search, next / previous |
| Ctrl+O | open PDF |
| Esc | back to home |
| Click | jump to the word |

## Structure

```
pdf_reader/
├── __main__.py           entry point
├── storage.py            preferences and progress (JSON in the user folder)
├── core/                 logic with no interface (testable)
│   ├── text.py           cleanup: LaTeX accents, ligatures, hyphenation
│   ├── document.py       opens the PDF, identifies the file by its content
│   ├── margins.py        detects headers, footers and page numbers
│   ├── search.py         search ignoring accents and case
│   ├── toc.py            chapters and where each one ends
│   ├── speech.py         splits the text into sentences for the voice, with pauses
│   ├── voices.py         voices (Piper and Kokoro): catalog, download and synthesis
│   ├── session.py        reading position (page/word)
│   ├── pacing.py         time per word, with pauses at punctuation
│   └── formatting.py     text like "2 days ago"
└── ui/
    ├── main_window.py    switches between screens, drag and drop
    ├── home_screen.py    recent files and "continue reading"
    ├── reading_screen.py reading bar, pages and shortcuts
    ├── text_panel.py     text, marker and focus mode
    ├── original_panel.py the PDF's original page, next to the text
    ├── toc_panel.py      the PDF's table of contents
    ├── narrator.py       generates audio in the background and plays it sentence by sentence
    ├── voice_download.py downloads a voice while showing progress
    ├── appearance_panel.py  theme, font and reading options
    ├── widgets.py        reusable buttons, labels and cards
    └── theme.py          color themes and stylesheet
```

Progress is stored in `%APPDATA%\PDFReader\data.json` and is keyed by the
PDF's content: moving or renaming the file loses nothing.

## Tests

```bash
pytest
```

## Build the executable (Windows)

```
pip install pyinstaller
pyinstaller --noconfirm pdf-reader.spec
```

The result is `dist/PDFReader.exe`, a single file that runs without Python installed.
The icon lives in `pdf_reader/assets/`. To redraw it, edit and run `python tools/make_icon.py` (needs Pillow).

## License

Copyright (C) 2026 ggekkos

This program is free software: you can redistribute it and/or modify it under the terms of
the GNU General Public License as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version. It is distributed WITHOUT ANY WARRANTY.
See [LICENSE](LICENSE) for the full text.

The GPL is required by some of the libraries the app uses:

| Dependency | License |
|---|---|
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | AGPL-3.0 (combining with GPL-3.0 is allowed by section 13 of both licenses) |
| [piper-tts](https://github.com/OHF-Voice/piper1-gpl) | GPL-3.0 |
| [phonemizer](https://github.com/bootphon/phonemizer) | GPL-3.0 |
| [espeak-ng](https://github.com/espeak-ng/espeak-ng) (via espeakng-loader) | GPL-3.0 |
| [PySide6 / Qt](https://www.qt.io/qt-for-python) | LGPL-3.0 |
| [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) | MIT |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | MIT |
| [NumPy](https://numpy.org) | BSD-3-Clause |

The voices are downloaded separately and keep their own licenses (see [Voices](#voices)).
Some of them (Dii, Miro) are for personal, non-commercial use only.
