#!/usr/bin/env python3
"""Prove that a Goku candidate changes only its declared icon policy."""

from __future__ import annotations

import argparse
import copy
import unicodedata
from pathlib import Path

from fontTools.ttLib import TTCollection, TTFont
from PIL import ImageFont

from bdf import load_bdf
from font_variants import is_powerline, is_private_use
from icon_optical_policy import OPTICAL_SCALE_BY_CODEPOINT


EXPECTED_STYLES = {"Regular", "Bold", "Italic", "Bold Italic"}
DEFAULT_SIZES = (10, 14, 20)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--regular-bdf", required=True, type=Path)
    parser.add_argument("--bold-bdf", required=True, type=Path)
    parser.add_argument("--sizes", type=int, nargs="+", default=DEFAULT_SIZES)
    return parser.parse_args()


def name_values(font: TTFont, name_id: int) -> set[str]:
    return {
        record.toUnicode()
        for record in font["name"].names
        if record.nameID == name_id
    }


def face_style(font: TTFont) -> str:
    matches = name_values(font, 2) & EXPECTED_STYLES
    assert len(matches) == 1
    return matches.pop()


def faces(collection: TTCollection) -> dict[str, TTFont]:
    result = {face_style(font): font for font in collection.fonts}
    assert set(result) == EXPECTED_STYLES
    return result


def face_indices(collection: TTCollection) -> dict[str, int]:
    result = {
        face_style(font): index for index, font in enumerate(collection.fonts)
    }
    assert set(result) == EXPECTED_STYLES
    return result


def outline_bytes(font: TTFont, glyph_name: str) -> bytes:
    glyph = copy.deepcopy(font["glyf"][glyph_name])
    glyph.removeHinting()
    return glyph.compile(font["glyf"])


def text_names(font: TTFont, bdf_path: Path) -> set[str]:
    cmap = font.getBestCmap()
    result = {
        cmap[glyph.encoding]
        for glyph in load_bdf(bdf_path).glyphs
        if glyph.encoding in cmap
        and unicodedata.category(chr(glyph.encoding))[0] in {"L", "M", "N", "P"}
    }
    result.add("zero.ss01")
    return result


def mask_signature(font: ImageFont.FreeTypeFont, character: str) -> tuple:
    mask, offset = font.getmask2(character, mode="L", anchor="ls")
    return mask.size, offset, bytes(mask)


def main() -> None:
    args = parse_args()
    baseline_collection = TTCollection(args.baseline)
    candidate_collection = TTCollection(args.candidate)
    baseline_faces = faces(baseline_collection)
    candidate_faces = faces(candidate_collection)
    baseline_indices = face_indices(baseline_collection)
    candidate_indices = face_indices(candidate_collection)

    policy_codepoints = set(OPTICAL_SCALE_BY_CODEPOINT)
    pua_codepoints = {
        codepoint
        for codepoint in baseline_faces["Regular"].getBestCmap()
        if is_private_use(codepoint)
    }
    assert policy_codepoints <= pua_codepoints

    for style in EXPECTED_STYLES:
        baseline = baseline_faces[style]
        candidate = candidate_faces[style]
        assert baseline.getGlyphOrder() == candidate.getGlyphOrder()
        assert baseline.getBestCmap() == candidate.getBestCmap()
        assert {
            name: advance
            for name, (advance, _) in baseline["hmtx"].metrics.items()
        } == {
            name: advance
            for name, (advance, _) in candidate["hmtx"].metrics.items()
        }
        expected_names = {
            candidate.getBestCmap()[codepoint] for codepoint in policy_codepoints
        }
        changed_names = {
            name
            for name in candidate.getGlyphOrder()
            if outline_bytes(baseline, name) != outline_bytes(candidate, name)
        }
        assert changed_names == expected_names, (
            f"{style} changed unexpected outlines: "
            f"extra={sorted(changed_names - expected_names)[:10]}, "
            f"missing={sorted(expected_names - changed_names)[:10]}"
        )

        bdf_path = args.bold_bdf if "Bold" in style else args.regular_bdf
        for name in text_names(candidate, bdf_path):
            assert outline_bytes(baseline, name) == outline_bytes(candidate, name)
        powerline_names = {
            name
            for codepoint, name in candidate.getBestCmap().items()
            if is_powerline(codepoint)
        }
        for name in powerline_names:
            assert outline_bytes(baseline, name) == outline_bytes(candidate, name)

    candidate_regular = candidate_faces["Regular"]
    candidate_bold = candidate_faces["Bold"]
    candidate_italic = candidate_faces["Italic"]
    candidate_bold_italic = candidate_faces["Bold Italic"]
    for codepoint in pua_codepoints:
        name = candidate_regular.getBestCmap()[codepoint]
        assert outline_bytes(candidate_regular, name) == outline_bytes(
            candidate_italic, name
        )
        assert outline_bytes(candidate_bold, name) == outline_bytes(
            candidate_bold_italic, name
        )

    raster_checks = 0
    intentional_blanks: dict[int, list[str]] = {}
    for size in sorted(set(args.sizes)):
        baseline_fonts = {
            style: ImageFont.truetype(
                str(args.baseline), size=size, index=baseline_indices[style]
            )
            for style in EXPECTED_STYLES
        }
        candidate_fonts = {
            style: ImageFont.truetype(
                str(args.candidate), size=size, index=candidate_indices[style]
            )
            for style in EXPECTED_STYLES
        }
        blank_labels: list[str] = []
        for codepoint in sorted(pua_codepoints):
            character = chr(codepoint)
            baseline_mask = mask_signature(baseline_fonts["Regular"], character)
            candidate_mask = mask_signature(candidate_fonts["Regular"], character)
            baseline_empty = not any(baseline_mask[2])
            candidate_empty = not any(candidate_mask[2])
            assert candidate_empty == baseline_empty
            if candidate_empty:
                blank_labels.append(f"U+{codepoint:04X}")
            if codepoint not in policy_codepoints:
                assert candidate_mask == baseline_mask
            assert candidate_mask == mask_signature(
                candidate_fonts["Italic"], character
            )
            assert mask_signature(
                candidate_fonts["Bold"], character
            ) == mask_signature(candidate_fonts["Bold Italic"], character)
            raster_checks += 1
        intentional_blanks[size] = blank_labels

    assert all(labels == ["U+EC03"] for labels in intentional_blanks.values())
    print("Goku candidate scope regression passed")
    print(f"  declared changed glyphs per face: {len(policy_codepoints)}")
    print("  every other outline is byte-identical to the baseline")
    print("  Gohu text and Powerline outlines are unchanged")
    print(f"  full-PUA raster checks: {raster_checks}")
    print(f"  intentional blank baseline: {intentional_blanks}")
    print("  all PUA glyphs remain identical across roman/italic pairs")


if __name__ == "__main__":
    main()
