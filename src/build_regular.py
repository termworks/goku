#!/usr/bin/env python3
"""Build the scalable Goku source face from Gohu's regular BDF."""

from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.agl import UV2AGL
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib.removeOverlaps import removeOverlaps

from bdf import load_bdf
from build_bdf_face import make_outline
from design import (
    ASCENT,
    CAP_HEIGHT,
    CELL_WIDTH,
    DESCENT,
    FAMILY,
    PIXEL_SIZE,
    POSTSCRIPT_STEM,
    SOURCE_CELL_HEIGHT,
    SOURCE_CELL_WIDTH,
    UPM,
    VERSION,
    X_HEIGHT,
    scale_grid,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def glyph_name(codepoint: int) -> str:
    return UV2AGL.get(
        codepoint,
        f"uni{codepoint:04X}" if codepoint <= 0xFFFF else f"u{codepoint:05X}",
    )


def main() -> None:
    args = parse_args()
    bdf = load_bdf(args.bdf)
    if bdf.bounding_box != (SOURCE_CELL_WIDTH, SOURCE_CELL_HEIGHT, 0, -3):
        raise ValueError(
            f"expected Gohu's 8x14 cell at 0/-3, got {bdf.bounding_box}"
        )

    order = [".notdef"]
    cmap: dict[int, str] = {}
    glyphs = {".notdef": TTGlyphPen(None).glyph()}
    metrics = {".notdef": (CELL_WIDTH, 0)}

    for source in bdf.glyphs:
        name = glyph_name(source.encoding)
        if name in glyphs:
            raise ValueError(f"duplicate glyph name {name}")
        order.append(name)
        cmap[source.encoding] = name
        glyphs[name] = make_outline(
            source,
            source.dwidth,
            SOURCE_CELL_HEIGHT,
            CELL_WIDTH,
            UPM,
        )
        left = min((x for x, _ in source.pixels), default=0)
        metrics[name] = (CELL_WIDTH, scale_grid(left, source.dwidth, CELL_WIDTH))

    postscript = f"{POSTSCRIPT_STEM}-Regular"
    builder = FontBuilder(UPM, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(
        ascent=ASCENT,
        descent=DESCENT,
        lineGap=0,
        caretSlopeRise=1,
        caretSlopeRun=0,
    )
    builder.setupNameTable(
        {
            "familyName": FAMILY,
            "styleName": "Regular",
            "uniqueFontIdentifier": f"{VERSION};GOKU;{postscript}",
            "fullName": f"{FAMILY} Regular",
            "psName": postscript,
            "version": f"Version {VERSION}",
        }
    )
    builder.setupOS2(
        sTypoAscender=ASCENT,
        sTypoDescender=DESCENT,
        sTypoLineGap=0,
        usWinAscent=ASCENT,
        usWinDescent=-DESCENT,
        usWeightClass=400,
        fsSelection=(1 << 6) | (1 << 7) | (1 << 8),
        sxHeight=X_HEIGHT,
        sCapHeight=CAP_HEIGHT,
    )
    # USE_TYPO_METRICS and WWS are defined for OS/2 version 4 and later.
    builder.font["OS/2"].version = 4
    builder.font["OS/2"].panose.bProportion = 9
    builder.setupPost(
        isFixedPitch=1,
        italicAngle=0,
        underlinePosition=-PIXEL_SIZE,
        underlineThickness=PIXEL_SIZE,
    )
    builder.setupMaxp()
    builder.font.recalcBBoxes = True
    builder.font.recalcTimestamp = False
    removeOverlaps(
        builder.font,
        glyphNames=[name for name in order if name != ".notdef"],
        removeHinting=True,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    builder.save(args.output)
    print(f"Built Goku source: {args.output}")
    print(
        f"Vectorized {len(cmap)} glyphs on the {UPM}/{CELL_WIDTH} grid; "
        f"vertical metrics {ASCENT}/{DESCENT}"
    )


if __name__ == "__main__":
    main()
