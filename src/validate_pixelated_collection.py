#!/usr/bin/env python3
"""Validate that a pixelated TTC is complete and strictly grid-aligned."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

from fontTools.ttLib import TTCollection, TTFont
from PIL import ImageFont

from pixelate_collection import (
    frozen_recording,
    grid_columns_for_advance,
    grid_boundaries as ordered_grid_boundaries,
    occupied_pixels,
    pixel_glyph,
)
from text_glyphs import text_glyph_names


DESCENDER_SAMPLE = "gyjpq"
WEIGHT_SAMPLE = "g y j p q Hamburgefonts 0123456789"
RASTER_SIZES = (*range(7, 15), 32)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--regular-bdf", required=True, type=Path)
    parser.add_argument("--bold-bdf", required=True, type=Path)
    parser.add_argument("--columns", required=True, type=int)
    parser.add_argument("--rows", required=True, type=int)
    return parser.parse_args()


def rounded_ratio(numerator: int, denominator: int) -> int:
    return (numerator + denominator // 2) // denominator


def grid_boundaries(start: int, end: int, count: int) -> set[int]:
    span = end - start
    return {
        start + rounded_ratio(index * span, count)
        for index in range(count + 1)
    }


def outline_names(font: TTFont) -> set[str]:
    glyf = font["glyf"]
    return {
        name
        for name in font.getGlyphOrder()
        if glyf[name].numberOfContours != 0
    }


def validate_face(
    source: TTFont,
    candidate: TTFont,
    face_index: int,
    columns: int,
    rows: int,
    bdf_path: Path,
) -> tuple[int, int, int]:
    assert source.getGlyphOrder() == candidate.getGlyphOrder(), (
        f"face {face_index}: glyph order changed"
    )
    assert source.getBestCmap() == candidate.getBestCmap(), (
        f"face {face_index}: cmap changed"
    )
    source_advances = {
        name: advance for name, (advance, _) in source["hmtx"].metrics.items()
    }
    candidate_advances = {
        name: advance for name, (advance, _) in candidate["hmtx"].metrics.items()
    }
    assert source_advances == candidate_advances, (
        f"face {face_index}: advance widths changed"
    )

    source_drawn = outline_names(source)
    candidate_drawn = outline_names(candidate)
    vanished = source_drawn - candidate_drawn
    assert not vanished, (
        f"face {face_index}: {len(vanished)} source outlines vanished; "
        f"sample={sorted(vanished)[:20]}"
    )

    glyf = candidate["glyf"]
    y_grid = grid_boundaries(
        candidate["hhea"].descent,
        candidate["hhea"].ascent,
        rows,
    )
    checked = 0
    contours = 0
    hinted_text = 0
    hinted_nontext: list[str] = []
    text_names = text_glyph_names(candidate, bdf_path)
    for name in sorted(candidate_drawn):
        glyph = glyf[name]
        assert not glyph.isComposite(), f"face {face_index} {name}: composite"
        glyph.expand(glyf)
        advance = candidate["hmtx"].metrics[name][0]
        glyph_columns = grid_columns_for_advance(advance, columns)
        x_grid = grid_boundaries(0, advance, glyph_columns)
        coordinates = glyph.coordinates
        assert all(x in x_grid and y in y_grid for x, y in coordinates), (
            f"face {face_index} {name}: coordinate is off-grid"
        )
        assert all(flag & 1 for flag in glyph.flags), (
            f"face {face_index} {name}: contains a curve point"
        )
        start = 0
        for end in glyph.endPtsOfContours:
            contour = coordinates[start : end + 1]
            assert len(contour) == 4, (
                f"face {face_index} {name}: non-rectangular contour"
            )
            for first, second in zip(contour, (*contour[1:], contour[0])):
                assert first[0] == second[0] or first[1] == second[1], (
                    f"face {face_index} {name}: diagonal segment"
                )
            contours += 1
            start = end + 1
        program = getattr(glyph, "program", None)
        if program is not None and program.getBytecode():
            if name in text_names:
                hinted_text += 1
            else:
                hinted_nontext.append(name)
        checked += 1
    assert not hinted_nontext, (
        f"face {face_index}: non-text glyphs contain hint programs; "
        f"sample={hinted_nontext[:20]}"
    )
    assert all(tag in candidate for tag in ("cvt ", "fpgm", "prep")), (
        f"face {face_index}: missing global TrueType hint tables"
    )
    assert hinted_text >= 125, (
        f"face {face_index}: insufficient freshly hinted text glyphs: "
        f"{hinted_text}"
    )

    rectangles = {}
    cmap = source.getBestCmap()
    ordered_y = ordered_grid_boundaries(
        source["hhea"].descent,
        source["hhea"].ascent,
        rows,
    )
    for character in DESCENDER_SAMPLE:
        name = cmap[ord(character)]
        advance = source["hmtx"].metrics[name][0]
        glyph_columns = grid_columns_for_advance(advance, columns)
        ordered_x = ordered_grid_boundaries(0, advance, glyph_columns)
        pixels = occupied_pixels(
            frozen_recording(source, name),
            ordered_x,
            ordered_y,
            0.5,
            rectangles,
        )
        expected = pixel_glyph(pixels, ordered_x, ordered_y)
        actual = copy.deepcopy(candidate["glyf"][name])
        actual.removeHinting()
        assert actual.compile(candidate["glyf"]) == expected.compile(
            candidate["glyf"]
        ), f"face {face_index}: {character} lost its neutral pixel silhouette"

    return checked, contours, hinted_text


def validate_weight_rasters(path: Path, collection: TTCollection) -> int:
    indices = {
        font["name"].getDebugName(17): index
        for index, font in enumerate(collection.fonts)
    }
    checks = 0
    for italic in (False, True):
        posture = "italic" if italic else "upright"
        for size in RASTER_SIZES:
            ink_by_weight: list[tuple[int, int]] = []
            for weight in range(100, 1000, 100):
                style = str(weight) + (" Italic" if italic else "")
                font = ImageFont.truetype(
                    str(path),
                    size=size,
                    index=indices[style],
                )
                ink = sum(bytes(font.getmask(WEIGHT_SAMPLE, mode="L")))
                ink_by_weight.append((weight, ink))
                checks += 1
            assert all(
                lighter[1] < heavier[1]
                for lighter, heavier in zip(ink_by_weight, ink_by_weight[1:])
            ), (
                f"weights are not visually ordered for {posture} at "
                f"{size}px: {ink_by_weight}"
            )
    return checks


def main() -> None:
    args = parse_args()
    source = TTCollection(args.source)
    candidate = TTCollection(args.candidate)
    assert len(source.fonts) == len(candidate.fonts), "face count changed"
    total_glyphs = 0
    total_contours = 0
    for face_index, (source_face, candidate_face) in enumerate(
        zip(source.fonts, candidate.fonts)
    ):
        weight = source_face["OS/2"].usWeightClass
        bdf_path = args.regular_bdf if weight <= 500 else args.bold_bdf
        checked, contours, hinted = validate_face(
            source_face,
            candidate_face,
            face_index,
            args.columns,
            args.rows,
            bdf_path,
        )
        total_glyphs += checked
        total_contours += contours
        print(
            f"  face {face_index:02}: {checked} non-empty grid glyphs, "
            f"{contours} rectangular runs, {hinted} hinted text glyphs"
        )
    raster_checks = validate_weight_rasters(args.candidate, candidate)
    source.close()
    candidate.close()
    print(
        f"Validated {len(source.fonts)} faces, {total_glyphs} non-empty glyphs, "
        f"{total_contours} grid-aligned rectangular runs, and "
        f"{raster_checks} ordered weight rasters"
    )


if __name__ == "__main__":
    main()
