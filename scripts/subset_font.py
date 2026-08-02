"""
Subsets a JetBrains Mono TTF down to only the 13 characters the portrait
and year-ramp ever draw, and writes it as woff2. Pure Python -- no bash,
no shell quoting headaches with backtick/quote characters.

Usage:
    python scripts/subset_font.py "C:\\path\\to\\JetBrainsMono-Regular.ttf"

Writes: assets/fonts/jbmono-ramp.woff2
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from svgutils import RAMP


def main():
    if len(sys.argv) != 2:
        print("usage: python scripts/subset_font.py /path/to/JetBrainsMono-Regular.ttf")
        sys.exit(1)

    src = sys.argv[1]
    if not os.path.exists(src):
        print(f"file not found: {src}")
        sys.exit(1)

    from fontTools import subset
    from fontTools.ttLib import TTFont

    out_dir = os.path.join("assets", "fonts")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "jbmono-ramp.woff2")

    font = TTFont(src)
    subsetter = subset.Subsetter()
    subsetter.populate(text=RAMP)
    subsetter.subset(font)
    font.flavor = "woff2"
    font.save(out_path)

    size_kb = os.path.getsize(out_path) / 1024
    print(f"wrote {out_path} ({size_kb:.1f} KB, {len(RAMP)} characters)")
    print("copy the font's LICENSE.txt into assets/fonts/ too (SIL OFL 1.1)")


if __name__ == "__main__":
    main()
