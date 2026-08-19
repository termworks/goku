#!/usr/bin/env python3
"""Explain exactly how a rejected Goku candidate differs from a good TTC."""

from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.ttLib import TTCollection
from PIL import ImageFont


STYLES = ("Regular", "Bold", "Italic", "Bold Italic")
TEXT_SAMPLE = (
    "abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ "
    "0123456789 0OQ 1Il| {}[]() <> != == -> => :: // **"
)
SIZES = (7, 8, 9, 10, 14, 20, 29)


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    return parser.parse_args()


def names(font, name_id: int) -> set[str]:
    return {
        record.toUnicode()
        for record in font["name"].names
        if record.nameID == name_id
    }


def style(font) -> str:
    matches = names(font, 2) & set(STYLES)
    assert len(matches) == 1
    return matches.pop()


def faces(collection: TTCollection):
    return {style(font): (index, font) for index, font in enumerate(collection.fonts)}


def glyph_bytes(font, glyph_name: str) -> bytes:
    return font["glyf"][glyph_name].compile(font["glyf"])


def mask_signature(font: ImageFont.FreeTypeFont, text: str):
    mask, offset = font.getmask2(text, mode="L", anchor="ls")
    return font.getlength(text), mask.size, offset, bytes(mask)


def is_terminal(codepoint: int) -> bool:
    return (
        0x2500 <= codepoint <= 0x259F
        or 0x2800 <= codepoint <= 0x28FF
        or 0x1FB00 <= codepoint <= 0x1FBFF
        or 0x1CC00 <= codepoint <= 0x1CEBF
    )


def is_private_use(codepoint: int) -> bool:
    return (
        0xE000 <= codepoint <= 0xF8FF
        or 0xF0000 <= codepoint <= 0xFFFFD
        or 0x100000 <= codepoint <= 0x10FFFD
    )


def main() -> None:
    options = args()
    baseline_collection = TTCollection(options.baseline)
    candidate_collection = TTCollection(options.candidate)
    baseline_faces = faces(baseline_collection)
    candidate_faces = faces(candidate_collection)
    assert set(baseline_faces) == set(candidate_faces) == set(STYLES)

    global_metric_fields = {
        "head": ("unitsPerEm", "xMin", "yMin", "xMax", "yMax", "macStyle"),
        "hhea": (
            "ascent",
            "descent",
            "lineGap",
            "advanceWidthMax",
            "minLeftSideBearing",
            "minRightSideBearing",
            "xMaxExtent",
        ),
        "OS/2": (
            "usWeightClass",
            "usWidthClass",
            "sTypoAscender",
            "sTypoDescender",
            "sTypoLineGap",
            "usWinAscent",
            "usWinDescent",
            "sxHeight",
            "sCapHeight",
        ),
        "post": ("italicAngle", "underlinePosition", "underlineThickness", "isFixedPitch"),
    }

    for face_style in STYLES:
        baseline_index, baseline = baseline_faces[face_style]
        candidate_index, candidate = candidate_faces[face_style]
        baseline_order = baseline.getGlyphOrder()
        candidate_order = candidate.getGlyphOrder()
        baseline_cmap = baseline.getBestCmap()
        candidate_cmap = candidate.getBestCmap()

        assert candidate_order[: len(baseline_order)] == baseline_order
        assert all(candidate_cmap.get(cp) == name for cp, name in baseline_cmap.items())

        added_codepoints = set(candidate_cmap) - set(baseline_cmap)
        changed_names = {
            name
            for name in baseline_order
            if glyph_bytes(baseline, name) != glyph_bytes(candidate, name)
        }
        metric_differences = {
            name
            for name in baseline_order
            if baseline["hmtx"].metrics[name] != candidate["hmtx"].metrics[name]
        }
        codepoints_by_name: dict[str, set[int]] = {}
        for cp, name in baseline_cmap.items():
            codepoints_by_name.setdefault(name, set()).add(cp)
        changed_codepoints = {
            cp
            for name in changed_names
            for cp in codepoints_by_name.get(name, ())
        }
        terminal_changes = {cp for cp in changed_codepoints if is_terminal(cp)}
        private_changes = {cp for cp in changed_codepoints if is_private_use(cp)}
        other_changes = changed_codepoints - terminal_changes - private_changes

        global_differences = []
        for table, fields in global_metric_fields.items():
            for field in fields:
                before = getattr(baseline[table], field)
                after = getattr(candidate[table], field)
                if before != after:
                    global_differences.append((table, field, before, after))

        raster_differences = []
        for size in SIZES:
            before_font = ImageFont.truetype(
                str(options.baseline), size=size, index=baseline_index
            )
            after_font = ImageFont.truetype(
                str(options.candidate), size=size, index=candidate_index
            )
            if mask_signature(before_font, TEXT_SAMPLE) != mask_signature(
                after_font, TEXT_SAMPLE
            ):
                raster_differences.append(size)

        print(face_style)
        print(
            f"  glyphs {len(baseline_order)} -> {len(candidate_order)}; "
            f"added cmap codepoints: {len(added_codepoints)}"
        )
        print(
            f"  changed existing outlines: {len(changed_names)} "
            f"({len(terminal_changes)} terminal, {len(private_changes)} private-use, "
            f"{len(other_changes)} other codepoints)"
        )
        print(f"  changed existing hmtx records: {len(metric_differences)}")
        print(f"  global metric differences: {global_differences}")
        print(f"  coding-text raster differences at sizes: {raster_differences}")
        if other_changes:
            print(
                "  unexpected changed codepoints: "
                + " ".join(f"U+{cp:04X}" for cp in sorted(other_changes))
            )

    baseline_collection.close()
    candidate_collection.close()


if __name__ == "__main__":
    main()
