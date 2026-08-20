#!/usr/bin/env python3
"""Quantize every outline in a TrueType collection onto a pixel grid.

For each virtual pixel, the source outline is intersected with that cell.  The
output contains a full rectangular pixel only when the geometric intersection
is greater than the configured coverage threshold.  This deliberately applies
to text, symbols, Nerd Font icons, alternates, and .notdef alike.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path

import pathops
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTCollection, TTFont

from design import CELL_WIDTH
from font_variants import is_private_use


# Experimental weight-aware thresholds are disabled by default. A common
# cutoff is the only terminal-safe default: stronger cutoffs can erase terminal
# rows from descenders, while softer cutoffs can overfill counters at small
# sizes. Symbols and icons must also retain one consistent design at every
# weight.
WEIGHT_THRESHOLD_OFFSETS = {
    100: 0.00,
    200: 0.00,
    300: 0.00,
    400: 0.00,
    500: -0.04,
    600: -0.08,
    700: -0.12,
    800: -0.16,
    900: -0.20,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--columns", type=int, default=20)
    parser.add_argument("--rows", type=int, default=35)
    parser.add_argument(
        "--icon-columns",
        type=int,
        default=8,
        help="coarse horizontal grid for private-use Nerd Font icons",
    )
    parser.add_argument(
        "--icon-rows",
        type=int,
        default=14,
        help="coarse vertical grid for private-use Nerd Font icons",
    )
    parser.add_argument(
        "--icon-threshold",
        type=float,
        default=0.25,
        help="coverage cutoff for coarse private-use icon pixels",
    )
    parser.add_argument(
        "--icon-fallback-threshold",
        type=float,
        default=0.05,
        help="lower cutoff used only when the normal coarse icon pass is empty",
    )
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument(
        "--fallback-threshold",
        type=float,
        default=0.05,
        help="lower cutoff used only when a non-icon source outline vanishes",
    )
    parser.add_argument(
        "--weight-contrast",
        type=float,
        default=0.0,
        help=(
            "strength of the numeric-weight threshold curve; 0 disables it "
            "and 1 uses the designed 100-900 progression"
        ),
    )
    parser.add_argument(
        "--family",
        help="optional prototype family name; omit to preserve source names",
    )
    parser.add_argument(
        "--allow-vanished",
        action="store_true",
        help="permit source outlines with no cell above the threshold",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if min(args.columns, args.rows, args.icon_columns, args.icon_rows) <= 0:
        parser.error("all grid dimensions must be positive")
    if not 0 <= args.threshold <= 1:
        parser.error("--threshold must be between 0 and 1")
    if not 0 <= args.fallback_threshold <= args.threshold:
        parser.error("--fallback-threshold must be between 0 and --threshold")
    if not 0 <= args.icon_threshold <= 1:
        parser.error("--icon-threshold must be between 0 and 1")
    if not 0 <= args.icon_fallback_threshold <= args.icon_threshold:
        parser.error(
            "--icon-fallback-threshold must be between 0 and --icon-threshold"
        )
    if not 0 <= args.weight_contrast <= 2:
        parser.error("--weight-contrast must be between 0 and 2")
    if args.source.resolve() == args.output.resolve():
        parser.error("--source and --output must be different files")
    return args


def rounded_ratio(numerator: int, denominator: int) -> int:
    """Round a non-negative ratio without ties-to-even behavior."""
    return (numerator + denominator // 2) // denominator


def grid_boundaries(start: int, end: int, count: int) -> tuple[int, ...]:
    span = end - start
    return tuple(start + rounded_ratio(index * span, count) for index in range(count + 1))


def grid_columns_for_advance(advance: int, columns_per_cell: int) -> int:
    """Scale the horizontal grid for any glyph spanning multiple cells."""
    return max(1, rounded_ratio(columns_per_cell * advance, CELL_WIDTH))


def rectangle_path(x0: int, y0: int, x1: int, y1: int) -> pathops.Path:
    path = pathops.Path()
    pen = path.getPen()
    pen.moveTo((x0, y0))
    pen.lineTo((x0, y1))
    pen.lineTo((x1, y1))
    pen.lineTo((x1, y0))
    pen.closePath()
    return path


def frozen_recording(
    font: TTFont,
    glyph_name: str,
) -> tuple[tuple[str, tuple[object, ...]], ...]:
    glyph_set = font.getGlyphSet()
    pen = DecomposingRecordingPen(glyph_set)
    glyph_set[glyph_name].draw(pen)
    return tuple((operator, tuple(operands)) for operator, operands in pen.value)


def is_italic(font: TTFont) -> bool:
    return bool(font["OS/2"].fsSelection & 1)


def weight_sensitive_glyphs(fonts: list[TTFont]) -> frozenset[str]:
    """Find glyphs whose upright outlines really change with font weight."""
    upright = sorted(
        (font for font in fonts if not is_italic(font)),
        key=lambda font: font["OS/2"].usWeightClass,
    )
    if len(upright) < 2:
        return frozenset()
    lightest = upright[0]
    heaviest = upright[-1]
    light_order = lightest.getGlyphOrder()
    heavy_order = heaviest.getGlyphOrder()
    if light_order != heavy_order:
        raise ValueError("weight faces do not share one glyph order")
    return frozenset(
        glyph_name
        for glyph_name in light_order
        if frozen_recording(lightest, glyph_name)
        != frozen_recording(heaviest, glyph_name)
    )


def private_use_glyphs(font: TTFont) -> frozenset[str]:
    """Return every glyph encoded in a Unicode private-use area.

    Nerd Fonts places its patched icon sets and Powerline symbols in these
    ranges. They use the separately configurable icon grid and coverage cutoff
    rather than the text defaults.
    """
    return frozenset(
        glyph_name
        for codepoint, glyph_name in font.getBestCmap().items()
        if is_private_use(codepoint)
    )


def threshold_for_weight(
    base_threshold: float,
    weight: int,
    contrast: float,
) -> float:
    offset = WEIGHT_THRESHOLD_OFFSETS.get(weight, 0.0) * contrast
    # Retain a non-degenerate coverage test even for experimental contrast
    # values, where the extrapolated curve could otherwise reach 0 or 1.
    return min(0.95, max(0.05, base_threshold + offset))


def recording_path(
    recording: tuple[tuple[str, tuple[object, ...]], ...],
) -> pathops.Path:
    path = pathops.Path()
    pen = path.getPen()
    for operator, operands in recording:
        getattr(pen, operator)(*operands)
    return pathops.simplify(path)


def occupied_pixels(
    recording: tuple[tuple[str, tuple[object, ...]], ...],
    x_boundaries: tuple[int, ...],
    y_boundaries: tuple[int, ...],
    threshold: float,
    rectangles: dict[tuple[int, int, int, int], pathops.Path],
) -> frozenset[tuple[int, int]]:
    outline = recording_path(recording)
    if not outline.verbs:
        return frozenset()
    left, bottom, right, top = outline.bounds
    pixels: set[tuple[int, int]] = set()
    for row, (y0, y1) in enumerate(zip(y_boundaries, y_boundaries[1:])):
        if y1 <= bottom or y0 >= top:
            continue
        for column, (x0, x1) in enumerate(zip(x_boundaries, x_boundaries[1:])):
            if x1 <= left or x0 >= right:
                continue
            box = (x0, y0, x1, y1)
            cell = rectangles.get(box)
            if cell is None:
                cell = rectangle_path(*box)
                rectangles[box] = cell
            intersection = pathops.op(outline, cell, pathops.PathOp.INTERSECTION)
            cell_area = (x1 - x0) * (y1 - y0)
            if abs(intersection.area) > threshold * cell_area:
                pixels.add((column, row))
    return frozenset(pixels)


def filled_rectangles(
    pixels: Iterable[tuple[int, int]],
) -> list[tuple[int, int, int, int]]:
    """Merge identical horizontal runs through adjacent grid rows."""
    rows: dict[int, list[int]] = {}
    for column, row in pixels:
        rows.setdefault(row, []).append(column)
    runs_by_row: dict[int, set[tuple[int, int]]] = {}
    for row, columns in sorted(rows.items()):
        columns.sort()
        start = previous = columns[0]
        runs: set[tuple[int, int]] = set()
        for column in columns[1:]:
            if column != previous + 1:
                runs.add((start, previous + 1))
                start = column
            previous = column
        runs.add((start, previous + 1))
        runs_by_row[row] = runs

    rectangles: list[tuple[int, int, int, int]] = []
    active: dict[tuple[int, int], int] = {}
    last_row = max(rows, default=-1)
    for row in range(last_row + 2):
        current = runs_by_row.get(row, set())
        for run in sorted(active.keys() - current):
            rectangles.append((*run, active.pop(run), row))
        for run in sorted(current - active.keys()):
            active[run] = row
    return rectangles


def pixel_glyph(
    pixels: frozenset[tuple[int, int]],
    x_boundaries: tuple[int, ...],
    y_boundaries: tuple[int, ...],
):
    pen = TTGlyphPen(None)
    for start, end, first_row, end_row in filled_rectangles(pixels):
        x0 = x_boundaries[start]
        x1 = x_boundaries[end]
        y0 = y_boundaries[first_row]
        y1 = y_boundaries[end_row]
        pen.moveTo((x0, y0))
        pen.lineTo((x0, y1))
        pen.lineTo((x1, y1))
        pen.lineTo((x1, y0))
        pen.closePath()
    return pen.glyph()


def set_name(font: TTFont, name_id: int, value: str) -> None:
    table = font["name"]
    destinations = {
        (record.platformID, record.platEncID, record.langID)
        for record in table.names
        if record.nameID == name_id
    } or {(3, 1, 0x409)}
    for platform_id, encoding_id, language_id in destinations:
        table.setName(value, name_id, platform_id, encoding_id, language_id)


def rename_face(font: TTFont, family: str) -> None:
    style = font["name"].getDebugName(17) or font["name"].getDebugName(2) or "Regular"
    postscript_family = "".join(character for character in family if character.isalnum())
    postscript_style = "".join(character for character in style if character.isalnum())
    postscript = f"{postscript_family}-{postscript_style}"
    version = font["name"].getDebugName(5) or "Version 1.000"
    for name_id, value in {
        1: family,
        3: f"{version};PIXEL;{postscript}",
        4: f"{family} {style}",
        6: postscript,
        16: family,
        17: style,
    }.items():
        set_name(font, name_id, value)


def clean_outline_tables(font: TTFont) -> None:
    # These optional tables cache or control the original outlines and become
    # stale after every glyph has been replaced.
    for tag in ("cvt ", "fpgm", "prep", "hdmx", "LTSH", "VDMX"):
        if tag in font:
            del font[tag]
    font.recalcBBoxes = True
    font.recalcTimestamp = False


def pixelate_face(
    font: TTFont,
    face_index: int,
    columns: int,
    rows: int,
    icon_columns: int,
    icon_rows: int,
    icon_threshold: float,
    icon_fallback_threshold: float,
    threshold: float,
    fallback_threshold: float,
    weight_contrast: float,
    weight_sensitive: frozenset[str],
    cache: dict[tuple[object, ...], frozenset[tuple[int, int]]],
    rectangles: dict[tuple[int, int, int, int], pathops.Path],
) -> dict[str, object]:
    if "glyf" not in font:
        raise ValueError(f"face {face_index} is not a TrueType glyf font")
    ascent = font["hhea"].ascent
    descent = font["hhea"].descent
    if ascent <= descent:
        raise ValueError(f"face {face_index} has invalid vertical metrics")
    text_y_boundaries = grid_boundaries(descent, ascent, rows)
    icon_y_boundaries = grid_boundaries(descent, ascent, icon_rows)
    icon_names = private_use_glyphs(font)
    glyf = font["glyf"]
    metrics = font["hmtx"].metrics
    processed = 0
    source_nonempty = 0
    vanished: list[str] = []
    total_pixels = 0
    cache_hits = 0
    contrast_fallbacks = 0
    icon_fallbacks = 0
    preservation_fallbacks = 0
    glyph_count = len(font.getGlyphOrder())
    weight = font["OS/2"].usWeightClass
    text_threshold = threshold_for_weight(threshold, weight, weight_contrast)

    for glyph_name in font.getGlyphOrder():
        advance, _ = metrics[glyph_name]
        source = glyf[glyph_name]
        if source.numberOfContours == 0 or advance <= 0:
            source.removeHinting()
            metrics[glyph_name] = (advance, 0)
            continue
        source_nonempty += 1
        is_icon = glyph_name in icon_names
        active_columns = icon_columns if is_icon else columns
        y_boundaries = icon_y_boundaries if is_icon else text_y_boundaries
        glyph_columns = grid_columns_for_advance(advance, active_columns)
        x_boundaries = grid_boundaries(0, advance, glyph_columns)
        recording = frozen_recording(font, glyph_name)
        neutral_threshold = icon_threshold if is_icon else threshold
        glyph_threshold = (
            text_threshold
            if not is_icon and glyph_name in weight_sensitive
            else neutral_threshold
        )
        key = (x_boundaries, y_boundaries, glyph_threshold, recording)
        pixels = cache.get(key)
        if pixels is None:
            try:
                pixels = occupied_pixels(
                    recording,
                    x_boundaries,
                    y_boundaries,
                    glyph_threshold,
                    rectangles,
                )
            except pathops.PathOpsError as error:
                raise ValueError(
                    f"could not pixelate face {face_index} glyph {glyph_name}"
                ) from error
            cache[key] = pixels
        else:
            cache_hits += 1
        if not pixels and is_icon and icon_fallback_threshold < icon_threshold:
            fallback_key = (
                x_boundaries,
                y_boundaries,
                icon_fallback_threshold,
                recording,
            )
            pixels = cache.get(fallback_key)
            if pixels is None:
                try:
                    pixels = occupied_pixels(
                        recording,
                        x_boundaries,
                        y_boundaries,
                        icon_fallback_threshold,
                        rectangles,
                    )
                except pathops.PathOpsError as error:
                    raise ValueError(
                        f"could not preserve coarse icon in face "
                        f"{face_index} glyph {glyph_name}"
                    ) from error
                cache[fallback_key] = pixels
            else:
                cache_hits += 1
            if pixels:
                icon_fallbacks += 1
        if not pixels and glyph_threshold != neutral_threshold:
            # A stronger light-weight cutoff must never erase a valid source
            # glyph. Fall back only this outline to the neutral cutoff.
            fallback_key = (
                x_boundaries,
                y_boundaries,
                neutral_threshold,
                recording,
            )
            pixels = cache.get(fallback_key)
            if pixels is None:
                try:
                    pixels = occupied_pixels(
                        recording,
                        x_boundaries,
                        y_boundaries,
                        neutral_threshold,
                        rectangles,
                    )
                except pathops.PathOpsError as error:
                    raise ValueError(
                        f"could not pixelate face {face_index} glyph "
                        f"{glyph_name} at the fallback threshold"
                    ) from error
                cache[fallback_key] = pixels
            else:
                cache_hits += 1
            if pixels:
                contrast_fallbacks += 1
        if (
            not pixels
            and not is_icon
            and fallback_threshold < neutral_threshold
        ):
            fallback_key = (
                x_boundaries,
                y_boundaries,
                fallback_threshold,
                recording,
            )
            pixels = cache.get(fallback_key)
            if pixels is None:
                try:
                    pixels = occupied_pixels(
                        recording,
                        x_boundaries,
                        y_boundaries,
                        fallback_threshold,
                        rectangles,
                    )
                except pathops.PathOpsError as error:
                    raise ValueError(
                        f"could not preserve face {face_index} glyph "
                        f"{glyph_name} at the fallback threshold"
                    ) from error
                cache[fallback_key] = pixels
            else:
                cache_hits += 1
            if pixels:
                preservation_fallbacks += 1
        target = pixel_glyph(pixels, x_boundaries, y_boundaries)
        glyf[glyph_name] = target
        if pixels:
            target.recalcBounds(glyf)
            metrics[glyph_name] = (advance, target.xMin)
        else:
            metrics[glyph_name] = (advance, 0)
            vanished.append(glyph_name)
        total_pixels += len(pixels)
        processed += 1
        if processed % 500 == 0:
            print(
                f"  face {face_index:02}: {processed}/{glyph_count} drawable glyphs",
                flush=True,
            )

    clean_outline_tables(font)
    return {
        "face": face_index,
        "style": font["name"].getDebugName(17) or font["name"].getDebugName(2),
        "glyphs": glyph_count,
        "source_nonempty": source_nonempty,
        "pixelated": processed,
        "occupied_pixels": total_pixels,
        "cache_hits": cache_hits,
        "contrast_fallbacks": contrast_fallbacks,
        "icon_fallbacks": icon_fallbacks,
        "preservation_fallbacks": preservation_fallbacks,
        "vanished_count": len(vanished),
        "vanished_sample": vanished[:40],
        "x_grid": columns,
        "y_grid": rows,
        "icon_glyphs": len(icon_names),
        "icon_x_grid": icon_columns,
        "icon_y_grid": icon_rows,
        "icon_threshold": icon_threshold,
        "icon_fallback_threshold": icon_fallback_threshold,
        "base_threshold": threshold,
        "fallback_threshold": fallback_threshold,
        "weight_threshold": text_threshold,
        "ascent": ascent,
        "descent": descent,
    }


def main() -> None:
    args = parse_args()
    collection = TTCollection(args.source)
    weight_sensitive = weight_sensitive_glyphs(collection.fonts)
    print(
        f"Applying numeric-weight contrast to {len(weight_sensitive)} "
        "weight-sensitive glyphs; keeping all other glyphs weight-stable",
        flush=True,
    )
    cache: dict[tuple[object, ...], frozenset[tuple[int, int]]] = {}
    rectangles: dict[tuple[int, int, int, int], pathops.Path] = {}
    reports: list[dict[str, object]] = []
    for face_index, font in enumerate(collection.fonts):
        print(
            f"Pixelating face {face_index + 1}/{len(collection.fonts)}: "
            f"{font['name'].getDebugName(17) or font['name'].getDebugName(2)}",
            flush=True,
        )
        reports.append(
            pixelate_face(
                font,
                face_index,
                args.columns,
                args.rows,
                args.icon_columns,
                args.icon_rows,
                args.icon_threshold,
                args.icon_fallback_threshold,
                args.threshold,
                args.fallback_threshold,
                args.weight_contrast,
                weight_sensitive,
                cache,
                rectangles,
            )
        )
        if args.family:
            rename_face(font, args.family)

    vanished = [
        (face["style"], face["vanished_count"], face["vanished_sample"])
        for face in reports
        if face["vanished_count"]
    ]
    if vanished and not args.allow_vanished:
        raise ValueError(
            "pixel grid erased source outlines; choose a finer grid or pass "
            f"--allow-vanished for experimentation: {vanished}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    collection.save(args.output, shareTables=True)
    collection.close()
    report = {
        "source": str(args.source),
        "output": str(args.output),
        "columns": args.columns,
        "rows": args.rows,
        "icon_columns": args.icon_columns,
        "icon_rows": args.icon_rows,
        "icon_threshold": args.icon_threshold,
        "icon_fallback_threshold": args.icon_fallback_threshold,
        "threshold": args.threshold,
        "fallback_threshold": args.fallback_threshold,
        "weight_contrast": args.weight_contrast,
        "weight_sensitive_glyphs": len(weight_sensitive),
        "faces": reports,
        "unique_outline_grids": len(cache),
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
