#!/usr/bin/env python3
"""Restore one Goku weight from its handcrafted Gohu 8x14 BDF.

The Nerd-patched Regular is cloned so coverage and symbols remain intact. Every
codepoint in the selected BDF is then restored as exact grid-aligned vector
rectangles. This keeps Regular and Bold equally faithful to their source and
prevents the patcher from changing box-drawing geometry.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.removeOverlaps import removeOverlaps

from bdf import BDFGlyph, load_bdf
from design import (
    FAMILY,
    POSTSCRIPT_STEM,
    SOURCE_CELL_HEIGHT,
    SOURCE_CELL_WIDTH,
    VERSION,
    scale_grid,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--bdf", required=True, type=Path)
    parser.add_argument("--style", required=True, choices=("Regular", "Bold"))
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def horizontal_runs(glyph: BDFGlyph) -> list[tuple[int, int, int]]:
    """Return (start_x, end_x, y) runs, reducing outline complexity."""
    rows: dict[int, list[int]] = {}
    for x, y in glyph.pixels:
        rows.setdefault(y, []).append(x)

    runs: list[tuple[int, int, int]] = []
    for y, columns in sorted(rows.items()):
        columns.sort()
        start = previous = columns[0]
        for column in columns[1:]:
            if column != previous + 1:
                runs.append((start, previous + 1, y))
                start = column
            previous = column
        runs.append((start, previous + 1, y))
    return runs


def diagonal_contacts(glyph: BDFGlyph) -> set[tuple[int, int]]:
    """Find corners where two filled pixels meet without an edge."""
    pixels = glyph.pixels
    contacts: set[tuple[int, int]] = set()
    for x, y in pixels:
        if (
            (x + 1, y + 1) in pixels
            and (x + 1, y) not in pixels
            and (x, y + 1) not in pixels
        ):
            contacts.add((x + 1, y + 1))
        if (
            (x + 1, y - 1) in pixels
            and (x + 1, y) not in pixels
            and (x, y - 1) not in pixels
        ):
            contacts.add((x + 1, y))
    return contacts


def make_outline(
    glyph: BDFGlyph,
    cell_width: int,
    cell_height: int,
    advance_width: int,
    units_per_em: int,
):
    pen = TTGlyphPen(None)
    for start_x, end_x, y in horizontal_runs(glyph):
        x0 = scale_grid(start_x, cell_width, advance_width)
        x1 = scale_grid(end_x, cell_width, advance_width)
        y0 = scale_grid(y, cell_height, units_per_em)
        y1 = scale_grid(y + 1, cell_height, units_per_em)

        pen.moveTo((x0, y0))
        pen.lineTo((x0, y1))
        pen.lineTo((x1, y1))
        pen.lineTo((x1, y0))
        pen.closePath()

    # A 2-unit bridge repairs corner-only contacts without changing a visible
    # source pixel at the intended raster sizes.
    bridge_radius = 1
    for x, y in diagonal_contacts(glyph):
        center_x = scale_grid(x, cell_width, advance_width)
        center_y = scale_grid(y, cell_height, units_per_em)
        x0, x1 = center_x - bridge_radius, center_x + bridge_radius
        y0, y1 = center_y - bridge_radius, center_y + bridge_radius
        pen.moveTo((x0, y0))
        pen.lineTo((x0, y1))
        pen.lineTo((x1, y1))
        pen.lineTo((x1, y0))
        pen.closePath()
    return pen.glyph()


def set_name(font: TTFont, name_id: int, value: str) -> None:
    name_table = font["name"]
    destinations = {
        (record.platformID, record.platEncID, record.langID)
        for record in name_table.names
        if record.nameID == name_id
    } or {(3, 1, 0x409)}
    for platform_id, encoding_id, language_id in destinations:
        name_table.setName(value, name_id, platform_id, encoding_id, language_id)


def update_metadata(font: TTFont, style: str) -> None:
    bold = style == "Bold"
    postscript = f"{POSTSCRIPT_STEM}-{style}"
    for name_id, value in {
        1: FAMILY,
        2: style,
        3: f"{VERSION};GOKU;{postscript}",
        4: f"{FAMILY} {style}",
        6: postscript,
        16: FAMILY,
        17: style,
    }.items():
        set_name(font, name_id, value)

    os2 = font["OS/2"]
    os2.usWeightClass = 700 if bold else 400
    os2.fsSelection &= ~((1 << 0) | (1 << 5) | (1 << 6) | (1 << 9))
    os2.fsSelection |= (1 << 5) if bold else (1 << 6)
    font["head"].macStyle = 1 if bold else 0
    font["post"].italicAngle = 0
    if "DSIG" in font:
        del font["DSIG"]


def add_unicode_alias(font: TTFont, codepoint: int, glyph_name: str) -> None:
    added = False
    for subtable in font["cmap"].tables:
        if not subtable.isUnicode():
            continue
        if subtable.format == 4 and codepoint > 0xFFFF:
            continue
        subtable.cmap[codepoint] = glyph_name
        added = True
    if not added:
        raise ValueError(f"no cmap subtable can encode U+{codepoint:04X}")


def add_dotted_zero(font: TTFont, source: BDFGlyph, bold: bool) -> str:
    """Add an opt-in dotted-zero alternate as stylistic set ``ss01``."""
    if bold:
        slash = {(5, 6), (4, 5), (5, 5), (3, 4), (4, 4), (3, 3)}
        dot = {(3, 3), (4, 3), (3, 4), (4, 4)}
    else:
        slash = {(5, 6), (4, 5), (3, 4), (2, 3)}
        dot = {(3, 4)}
    alternate = replace(
        source,
        name="zero.ss01",
        encoding=-1,
        pixels=frozenset((source.pixels - slash) | dot),
    )
    name = alternate.name
    if name in font.getGlyphOrder():
        raise ValueError(f"alternate glyph already exists: {name}")

    font.setGlyphOrder([*font.getGlyphOrder(), name])
    font["glyf"][name] = make_outline(
        alternate,
        alternate.dwidth,
        SOURCE_CELL_HEIGHT,
        font["hmtx"].metrics["zero"][0],
        font["head"].unitsPerEm,
    )
    leftmost = min(x for x, _ in alternate.pixels)
    advance = font["hmtx"].metrics["zero"][0]
    font["hmtx"].metrics[name] = (
        advance,
        scale_grid(leftmost, alternate.dwidth, advance),
    )
    addOpenTypeFeaturesFromString(
        font,
        "feature ss01 { sub zero by zero.ss01; } ss01;",
    )
    return name


def main() -> None:
    args = parse_args()
    bdf = load_bdf(args.bdf)
    if bdf.bounding_box != (SOURCE_CELL_WIDTH, SOURCE_CELL_HEIGHT, 0, -3):
        raise ValueError(
            f"expected Gohu's 8x14 cell at 0/-3, got {bdf.bounding_box}"
        )

    font = TTFont(args.base, recalcTimestamp=False)
    if "glyf" not in font:
        raise ValueError("base must be a TrueType glyf outline font")
    cmap = font.getBestCmap()
    units_per_em = font["head"].unitsPerEm
    metrics = font["hmtx"].metrics
    replaced: list[str] = []
    missing: list[int] = []
    aliases: list[int] = []
    seen: dict[str, frozenset[tuple[int, int]]] = {}

    for bdf_glyph in bdf.glyphs:
        glyph_name = cmap.get(bdf_glyph.encoding)
        if glyph_name is None:
            if not bdf_glyph.pixels and 0x20 in cmap:
                glyph_name = cmap[0x20]
                add_unicode_alias(font, bdf_glyph.encoding, glyph_name)
                aliases.append(bdf_glyph.encoding)
            else:
                missing.append(bdf_glyph.encoding)
                continue
        previous = seen.get(glyph_name)
        if previous is not None and previous != bdf_glyph.pixels:
            raise ValueError(f"conflicting BDF bitmaps map to {glyph_name}")
        seen[glyph_name] = bdf_glyph.pixels

        advance_width = metrics[glyph_name][0]
        font["glyf"][glyph_name] = make_outline(
            bdf_glyph,
            bdf_glyph.dwidth,
            SOURCE_CELL_HEIGHT,
            advance_width,
            units_per_em,
        )
        leftmost = min((x for x, _ in bdf_glyph.pixels), default=0)
        metrics[glyph_name] = (
            advance_width,
            scale_grid(leftmost, bdf_glyph.dwidth, advance_width),
        )
        replaced.append(glyph_name)

    if missing:
        codepoints = ", ".join(f"U+{value:04X}" for value in missing[:16])
        raise ValueError(
            f"base font lacks {len(missing)} BDF codepoints: {codepoints}"
        )

    zero = next(glyph for glyph in bdf.glyphs if glyph.encoding == ord("0"))
    replaced.append(add_dotted_zero(font, zero, args.style == "Bold"))
    removeOverlaps(font, glyphNames=sorted(set(replaced)), removeHinting=True)
    update_metadata(font, args.style)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    font.save(args.output, reorderTables=False)
    print(f"Built {args.style}: {args.output}")
    print(f"Restored {len(set(replaced))} glyphs from {len(bdf.glyphs)} BDF entries")
    print(f"Added {len(aliases)} blank Unicode-space aliases")
    print("Added dotted-zero alternate: ss01")
    print(f"Preserved {len(font.getGlyphOrder())} total glyphs and {units_per_em} UPM")


if __name__ == "__main__":
    main()
