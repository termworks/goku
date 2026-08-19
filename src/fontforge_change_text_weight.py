#!/usr/bin/env fontforge
"""Use FontForge's stem-aware weight engine on text glyphs only."""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import fontforge


def is_text_glyph(glyph) -> bool:
    if glyph.glyphname == "zero.ss01":
        return True
    codepoint = glyph.unicode
    return codepoint >= 0 and unicodedata.category(chr(codepoint))[0] in {
        "L",
        "M",
        "N",
        "P",
    }


def main() -> None:
    if len(sys.argv) not in {4, 5}:
        raise SystemExit(
            "usage: script.py INPUT.ttf OUTPUT.ttf STEM_DELTA [GLYPH_NAMES.txt]"
        )
    source, output, delta_text = sys.argv[1:4]
    requested_codepoints: set[int] | None = None
    requested_names: set[str] = set()
    if len(sys.argv) == 5:
        requested_codepoints = set()
        for line in Path(sys.argv[4]).read_text(encoding="utf-8").splitlines():
            if line.startswith("U+"):
                requested_codepoints.add(int(line[2:], 16))
            elif line.startswith("name:"):
                requested_names.add(line.removeprefix("name:"))
            elif line:
                raise ValueError(f"invalid selection line: {line}")
    delta = float(delta_text)
    font = fontforge.open(source)
    font.selection.none()
    selected = 0
    found_codepoints: set[int] = set()
    found_names: set[str] = set()
    for glyph in font.glyphs():
        glyph_codepoints = {glyph.unicode} if glyph.unicode >= 0 else set()
        for alternate in glyph.altuni or ():
            glyph_codepoints.add(alternate[0])
        if requested_codepoints is not None:
            matched_codepoints = glyph_codepoints & requested_codepoints
            matched_names = {glyph.glyphname} & requested_names
            should_select = bool(matched_codepoints or matched_names)
            found_codepoints.update(matched_codepoints)
            found_names.update(matched_names)
        else:
            should_select = is_text_glyph(glyph)
        if should_select:
            font.selection.select(("more",), glyph.glyphname)
            selected += 1
    if requested_codepoints is not None:
        missing_codepoints = requested_codepoints - found_codepoints
        missing_names = requested_names - found_names
        if missing_codepoints or missing_names:
            labels = [f"U+{codepoint:04X}" for codepoint in missing_codepoints]
            labels.extend(f"name:{name}" for name in missing_names)
            raise ValueError(f"missing requested glyphs: {sorted(labels)}")
    font.changeWeight(delta, "auto", 0, 0, "retain")
    font.generate(output)
    font.close()
    print(f"Changed {selected} text glyphs by {delta:g} units -> {output}")


if __name__ == "__main__":
    main()
