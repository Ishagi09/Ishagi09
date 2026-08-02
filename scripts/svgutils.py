"""Shared helpers for the profile SVG generators."""
from __future__ import annotations
import base64
import os

# 13-level brightness ramp, light -> dark. Index 0 MUST stay a real space
# so the background (post background-removal) reads as empty, not as a
# printed glyph.
RAMP = " .'`:;-=+*#%@"

FONT_FAMILY = "JBMonoProfile"


def escape_svg_text(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def font_face_css(font_path: str | None) -> str:
    """Return an @font-face block with the font inlined as base64 data URI.

    font_path should point to a woff2 (or ttf) file already SUBSET to only
    the glyphs actually used on the page (see scripts/subset_font.sh) --
    inlining a full TTF is ~4.5MB, a 13-character ramp subset is ~1.3KB.
    """
    if not font_path or not os.path.exists(font_path):
        return ""
    with open(font_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    fmt = "woff2" if font_path.endswith(".woff2") else "truetype"
    return f"""
    @font-face {{
      font-family: '{FONT_FAMILY}';
      src: url(data:font/{fmt};base64,{data}) format('{fmt}');
      font-weight: 400;
      font-style: normal;
    }}
    """


def char_advance(font_size: float) -> float:
    """Monospace advance width for JetBrains Mono at 0.600em."""
    return font_size * 0.6
