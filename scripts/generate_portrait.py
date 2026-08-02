"""
Turns a headshot into a self-typing ASCII portrait SVG.

Run this ONCE, locally, whenever you want to change the photo. It is not
part of the daily GitHub Actions workflow (that only refreshes stats).

Usage:
    python scripts/generate_portrait.py photo.jpg assets/portrait.svg \
        --font assets/fonts/jbmono-ramp.woff2 --cols 90

Photo guidelines that actually matter (bad input can't be fixed by tuning):
  - side light (~45 deg), not flat frontal light
  - fill the frame: chin to just above the hair
  - 1200px+ source resolution
  - plain background, and don't wear black against a dark wall
  - slight angle, not dead-on

Pipeline: rembg cutout (forces background to white) -> grayscale ->
bilateral filter (smooth skin, keep edges) -> CLAHE (local contrast) ->
darkening curve (v/255)^1.7 (keeps glasses/brows/lips from washing out) ->
map to a 13-level ramp -> SVG with a per-row typing animation (SMIL),
single fill colour (no per-character rainbow -- that's what makes most
ASCII art look like static), font embedded as base64 since GitHub's
sanitiser strips <style> blocks it doesn't already know but keeps
inline @font-face data URIs inside an SVG's own <style>.
"""
from __future__ import annotations
import argparse
import sys

import numpy as np
import cv2
from PIL import Image

from svgutils import RAMP, FONT_FAMILY, escape_svg_text, font_face_css, char_advance


def remove_background(img: Image.Image) -> Image.Image:
    from rembg import remove  # imported lazily: heavy, downloads a model on first use
    cut = remove(img)  # -> RGBA, subject isolated, rest transparent
    bg = Image.new("RGBA", cut.size, (255, 255, 255, 255))
    bg.paste(cut, (0, 0), cut)
    return bg.convert("RGB")


def to_ascii_grid(img: Image.Image, cols: int):
    """Returns (lines, colors) where colors[i][j] is a '#rrggbb' string
    sampled from the same cell -- so hair, skin and accessories keep their
    own tone instead of one flat fill. This is not per-character *rainbow*
    (arbitrary/random hues, which makes ASCII art look like static); it's
    the real colour of that region of the photo.
    """
    w, h = img.size
    # monospace characters are ~2x taller than wide, hence the 0.48 factor
    rows = max(1, round(cols * (h / w) * 0.48))

    rgb = np.array(img)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    small = cv2.resize(gray, (cols, rows), interpolation=cv2.INTER_AREA)
    color_small = cv2.resize(rgb, (cols, rows), interpolation=cv2.INTER_AREA)

    curved = 255.0 * (small.astype(np.float64) / 255.0) ** 1.7

    levels = len(RAMP)
    lines = []
    colors = []
    for yi, row in enumerate(curved):
        line_chars = []
        color_row = []
        for xi, v in enumerate(row):
            # v near 255 (bright/background) -> RAMP[0] (space)
            # v near 0 (dark) -> RAMP[-1] (densest glyph)
            idx = int(round((255 - v) / 255 * (levels - 1)))
            idx = max(0, min(levels - 1, idx))
            line_chars.append(RAMP[idx])
            r, g, b = color_small[yi, xi]
            color_row.append(f"#{r:02x}{g:02x}{b:02x}")
        lines.append("".join(line_chars))
        colors.append(color_row)
    return lines, colors


def build_svg(lines: list[str], colors: list[list[str]] | None, font_path: str | None,
              font_size: float = 12.9, fill: str = "#c9d1d9", stagger: float = 0.09) -> str:
    advance = char_advance(font_size)
    line_height = font_size * 1.15
    cols = max((len(l) for l in lines), default=0)
    width = advance * cols
    height = line_height * len(lines)

    font_css = font_face_css(font_path)
    family = f"'{FONT_FAMILY}', monospace" if font_css else "monospace"

    rows_svg = []
    for i, line in enumerate(lines):
        y = (i + 1) * line_height - (line_height * 0.25)
        row_w = advance * len(line)
        clip_id = f"clip{i}"

        if colors is not None:
            # one <tspan> per character with its own sampled colour.
            # monospace advance keeps them aligned without explicit x's.
            spans = "".join(
                f'<tspan fill="{colors[i][j]}">{escape_svg_text(ch)}</tspan>'
                for j, ch in enumerate(line)
            )
        else:
            spans = escape_svg_text(line)

        rows_svg.append(f"""
    <clipPath id="{clip_id}">
      <rect x="0" y="{y - line_height:.2f}" width="0" height="{line_height:.2f}">
        <animate attributeName="width" from="0" to="{row_w:.2f}"
          begin="{i * stagger:.2f}s" dur="0.35s" fill="freeze" />
      </rect>
    </clipPath>
    <text x="0" y="{y:.2f}" font-size="{font_size}" fill="{fill}"
      clip-path="url(#{clip_id})" xml:space="preserve">{spans}</text>""")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}"
  viewBox="0 0 {width:.0f} {height:.0f}">
  <style>
    {font_css}
    text {{ font-family: {family}; }}
  </style>
  {''.join(rows_svg)}
</svg>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("photo")
    ap.add_argument("out_svg")
    ap.add_argument("--font", default=None,
                     help="path to a subset woff2/ttf to embed (see scripts/subset_font.sh)")
    ap.add_argument("--cols", type=int, default=90,
                     help="below ~88 the face muddies, much above it the block dominates the page")
    ap.add_argument("--font-size", type=float, default=12.9)
    ap.add_argument("--fill", default="#c9d1d9", help="fill colour used only in --mode mono")
    ap.add_argument("--mode", choices=["color", "mono"], default="color",
                     help="color = each character keeps the real tone from that part of the "
                          "photo (hair/skin/accessories separate); mono = one flat fill colour")
    args = ap.parse_args()

    img = Image.open(args.photo).convert("RGB")
    img = remove_background(img)
    lines, colors = to_ascii_grid(img, args.cols)
    if args.mode == "mono":
        colors = None
    svg = build_svg(lines, colors, args.font, args.font_size, args.fill)

    with open(args.out_svg, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {args.out_svg} ({len(lines)} rows x {args.cols} cols)")


if __name__ == "__main__":
    sys.exit(main())
