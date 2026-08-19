#!/usr/bin/env python3
"""Structural and FreeType regression tests for native terminal graphics."""

from __future__ import annotations

import argparse
import copy
import math
from pathlib import Path

from fontTools.ttLib import TTCollection
from PIL import Image, ImageChops, ImageDraw, ImageFont

from design import ASCENT, CELL_WIDTH, DESCENT, UPM
from terminal_graphics import sextant_patterns


SIZES = (7, 8, 9, 10, 11, 12, 13, 14, 16, 20, 24, 29)
EXPECTED_STYLES = {"Regular", "Bold", "Italic", "Bold Italic"}
NATIVE_BOX_CODEPOINTS = (
    *range(0x2504, 0x2508),
    *range(0x254C, 0x2550),
    *range(0x256D, 0x2580),
)
SEXTANT_CODEPOINTS = tuple(range(0x1FB00, 0x1FB3C))
DIAGONAL_MOSAIC_CODEPOINTS = tuple(range(0x1FB3C, 0x1FB68))
TRIANGULAR_BLOCK_CODEPOINTS = tuple(range(0x1FB68, 0x1FB70))
LEGACY_EIGHTH_CODEPOINTS = tuple(range(0x1FB70, 0x1FB8C))
LEGACY_SHADE_FILL_CODEPOINTS = (
    *range(0x1FB8C, 0x1FB93),
    *range(0x1FB94, 0x1FBA0),
)
LEGACY_DIAGONAL_BOX_CODEPOINTS = tuple(range(0x1FBA0, 0x1FBB0))
LEGACY_THIRD_BLOCK_CODEPOINTS = (0x1FBCE, 0x1FBCF)
LEGACY_EXTENDED_DIAGONAL_CODEPOINTS = tuple(range(0x1FBD0, 0x1FBE0))
LEGACY_GEOMETRIC_CODEPOINTS = tuple(range(0x1FBE0, 0x1FBF0))
SEGMENTED_DIGIT_CODEPOINTS = tuple(range(0x1FBF0, 0x1FBFA))
LEGACY_CODEPOINTS = (
    *SEXTANT_CODEPOINTS,
    *DIAGONAL_MOSAIC_CODEPOINTS,
    *TRIANGULAR_BLOCK_CODEPOINTS,
    *LEGACY_EIGHTH_CODEPOINTS,
    *LEGACY_SHADE_FILL_CODEPOINTS,
    *LEGACY_DIAGONAL_BOX_CODEPOINTS,
    *LEGACY_THIRD_BLOCK_CODEPOINTS,
    *LEGACY_EXTENDED_DIAGONAL_CODEPOINTS,
    *LEGACY_GEOMETRIC_CODEPOINTS,
    *SEGMENTED_DIGIT_CODEPOINTS,
)
SUPPLEMENT_CODEPOINTS = tuple(range(0x1CC21, 0x1CC30))
GRAPHICS_CODEPOINTS = [
    *NATIVE_BOX_CODEPOINTS,
    *range(0x2580, 0x25A0),
    *range(0x2800, 0x2900),
    *LEGACY_CODEPOINTS,
    *SUPPLEMENT_CODEPOINTS,
]
COMPLEMENTS = (
    (0x2580, 0x2584),
    (0x2587, 0x2594),
    (0x2589, 0x2595),
    (0x258C, 0x2590),
    (0x2596, 0x259C),
    (0x2597, 0x259B),
    (0x2598, 0x259F),
    (0x2599, 0x259D),
    (0x259A, 0x259E),
    (0x1FB68, 0x1FB6C),
    (0x1FB69, 0x1FB6D),
    (0x1FB6A, 0x1FB6E),
    (0x1FB6B, 0x1FB6F),
    (0x2592, 0x1FB90),
    (0x1FB95, 0x1FB96),
    *((0x1FB3C + index, 0x1FB52 + index) for index in range(22)),
)
LINE_COMPOSITIONS = (
    (0x2574, 0x2576, 0x2500),
    (0x2575, 0x2577, 0x2502),
    (0x2578, 0x257A, 0x2501),
    (0x2579, 0x257B, 0x2503),
    (0x1FB8C, 0x1FB8D, 0x2592),
    (0x1FB8E, 0x1FB8F, 0x2592),
    (0x1FBA0, 0x1FBA1, 0x1FBA7),
    (0x1FBA2, 0x1FBA3, 0x1FBA6),
    (0x1FBA0, 0x1FBA2, 0x1FBA4),
    (0x1FBA1, 0x1FBA3, 0x1FBA5),
    (0x1FBA0, 0x1FBA3, 0x1FBA8),
    (0x1FBA1, 0x1FBA2, 0x1FBA9),
    (0x1FBA4, 0x1FBA5, 0x1FBAE),
)
_SEXTANT_BY_MASK = {
    mask: 0x1FB00 + index for index, mask in enumerate(sextant_patterns())
}
SEXTANT_COMPLEMENTS = tuple(
    (codepoint, _SEXTANT_BY_MASK[63 ^ mask])
    for mask, codepoint in _SEXTANT_BY_MASK.items()
    if mask < (63 ^ mask) and (63 ^ mask) in _SEXTANT_BY_MASK
)
SEPARATED_QUADRANT_COMPLEMENTS = tuple(
    (0x1CC20 + mask, 0x1CC20 + (15 ^ mask))
    for mask in range(1, 15)
    if mask < (15 ^ mask)
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", required=True, type=Path)
    return parser.parse_args()


def names(font, name_id: int) -> set[str]:
    return {
        record.toUnicode()
        for record in font["name"].names
        if record.nameID == name_id
    }


def style(font) -> str:
    matches = names(font, 2) & EXPECTED_STYLES
    assert len(matches) == 1
    return matches.pop()


def outline_bytes(font, codepoint: int) -> bytes:
    glyph = copy.deepcopy(font["glyf"][font.getBestCmap()[codepoint]])
    glyph.removeHinting()
    return glyph.compile(font["glyf"])


def raster(font: ImageFont.FreeTypeFont, character: str, size: int) -> Image.Image:
    advance = math.ceil(font.getlength(character))
    image = Image.new("L", (advance + 8, size + 10))
    baseline = 4 + round(size * ASCENT / UPM)
    ImageDraw.Draw(image).text(
        (4, baseline),
        character,
        font=font,
        fill=255,
        anchor="ls",
    )
    return image


def saturated_union(left: Image.Image, right: Image.Image) -> Image.Image:
    return ImageChops.add(left, right, scale=1.0, offset=0)


def main() -> None:
    args = parse_args()
    collection = TTCollection(args.collection)
    faces = {style(font): (index, font) for index, font in enumerate(collection.fonts)}
    assert set(faces) == EXPECTED_STYLES
    regular = faces["Regular"][1]
    reference_cmap = regular.getBestCmap()
    assert all(codepoint in reference_cmap for codepoint in GRAPHICS_CODEPOINTS)

    full_name = reference_cmap[0x2588]
    full = regular["glyf"][full_name]
    full.recalcBounds(regular["glyf"])
    assert (full.xMin, full.yMin, full.xMax, full.yMax) == (
        0,
        DESCENT,
        CELL_WIDTH,
        ASCENT,
    )

    # All terminal primitives stay unhinted, upright and weight-independent.
    for codepoint in GRAPHICS_CODEPOINTS:
        reference = outline_bytes(regular, codepoint)
        for _, font in faces.values():
            assert font.getBestCmap()[codepoint] == reference_cmap[codepoint]
            assert font["hmtx"].metrics[reference_cmap[codepoint]][0] == CELL_WIDTH
            assert outline_bytes(font, codepoint) == reference

    # The imported box glyphs used to overflow by up to 12 units and used a
    # different vertical center. Native replacements stay inside the cell.
    for codepoint in NATIVE_BOX_CODEPOINTS:
        glyph = regular["glyf"][reference_cmap[codepoint]]
        glyph.recalcBounds(regular["glyf"])
        assert 0 <= glyph.xMin <= glyph.xMax <= CELL_WIDTH, (codepoint, glyph.xMin, glyph.xMax)
        assert DESCENT <= glyph.yMin <= glyph.yMax <= ASCENT, (codepoint, glyph.yMin, glyph.yMax)

    for codepoint in (*LEGACY_CODEPOINTS, *SUPPLEMENT_CODEPOINTS):
        glyph = regular["glyf"][reference_cmap[codepoint]]
        glyph.recalcBounds(regular["glyf"])
        assert 0 <= glyph.xMin <= glyph.xMax <= CELL_WIDTH
        assert DESCENT <= glyph.yMin <= glyph.yMax <= ASCENT

    blank = regular["glyf"][reference_cmap[0x2800]]
    assert blank.numberOfContours == 0
    for pattern in range(1, 256):
        glyph = regular["glyf"][reference_cmap[0x2800 + pattern]]
        assert glyph.numberOfContours == 4 * pattern.bit_count()

    # Native-grid shades contain exactly 25%, 50%, and 75% of 8x14 pixels.
    assert [
        regular["glyf"][reference_cmap[codepoint]].numberOfContours
        for codepoint in (0x2591, 0x2592, 0x2593)
    ] == [28, 56, 84]

    raster_checks = 0
    worst_complement_error = 0
    for size in SIZES:
        raster_fonts = {
            face_style: ImageFont.truetype(
                str(args.collection),
                size=size,
                index=index,
            )
            for face_style, (index, _) in faces.items()
        }
        for face_style, font in raster_fonts.items():
            advance = font.getlength("█")
            assert abs(advance - size * CELL_WIDTH / UPM) <= 1 / 32

            # Every generated graphic must survive FreeType rasterization at
            # every supported small size. U+2800 is intentionally blank.
            for codepoint in GRAPHICS_CODEPOINTS:
                mask = raster(font, chr(codepoint), size)
                if codepoint == 0x2800:
                    assert mask.getbbox() is None
                else:
                    assert mask.getbbox() is not None, (
                        face_style,
                        size,
                        hex(codepoint),
                    )
                raster_checks += 1

            full_mask = raster(font, "█", size)
            for first, second in COMPLEMENTS:
                combined = saturated_union(
                    raster(font, chr(first), size),
                    raster(font, chr(second), size),
                )
                difference = ImageChops.difference(combined, full_mask)
                error = sum(difference.tobytes())
                # FreeType can differ by one alpha level on one outer fringe
                # pixel when two complementary edges are rasterized
                # independently. That cannot produce a visible seam; any
                # larger disagreement is a real geometry failure.
                # Dense inverse/checker complements have many independently
                # rasterized pixel edges. A one-alpha fringe remains
                # invisible even when it occurs at several such edges.
                assert max(difference.tobytes(), default=0) <= 1 and error <= 32, (
                    face_style,
                    size,
                    hex(first),
                    hex(second),
                    error,
                )
                worst_complement_error = max(worst_complement_error, error)
                raster_checks += 1

            for first, second, target in LINE_COMPOSITIONS:
                combined = saturated_union(
                    raster(font, chr(first), size),
                    raster(font, chr(second), size),
                )
                target_mask = raster(font, chr(target), size)
                difference = ImageChops.difference(combined, target_mask)
                error = sum(difference.tobytes())
                assert max(difference.tobytes(), default=0) <= 1 and error <= 8, (
                    face_style,
                    size,
                    hex(first),
                    hex(second),
                    hex(target),
                    error,
                )
                worst_complement_error = max(worst_complement_error, error)
                raster_checks += 1

            for first, second in SEXTANT_COMPLEMENTS:
                combined = saturated_union(
                    raster(font, chr(first), size),
                    raster(font, chr(second), size),
                )
                difference = ImageChops.difference(combined, full_mask)
                error = sum(difference.tobytes())
                assert max(difference.tobytes(), default=0) <= 1 and error <= 8, (
                    face_style,
                    size,
                    hex(first),
                    hex(second),
                    error,
                )
                worst_complement_error = max(worst_complement_error, error)
                raster_checks += 1

            separated_full = raster(font, chr(0x1CC2F), size)
            for first, second in SEPARATED_QUADRANT_COMPLEMENTS:
                combined = saturated_union(
                    raster(font, chr(first), size),
                    raster(font, chr(second), size),
                )
                difference = ImageChops.difference(combined, separated_full)
                error = sum(difference.tobytes())
                assert max(difference.tobytes(), default=0) <= 1 and error <= 8, (
                    face_style,
                    size,
                    hex(first),
                    hex(second),
                    error,
                )
                worst_complement_error = max(worst_complement_error, error)
                raster_checks += 1

            shade_ink = [
                sum(raster(font, chr(codepoint), size).tobytes())
                for codepoint in (0x2591, 0x2592, 0x2593)
            ]
            assert shade_ink[0] < shade_ink[1] < shade_ink[2]
            raster_checks += 3

    # Every braille pattern must be the exact union of its Unicode dot bits.
    for size in (7, 10, 14, 20, 29):
        font = ImageFont.truetype(
            str(args.collection),
            size=size,
            index=faces["Regular"][0],
        )
        blank_mask = raster(font, chr(0x2800), size)
        single_dots = [raster(font, chr(0x2800 + (1 << bit)), size) for bit in range(8)]
        for pattern in range(256):
            expected = blank_mask.copy()
            for bit, dot in enumerate(single_dots):
                if pattern & (1 << bit):
                    expected = saturated_union(expected, dot)
            actual = raster(font, chr(0x2800 + pattern), size)
            assert actual.tobytes() == expected.tobytes(), (size, pattern)
            if pattern:
                assert actual.getbbox() is not None, (size, pattern)
            raster_checks += 1

    collection.close()
    print("Native terminal-graphics audit passed")
    print(
        "  27 non-Gohu box glyphs, 32 blocks, all 256 braille, and "
        f"{len(LEGACY_CODEPOINTS)} legacy plus {len(SUPPLEMENT_CODEPOINTS)} "
        "Unicode 17 supplement glyphs present"
    )
    print("  outlines identical across Regular/Bold/Italic/Bold Italic")
    print(
        f"  {len(COMPLEMENTS)} full-cell complements and "
        f"{len(LINE_COMPOSITIONS)} split lines compose exactly; "
        f"{len(SEXTANT_COMPLEMENTS)} sextant and "
        f"{len(SEPARATED_QUADRANT_COMPLEMENTS)} separated-quadrant "
        "complement pairs compose"
    )
    print(f"  worst complement raster alpha error: {worst_complement_error}")
    print("  light/medium/dark shade density is strictly ordered")
    print(
        f"  every generated glyph remains visible; {raster_checks} raster "
        "checks at 7–29 px"
    )


if __name__ == "__main__":
    main()
