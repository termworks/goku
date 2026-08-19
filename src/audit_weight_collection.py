#!/usr/bin/env python3
"""Verify that Goku's weight family changes text weight and nothing else."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

from fontTools.ttLib import TTCollection, TTFont
from PIL import ImageFont

from design import VERSION
from text_glyphs import text_glyph_names


EXPECTED = {
    "100": (100, "Regular", True),
    "100 Italic": (100, "Italic", True),
    "200": (200, "Regular", True),
    "200 Italic": (200, "Italic", True),
    "300": (300, "Regular", True),
    "300 Italic": (300, "Italic", True),
    "400": (400, "Regular", False),
    "400 Italic": (400, "Italic", False),
    "500": (500, "Regular", True),
    "500 Italic": (500, "Italic", True),
    "600": (600, "Bold", True),
    "600 Italic": (600, "Bold Italic", True),
    "700": (700, "Bold", False),
    "700 Italic": (700, "Bold Italic", False),
    "800": (800, "Bold", True),
    "800 Italic": (800, "Bold Italic", True),
    "900": (900, "Bold", True),
    "900 Italic": (900, "Bold Italic", True),
}
MAX_WEIGHT_EDGE_DRIFT = 100
CODING_SAMPLE = (
    "abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ "
    "0123456789 0O1Il| {}[]() <> != == -> => :: // **"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--regular-bdf", required=True, type=Path)
    parser.add_argument("--bold-bdf", required=True, type=Path)
    parser.add_argument("--family", default="Goku")
    return parser.parse_args()


def font_name(font: TTFont, name_id: int) -> str:
    value = font["name"].getDebugName(name_id)
    if not value:
        raise ValueError(f"missing name ID {name_id}")
    return value


def indexed_faces(collection: TTCollection) -> dict[str, tuple[int, TTFont]]:
    return {
        font_name(font, 17): (index, font)
        for index, font in enumerate(collection.fonts)
    }


def outline_bytes(font: TTFont, glyph_name: str) -> bytes:
    glyph = copy.deepcopy(font["glyf"][glyph_name])
    glyph.removeHinting()
    return glyph.compile(font["glyf"])


def outline_bounds(font: TTFont, glyph_name: str) -> tuple[int, int, int, int] | None:
    glyph = font["glyf"][glyph_name]
    if glyph.numberOfContours == 0:
        return None
    glyph.recalcBounds(font["glyf"])
    return glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax


def private_use(codepoint: int) -> bool:
    return (
        0xE000 <= codepoint <= 0xF8FF
        or 0xF0000 <= codepoint <= 0xFFFFD
        or 0x100000 <= codepoint <= 0x10FFFD
    )


def mask(font: ImageFont.FreeTypeFont, character: str) -> tuple:
    bitmap, offset = font.getmask2(character, mode="L", anchor="ls")
    return font.getlength(character), bitmap.size, offset, bytes(bitmap)


def has_glyph_program(font: TTFont, glyph_name: str) -> bool:
    glyph = font["glyf"][glyph_name]
    return bool(
        hasattr(glyph, "program")
        and glyph.program is not None
        and glyph.program.getBytecode()
    )


def main() -> None:
    args = parse_args()
    source_collection = TTCollection(args.source)
    candidate_collection = TTCollection(args.candidate)
    source = indexed_faces(source_collection)
    candidate = indexed_faces(candidate_collection)
    if set(candidate) != set(EXPECTED):
        raise ValueError(
            f"candidate styles differ: {sorted(set(candidate) ^ set(EXPECTED))}"
        )

    for style, (weight_value, source_style, should_change) in EXPECTED.items():
        _, original = source[source_style]
        _, weighted = candidate[style]
        assert font_name(weighted, 16) == args.family
        suffix = "Italic" if style.endswith(" Italic") else ""
        postscript = f"{''.join(c for c in args.family if c.isalnum())}-{weight_value}{suffix}"
        assert font_name(weighted, 4) == (
            f"{args.family}-{weight_value}{' Italic' if suffix else ''}"
        )
        assert font_name(weighted, 6) == postscript
        assert font_name(weighted, 5) == f"Version {VERSION}; Goku"
        assert font_name(weighted, 3) == f"{VERSION};GOKU;{postscript}"
        assert weighted["OS/2"].usWeightClass == weight_value
        assert weighted.getGlyphOrder() == original.getGlyphOrder()
        assert weighted.getBestCmap() == original.getBestCmap()
        assert {
            name: advance for name, (advance, _) in weighted["hmtx"].metrics.items()
        } == {
            name: advance for name, (advance, _) in original["hmtx"].metrics.items()
        }

        bdf_path = (
            args.bold_bdf if source_style.startswith("Bold") else args.regular_bdf
        )
        allowed = text_glyph_names(original, bdf_path)
        changed = {
            name
            for name in original.getGlyphOrder()
            if outline_bytes(original, name) != outline_bytes(weighted, name)
        }
        assert changed <= allowed, f"{style} altered non-text: {sorted(changed - allowed)}"
        if should_change:
            assert changed, f"{style} did not change any text outlines"
        else:
            assert not changed, f"{style} unexpectedly changed outlines"

        hinted_text = {name for name in allowed if has_glyph_program(weighted, name)}
        hinted_nontext = {
            name
            for name in weighted.getGlyphOrder()
            if name not in allowed and has_glyph_program(weighted, name)
        }
        assert len(hinted_text) >= 300, (
            f"{style} lost small-size text hinting: {len(hinted_text)} hinted glyphs"
        )
        assert not hinted_nontext, (
            f"{style} unexpectedly hinted symbols: {sorted(hinted_nontext)[:12]}"
        )

        edge_drifts: dict[str, int] = {}
        for name in changed:
            original_bounds = outline_bounds(original, name)
            weighted_bounds = outline_bounds(weighted, name)
            if original_bounds is None or weighted_bounds is None:
                continue
            edge_drifts[name] = max(
                abs(before - after)
                for before, after in zip(original_bounds, weighted_bounds)
            )
        excessive_drift = {
            name: drift
            for name, drift in edge_drifts.items()
            if drift > MAX_WEIGHT_EDGE_DRIFT
        }
        assert not excessive_drift, (
            f"{style} contains likely glyph substitutions: "
            f"{sorted(excessive_drift.items(), key=lambda item: -item[1])[:12]}"
        )

        for table, fields in {
            "head": ("unitsPerEm",),
            "hhea": ("ascent", "descent", "lineGap", "advanceWidthMax"),
            "OS/2": (
                "usWidthClass",
                "sTypoAscender",
                "sTypoDescender",
                "sTypoLineGap",
                "usWinAscent",
                "usWinDescent",
                "sxHeight",
                "sCapHeight",
            ),
            "post": ("isFixedPitch",),
        }.items():
            for field in fields:
                assert getattr(weighted[table], field) == getattr(original[table], field)
        print(
            f"{style}: {len(changed)} text outlines changed; non-text preserved; "
            f"max edge drift {max(edge_drifts.values(), default=0)}; "
            f"{len(hinted_text)} text glyphs hinted"
        )

    weight_raster_checks = 0
    for italic in (False, True):
        for size in (10, 14, 32):
            ink_by_weight: list[tuple[int, int]] = []
            raster_signatures: set[bytes] = set()
            for weight_value in range(100, 1000, 100):
                style = str(weight_value) + (" Italic" if italic else "")
                candidate_index, _ = candidate[style]
                raster_font = ImageFont.truetype(
                    str(args.candidate), size=size, index=candidate_index
                )
                raster = mask(raster_font, CODING_SAMPLE)[3]
                ink_by_weight.append((weight_value, sum(raster)))
                raster_signatures.add(raster)
                weight_raster_checks += 1
            assert len(raster_signatures) == 9, (
                f"numeric weights collapse to identical "
                f"{'italic' if italic else 'upright'} rasters at {size}px"
            )
            assert all(
                lighter[1] < heavier[1]
                for lighter, heavier in zip(ink_by_weight, ink_by_weight[1:])
            ), (
                f"numeric weights are not visually monotonic for "
                f"{'italic' if italic else 'upright'} at {size}px: {ink_by_weight}"
            )

    pua = [
        codepoint
        for codepoint in source["Regular"][1].getBestCmap()
        if private_use(codepoint)
    ]
    raster_checks = 0
    baseline_raster_checks = 0
    for style, (_, source_style, _) in EXPECTED.items():
        candidate_index, _ = candidate[style]
        source_index, _ = source[source_style]
        for size in (10, 14):
            original_font = ImageFont.truetype(
                str(args.source), size=size, index=source_index
            )
            weighted_font = ImageFont.truetype(
                str(args.candidate), size=size, index=candidate_index
            )
            for codepoint in pua:
                character = chr(codepoint)
                assert mask(weighted_font, character) == mask(original_font, character)
                raster_checks += 1

        if not EXPECTED[style][2]:
            for size in range(7, 15):
                original_font = ImageFont.truetype(
                    str(args.source), size=size, index=source_index
                )
                weighted_font = ImageFont.truetype(
                    str(args.candidate), size=size, index=candidate_index
                )
                assert mask(weighted_font, CODING_SAMPLE) == mask(
                    original_font, CODING_SAMPLE
                ), f"{style} no longer matches known-good raster at {size}px"
                baseline_raster_checks += 1

    source_collection.close()
    candidate_collection.close()
    print(
        f"Weight-family audit passed: {len(EXPECTED)} faces, "
        f"{weight_raster_checks} distinct/monotonic weight rasters, "
        f"{raster_checks} PUA rasters, "
        f"{baseline_raster_checks} known-good text rasters"
    )


if __name__ == "__main__":
    main()
