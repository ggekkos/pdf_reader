"""Generate the app icon (``pdf_reader/assets/icon.ico`` and ``icon.png``).

Usage: ``python tools/make_icon.py``. Draws at 1024 px and scales down,
so the edges stay smooth at every size.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

S = 1024
BACKGROUND = "#1e1e1e"
PAGE = "#f1ece1"
LINE = "#b9b2a4"
HIGHLIGHT = "#c9a227"
FOLD = "#d6cfbf"

TARGET = Path(__file__).resolve().parent.parent / "pdf_reader" / "assets"


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Background: dark rounded square.
    d.rounded_rectangle((32, 32, S - 32, S - 32), radius=200, fill=BACKGROUND)

    # Page with its top-right corner folded.
    x0, y0, x1, y1 = 232, 150, 792, 874
    fold = 150
    d.rounded_rectangle((x0, y0, x1, y1), radius=36, fill=PAGE)
    d.polygon([(x1 - fold, y0), (x1 + 1, y0), (x1 + 1, y0 + fold)], fill=BACKGROUND)
    d.rectangle((x1 - fold - 2, y0 - 2, x1 + 2, y0 + 30), fill=BACKGROUND)
    d.rectangle((x1 - 30, y0 - 2, x1 + 2, y0 + fold + 2), fill=BACKGROUND)
    d.polygon([(x1 - fold, y0), (x1 - fold, y0 + fold), (x1, y0 + fold)], fill=FOLD)
    d.rectangle((x1 - fold, y0 + 20, x1 - fold + 1, y0 + fold), fill=PAGE)

    # Lines of text; on the middle one, a "word" highlighted by the marker.
    left, h, r = x0 + 70, 34, 17
    lines = [(300, 540), (380, 650), (460, 610), (540, 650), (620, 520), (700, 600)]
    for i, (y, right) in enumerate(lines):
        if i == 0:
            right = min(right, x1 - fold - 40)
        if i == 2:
            # Line with the highlighted word in the middle.
            d.rounded_rectangle((left, y, left + 90, y + h), radius=r, fill=LINE)
            d.rounded_rectangle((left + 120, y - 26, left + 330, y + h + 26), radius=28,
                                fill=HIGHLIGHT)
            d.rounded_rectangle((left + 150, y, left + 300, y + h), radius=r, fill="#111111")
            d.rounded_rectangle((left + 360, y, x1 - 70, y + h), radius=r, fill=LINE)
            continue
        d.rounded_rectangle((left, y, x1 - 70 - (650 - right) // 2, y + h), radius=r,
                            fill=LINE)
    return img


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    img = draw()
    img.resize((256, 256), Image.LANCZOS).save(TARGET / "icon.png")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(TARGET / "icon.ico", sizes=sizes)
    print(f"Icon saved to {TARGET}")


if __name__ == "__main__":
    main()
