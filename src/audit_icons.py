#!/usr/bin/env python3
"""Create a deterministic geometry and raster inventory of Goku's PUA icons."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from fontTools.pens.momentsPen import MomentsPen
from fontTools.ttLib import TTCollection, TTFont
from fontTools.ttLib.removeOverlaps import _simplify, skPathFromGlyph
from PIL import ImageFont

from bdf import load_bdf
from design import ASCENT, CELL_WIDTH, DESCENT, UPM
from font_variants import is_powerline, is_private_use


DEFAULT_SIZES = (10, 14, 20)

# Destination ranges used by the pinned Nerd Fonts 3.4.0 patcher. The patcher
# relocates several source fonts; these are the resulting Goku codepoints.
# More-specific overlaps must precede broader ranges.
SOURCE_RANGES = (
    ("Pomicons", 0xE000, 0xE00A),
    ("Font Awesome Extension", 0xE200, 0xE2A9),
    ("Weather Icons", 0xE300, 0xE3EB),
    ("Seti-UI + Custom", 0xE5FA, 0xE6FF),
    ("Devicons", 0xE700, 0xE8EF),
    ("Codicons", 0xEA60, 0xEC1E),
    ("Progress Indicators", 0xEE00, 0xEE0B),
    ("Font Awesome", 0xED00, 0xF2FF),
    ("Font Logos", 0xF300, 0xF381),
    ("Octicons", 0xF400, 0xF533),
    ("Material Design Icons", 0xF0001, 0xF1AF0),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--gohu-bdf", required=True, type=Path)
    parser.add_argument("--sizes", type=int, nargs="+", default=DEFAULT_SIZES)
    parser.add_argument("--face-index", type=int, default=0)
    return parser.parse_args()


def codepoint_label(codepoint: int) -> str:
    width = 4 if codepoint <= 0xFFFF else 5
    return f"U+{codepoint:0{width}X}"


def infer_source(codepoint: int, gohu_codepoints: set[int]) -> str:
    # Gohu is restored after Nerd Fonts patching, so its encoded glyph wins if
    # an upstream source ever occupies the same private-use codepoint.
    if codepoint in gohu_codepoints:
        return "GohuFont"
    if is_powerline(codepoint):
        return "Powerline"
    for source, start, end in SOURCE_RANGES:
        if start <= codepoint <= end:
            return source
    return "Unknown"


def name_values(font: TTFont, name_id: int) -> list[str]:
    return sorted(
        {
            record.toUnicode()
            for record in font["name"].names
            if record.nameID == name_id
        }
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rounded(value: float) -> float:
    return round(value, 6)


def outline_metrics(font: TTFont, glyph_name: str) -> dict[str, Any]:
    glyph = font["glyf"][glyph_name]
    if glyph.numberOfContours == 0:
        return {"empty": True}
    glyph.recalcBounds(font["glyf"])
    bounds = [glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax]
    width = glyph.xMax - glyph.xMin
    height = glyph.yMax - glyph.yMin

    # Signed contour moments become nonsensical when overlapping components or
    # contours cancel one another. Measure a non-mutating Skia simplification of
    # the filled outline, using the same path operation as FontTools' overlap
    # remover, so holes and unions contribute correctly.
    path = _simplify(skPathFromGlyph(glyph_name, font.getGlyphSet()), glyph_name)
    moments = MomentsPen()
    path.draw(moments)
    signed_area = moments.area
    if math.isclose(signed_area, 0.0, abs_tol=1e-9):
        centroid = None
        visual_area = 0.0
    else:
        centroid = [
            rounded(moments.momentX / signed_area),
            rounded(moments.momentY / signed_area),
        ]
        visual_area = abs(signed_area)

    return {
        "empty": False,
        "bounds": bounds,
        "width": width,
        "height": height,
        "bbox_center": [rounded((glyph.xMin + glyph.xMax) / 2), rounded((glyph.yMin + glyph.yMax) / 2)],
        "visual_area": rounded(visual_area),
        "ink_centroid": centroid,
        "width_ratio": rounded(width / CELL_WIDTH),
        "height_ratio": rounded(height / UPM),
        "area_ratio": rounded(visual_area / (CELL_WIDTH * UPM)),
        "fill_ratio": rounded(visual_area / (width * height)) if width and height else 0.0,
        "touches_cell_edge": (
            glyph.xMin <= 0
            or glyph.xMax >= CELL_WIDTH
            or glyph.yMin <= DESCENT
            or glyph.yMax >= ASCENT
        ),
    }


def raster_metrics(font: ImageFont.FreeTypeFont, character: str) -> dict[str, Any]:
    mask, offset = font.getmask2(character, mode="L", anchor="ls")
    ink_box = mask.getbbox()
    advance = font.getlength(character)
    if ink_box is None:
        return {
            "empty": True,
            "advance": rounded(advance),
        }

    left, top, right, bottom = ink_box
    offset_x, offset_y = offset
    bounds = [
        offset_x + left,
        offset_y + top,
        offset_x + right,
        offset_y + bottom,
    ]
    pixels = bytes(mask)
    mask_width, _ = mask.size
    total = sum(pixels)
    weighted_x = 0.0
    weighted_y = 0.0
    for index, value in enumerate(pixels):
        if not value:
            continue
        x = index % mask_width
        y = index // mask_width
        weighted_x += (offset_x + x + 0.5) * value
        weighted_y += (offset_y + y + 0.5) * value
    width = right - left
    height = bottom - top
    visual_area = total / 255
    return {
        "empty": False,
        "bounds": bounds,
        "width": width,
        "height": height,
        "advance": rounded(advance),
        "visual_area": rounded(visual_area),
        "ink_centroid": [
            rounded(weighted_x / total),
            rounded(weighted_y / total),
        ],
        "fill_ratio": rounded(visual_area / (width * height)),
    }


def percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return rounded(ordered[lower])
    weight = position - lower
    return rounded(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def distribution(values: Iterable[float]) -> dict[str, float | int | None]:
    materialized = list(values)
    return {
        "count": len(materialized),
        "minimum": rounded(min(materialized)) if materialized else None,
        "p05": percentile(materialized, 0.05),
        "median": percentile(materialized, 0.5),
        "p95": percentile(materialized, 0.95),
        "maximum": rounded(max(materialized)) if materialized else None,
    }


def summarize(icons: list[dict[str, Any]], sizes: tuple[int, ...]) -> dict[str, Any]:
    ordinary = [icon for icon in icons if not icon["protected"]]
    nonempty = [icon for icon in ordinary if not icon["outline"]["empty"]]
    source_counts = Counter(icon["source"] for icon in icons)
    raster_empty = {
        str(size): sum(icon["raster"][str(size)]["empty"] for icon in icons)
        for size in sizes
    }
    return {
        "pua_mappings": len(icons),
        "unique_glyphs": len({icon["glyph"] for icon in icons}),
        "ordinary_icons": len(ordinary),
        "protected_powerline": len(icons) - len(ordinary),
        "unknown_source": source_counts["Unknown"],
        "empty_outlines": sum(icon["outline"]["empty"] for icon in icons),
        "empty_rasters": raster_empty,
        "source_counts": dict(sorted(source_counts.items())),
        "ordinary_outline_distributions": {
            key: distribution(icon["outline"][key] for icon in nonempty)
            for key in ("width_ratio", "height_ratio", "area_ratio", "fill_ratio")
        },
        "ordinary_centroid_offsets": {
            "x_from_cell_center": distribution(
                icon["outline"]["ink_centroid"][0] - CELL_WIDTH / 2
                for icon in nonempty
                if icon["outline"]["ink_centroid"] is not None
            ),
            "y_from_line_center": distribution(
                icon["outline"]["ink_centroid"][1] - (ASCENT + DESCENT) / 2
                for icon in nonempty
                if icon["outline"]["ink_centroid"] is not None
            ),
        },
    }


def main() -> None:
    args = parse_args()
    sizes = tuple(sorted(set(args.sizes)))
    collection = TTCollection(args.collection)
    if not 0 <= args.face_index < len(collection.fonts):
        raise ValueError(f"face index {args.face_index} is outside the collection")
    font = collection.fonts[args.face_index]
    cmap = font.getBestCmap()
    gohu_codepoints = {glyph.encoding for glyph in load_bdf(args.gohu_bdf).glyphs}
    reverse_cmap: dict[str, list[int]] = defaultdict(list)
    for codepoint, glyph_name in cmap.items():
        reverse_cmap[glyph_name].append(codepoint)

    raster_fonts = {
        size: ImageFont.truetype(
            str(args.collection),
            size=size,
            index=args.face_index,
        )
        for size in sizes
    }
    icons: list[dict[str, Any]] = []
    for codepoint, glyph_name in sorted(cmap.items()):
        if not is_private_use(codepoint):
            continue
        icons.append(
            {
                "codepoint": codepoint_label(codepoint),
                "codepoint_value": codepoint,
                "glyph": glyph_name,
                "source": infer_source(codepoint, gohu_codepoints),
                "protected": is_powerline(codepoint),
                "aliases": [
                    codepoint_label(alias)
                    for alias in sorted(reverse_cmap[glyph_name])
                    if alias != codepoint
                ],
                "outline": outline_metrics(font, glyph_name),
                "raster": {
                    str(size): raster_metrics(raster_fonts[size], chr(codepoint))
                    for size in sizes
                },
            }
        )

    report = {
        "schema": 1,
        "collection": str(args.collection),
        "collection_sha256": sha256(args.collection),
        "family": name_values(font, 1),
        "style": name_values(font, 2),
        "face_index": args.face_index,
        "units_per_em": font["head"].unitsPerEm,
        "cell": {
            "advance": CELL_WIDTH,
            "ascent": ASCENT,
            "descent": DESCENT,
        },
        "raster_sizes": list(sizes),
        "coordinate_systems": {
            "outline": "x right, y up, font units, baseline origin",
            "raster": "x right, y down, pixels, baseline origin",
        },
        "summary": summarize(icons, sizes),
        "icons": icons,
    }
    if report["summary"]["unknown_source"]:
        unknown = [icon["codepoint"] for icon in icons if icon["source"] == "Unknown"]
        raise ValueError(f"unclassified PUA source ranges: {unknown[:20]}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output}")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
