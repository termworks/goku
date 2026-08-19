#!/usr/bin/env python3
"""Validate the four-face Goku terminal-font collection."""

from __future__ import annotations

import argparse
import copy
import unicodedata
from pathlib import Path

from fontTools.ttLib import TTCollection, TTFont

from bdf import load_bdf
from design import (
    ASCENT,
    CELL_WIDTH,
    DESCENT,
    FAMILY,
    FONT_TIMESTAMP,
    ITALIC_OVERHANG,
    POSTSCRIPT_STEM,
    UPM,
    VERSION,
)
from font_variants import is_powerline, is_private_use


EXPECTED_STYLES = {"Regular", "Bold", "Italic", "Bold Italic"}
HINT_TABLES = {"cvt ", "fpgm", "prep"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", required=True, type=Path)
    parser.add_argument("--regular-bdf", required=True, type=Path)
    parser.add_argument("--bold-bdf", required=True, type=Path)
    return parser.parse_args()


def names(font: TTFont, name_id: int) -> set[str]:
    return {
        record.toUnicode()
        for record in font["name"].names
        if record.nameID == name_id
    }


def style(font: TTFont) -> str:
    matches = names(font, 2) & EXPECTED_STYLES
    assert len(matches) == 1, f"ambiguous style names: {names(font, 2)}"
    return matches.pop()


def typographic_metrics(font: TTFont) -> tuple[int, ...]:
    return (
        font["head"].unitsPerEm,
        font["hhea"].ascent,
        font["hhea"].descent,
        font["hhea"].lineGap,
        font["OS/2"].sTypoAscender,
        font["OS/2"].sTypoDescender,
        font["OS/2"].sTypoLineGap,
    )


def glyph_outline_bytes(font: TTFont, codepoint_or_name: int | str) -> bytes:
    name = (
        font.getBestCmap()[codepoint_or_name]
        if isinstance(codepoint_or_name, int)
        else codepoint_or_name
    )
    glyph = copy.deepcopy(font["glyf"][name])
    glyph.removeHinting()
    return glyph.compile(font["glyf"])


def glyph_bounds_by_name(
    font: TTFont,
    name: str,
) -> tuple[int, int, int, int] | None:
    glyph = font["glyf"][name]
    if glyph.numberOfContours == 0:
        return None
    glyph.recalcBounds(font["glyf"])
    return glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax


def glyph_bounds(font: TTFont, codepoint: int) -> tuple[int, int, int, int]:
    bounds = glyph_bounds_by_name(font, font.getBestCmap()[codepoint])
    assert bounds is not None
    return bounds


def font_vertical_bounds(font: TTFont) -> tuple[int, int]:
    bounds = [
        value
        for name in font.getGlyphOrder()
        if (value := glyph_bounds_by_name(font, name)) is not None
    ]
    return min(value[1] for value in bounds), max(value[3] for value in bounds)


def has_glyph_program(font: TTFont, name: str) -> bool:
    glyph = font["glyf"][name]
    return bool(
        hasattr(glyph, "program")
        and glyph.program is not None
        and glyph.program.getBytecode()
    )


def text_glyph_names(font: TTFont, bdf_path: Path) -> set[str]:
    cmap = font.getBestCmap()
    selected = {
        cmap[glyph.encoding]
        for glyph in load_bdf(bdf_path).glyphs
        if glyph.encoding in cmap
        and unicodedata.category(chr(glyph.encoding))[0] in {"L", "M", "N", "P"}
    }
    selected.add("zero.ss01")
    return selected


def single_substitutions(font: TTFont, feature_tag: str) -> dict[str, str]:
    feature_list = font["GSUB"].table.FeatureList.FeatureRecord
    lookup_list = font["GSUB"].table.LookupList.Lookup
    mapping: dict[str, str] = {}
    for record in feature_list:
        if record.FeatureTag != feature_tag:
            continue
        for index in record.Feature.LookupListIndex:
            for subtable in lookup_list[index].SubTable:
                mapping.update(getattr(subtable, "mapping", {}))
    return mapping


def validate_icon_bounds(font: TTFont) -> int:
    cmap = font.getBestCmap()
    names_to_check = {
        name
        for codepoint, name in cmap.items()
        if is_private_use(codepoint) and not is_powerline(codepoint)
    }
    checked = 0
    for name in names_to_check:
        bounds = glyph_bounds_by_name(font, name)
        if bounds is None:
            continue
        assert 0 <= bounds[0] <= bounds[2] <= CELL_WIDTH, (
            f"ordinary icon {name} escapes cell: {bounds}"
        )
        checked += 1
    return checked


def validate_italic_overhang(font: TTFont, text_names: set[str]) -> int:
    checked = 0
    for name in text_names:
        bounds = glyph_bounds_by_name(font, name)
        if bounds is None:
            continue
        assert -ITALIC_OVERHANG <= bounds[0]
        assert bounds[2] <= CELL_WIDTH + ITALIC_OVERHANG
        checked += 1
    return checked


def main() -> None:
    args = parse_args()
    collection = TTCollection(args.collection)
    assert len(collection.fonts) == 4, "Goku collection must contain four faces"
    faces = {style(font): font for font in collection.fonts}
    assert set(faces) == EXPECTED_STYLES
    regular = faces["Regular"]
    bold = faces["Bold"]
    italic = faces["Italic"]
    bold_italic = faces["Bold Italic"]
    regular_bdf = load_bdf(args.regular_bdf)
    bold_bdf = load_bdf(args.bold_bdf)

    reference_order = regular.getGlyphOrder()
    reference_cmap = regular.getBestCmap()
    reference_widths = {
        name: advance for name, (advance, _) in regular["hmtx"].metrics.items()
    }
    expected_metrics = (UPM, ASCENT, DESCENT, 0, ASCENT, DESCENT, 0)
    assert ASCENT - DESCENT == UPM
    assert len(reference_cmap) > 10_000, "Nerd glyph set was not merged"
    assert "zero.ss01" in reference_order
    # The conventional control glyph `.null` has no advance; every printable
    # or terminal-addressable glyph must use the single Goku cell width.
    assert reference_widths.get(".null") == 0
    assert {
        advance for name, advance in reference_widths.items() if name != ".null"
    } == {CELL_WIDTH}

    text_by_style = {
        "Regular": text_glyph_names(regular, args.regular_bdf),
        "Bold": text_glyph_names(bold, args.bold_bdf),
        "Italic": text_glyph_names(italic, args.regular_bdf),
        "Bold Italic": text_glyph_names(bold_italic, args.bold_bdf),
    }
    hint_counts: dict[str, int] = {}
    icon_counts: dict[str, int] = {}

    for face_style, font in faces.items():
        assert names(font, 1) == {FAMILY}
        assert names(font, 16) == {FAMILY}
        assert names(font, 2) == {face_style}
        assert names(font, 17) == {face_style}
        assert names(font, 5) == {f"Version {VERSION}; Goku"}
        ps_style = face_style.replace(" ", "")
        assert names(font, 6) == {f"{POSTSCRIPT_STEM}-{ps_style}"}
        assert font.getGlyphOrder() == reference_order
        assert font.getBestCmap() == reference_cmap
        assert typographic_metrics(font) == expected_metrics
        assert font["head"].created == FONT_TIMESTAMP
        assert font["head"].modified == FONT_TIMESTAMP
        assert {
            name: advance for name, (advance, _) in font["hmtx"].metrics.items()
        } == reference_widths
        expected_weight = 700 if "Bold" in face_style else 400
        assert font["OS/2"].usWeightClass == expected_weight
        is_italic = "Italic" in face_style
        assert bool(font["OS/2"].fsSelection & 1) == is_italic
        assert font["OS/2"].fsSelection & (1 << 7), "USE_TYPO_METRICS missing"
        assert font["OS/2"].fsSelection & (1 << 8), "WWS bit missing"
        assert not font["OS/2"].fsSelection & (1 << 9)
        assert bool(font["head"].macStyle & 2) == is_italic
        assert font["post"].italicAngle == (-12 if is_italic else 0)
        minimum, maximum = font_vertical_bounds(font)
        assert font["OS/2"].usWinAscent >= maximum
        assert font["OS/2"].usWinDescent >= -minimum
        assert HINT_TABLES <= set(font.keys())
        substitutions = single_substitutions(font, "ss01")
        assert substitutions.get("zero") == "zero.ss01"

        text_names = text_by_style[face_style]
        hinted = {name for name in text_names if has_glyph_program(font, name)}
        hinted_symbols = {
            name
            for name in font.getGlyphOrder()
            if name not in text_names and has_glyph_program(font, name)
        }
        assert len(hinted) >= 300, f"too few hinted text glyphs: {len(hinted)}"
        assert not hinted_symbols, (
            f"symbol glyphs unexpectedly contain bytecode: {sorted(hinted_symbols)[:8]}"
        )
        hint_counts[face_style] = len(hinted)
        icon_counts[face_style] = validate_icon_bounds(font)

    regular_codepoints = {glyph.encoding for glyph in regular_bdf.glyphs}
    bold_codepoints = {glyph.encoding for glyph in bold_bdf.glyphs}
    assert regular_codepoints <= reference_cmap.keys()
    assert bold_codepoints <= reference_cmap.keys()
    changed_bold = sum(
        glyph_outline_bytes(regular, codepoint)
        != glyph_outline_bytes(bold, codepoint)
        for codepoint in regular_codepoints & bold_codepoints
    )
    regular_pixels = {glyph.encoding: glyph.pixels for glyph in regular_bdf.glyphs}
    bold_pixels = {glyph.encoding: glyph.pixels for glyph in bold_bdf.glyphs}
    source_changed = sum(
        regular_pixels[codepoint] != bold_pixels[codepoint]
        for codepoint in regular_codepoints & bold_codepoints
    )
    assert changed_bold == source_changed

    full_cell = (0, DESCENT, CELL_WIDTH, ASCENT)
    assert glyph_bounds(regular, 0x2588) == full_cell
    assert glyph_bounds(bold, 0x2588) == full_cell
    assert glyph_outline_bytes(regular, "zero") != glyph_outline_bytes(
        regular, "zero.ss01"
    )
    assert glyph_outline_bytes(bold, "zero") != glyph_outline_bytes(
        bold, "zero.ss01"
    )
    assert glyph_outline_bytes(regular, ord("A")) != glyph_outline_bytes(
        italic, ord("A")
    )
    assert glyph_outline_bytes(bold, ord("A")) != glyph_outline_bytes(
        bold_italic, ord("A")
    )
    for codepoint in (0x2500, 0x2502, 0x2588, 0xE0B0, 0xF015):
        assert glyph_outline_bytes(regular, codepoint) == glyph_outline_bytes(
            italic, codepoint
        )
        assert glyph_outline_bytes(bold, codepoint) == glyph_outline_bytes(
            bold_italic, codepoint
        )

    italic_counts = {
        "Italic": validate_italic_overhang(italic, text_by_style["Italic"]),
        "Bold Italic": validate_italic_overhang(
            bold_italic, text_by_style["Bold Italic"]
        ),
    }

    print("Goku TTC validation passed")
    print(f"  faces: {', '.join(faces)}")
    print(f"  version: {VERSION}; deterministic timestamp: {FONT_TIMESTAMP}")
    print(f"  typographic metrics: {expected_metrics}")
    print(f"  glyphs/cmap per face: {len(reference_order)}/{len(reference_cmap)}")
    print(f"  source-matched bold differences: {changed_bold}")
    print(f"  hinted text glyphs: {hint_counts}")
    print(f"  cell-contained ordinary icons: {icon_counts}")
    print(f"  bounded italic text glyphs: {italic_counts}")
    print(f"  monospaced advance: {CELL_WIDTH} (.null is zero-width)")
    print(f"  full-cell block: {full_cell}")
    print("  ss01 dotted zero is available in every face")
    print("  symbols/icons stay unhinted and upright in italic faces")


if __name__ == "__main__":
    main()
