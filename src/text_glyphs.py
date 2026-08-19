"""Select Gohu text without accidentally treating terminal art as prose."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from fontTools.ttLib import TTFont

from bdf import load_bdf


# These two punctuation marks deliberately span the cell like terminal rules;
# treating them as ordinary prose would create a visible gap in repeated runs.
EDGE_SPANNING_PUNCTUATION = {0x2014, 0x2015}


def text_glyph_names(font: TTFont, bdf_path: Path) -> set[str]:
    """Return letter, mark, number, and punctuation glyphs from Gohu only."""
    cmap = font.getBestCmap()
    names = {
        cmap[glyph.encoding]
        for glyph in load_bdf(bdf_path).glyphs
        if glyph.encoding in cmap
        and glyph.encoding not in EDGE_SPANNING_PUNCTUATION
        and unicodedata.category(chr(glyph.encoding))[0] in {"L", "M", "N", "P"}
    }
    if "zero.ss01" in font.getGlyphOrder():
        names.add("zero.ss01")
    return names
