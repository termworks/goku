#!/usr/bin/env python3
"""Raster-regression checks for Goku at small and native terminal sizes."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from fontTools.ttLib import TTCollection
from PIL import ImageFont

from design import CELL_WIDTH, UPM


SIZES = (7, 8, 9, 10, 11, 12, 13, 14, 16, 20, 24, 29)
SAMPLES = ("A", "0", "─", "│", "█", "▓", "▒", "░", "\ue0b0", "\uf015")
UPRIGHT = ("─", "│", "█", "▓", "▒", "░", "\ue0b0", "\uf015")
EXPECTED_STYLES = {"Regular", "Bold", "Italic", "Bold Italic"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", required=True, type=Path)
    return parser.parse_args()


def name_values(font, name_id: int) -> set[str]:
    return {
        record.toUnicode()
        for record in font["name"].names
        if record.nameID == name_id
    }


def face_style(font) -> str:
    matches = name_values(font, 2) & EXPECTED_STYLES
    assert len(matches) == 1
    return matches.pop()


def mask_signature(
    font: ImageFont.FreeTypeFont,
    text: str,
) -> tuple[tuple[int, int], bytes]:
    mask = font.getmask(text, mode="L")
    return mask.size, bytes(mask)


def assert_full_block(font: ImageFont.FreeTypeFont) -> None:
    mask = font.getmask("█", mode="L")
    width, height = mask.size
    pixels = bytes(mask)
    assert width and height and any(pixels)
    assert all(any(pixels[y * width + x] for y in range(height)) for x in range(width))
    assert all(any(pixels[y * width : (y + 1) * width]) for y in range(height))


def main() -> None:
    args = parse_args()
    collection = TTCollection(args.collection)
    indices = {face_style(font): index for index, font in enumerate(collection.fonts)}
    assert set(indices) == EXPECTED_STYLES

    checked_masks = 0
    for size in SIZES:
        fonts = {
            style: ImageFont.truetype(str(args.collection), size=size, index=index)
            for style, index in indices.items()
        }

        advances = {
            round(font.getlength(character), 6)
            for font in fonts.values()
            for character in SAMPLES
        }
        assert len(advances) == 1, f"non-monospaced raster advances at {size}px: {advances}"
        advance = advances.pop()
        assert abs(advance - size * CELL_WIDTH / UPM) <= 1 / 32

        for font in fonts.values():
            for character in SAMPLES:
                dimensions, pixels = mask_signature(font, character)
                assert dimensions[0] > 0 and dimensions[1] > 0
                assert any(pixels), f"empty U+{ord(character):04X} mask at {size}px"
                # Cell-contained icons should never rasterize as a double-width
                # glyph. One antialiasing fringe pixel is allowed per side.
                if ord(character) >= 0xE000 and character != "\ue0b0":
                    assert dimensions[0] <= math.ceil(advance) + 2
                checked_masks += 1
            assert_full_block(font)

        for character in UPRIGHT:
            assert mask_signature(fonts["Regular"], character) == mask_signature(
                fonts["Italic"], character
            ), f"italic changed U+{ord(character):04X} at {size}px"
            assert mask_signature(fonts["Bold"], character) == mask_signature(
                fonts["Bold Italic"], character
            ), f"bold italic changed U+{ord(character):04X} at {size}px"

    native = ImageFont.truetype(
        str(args.collection),
        size=14,
        index=indices["Regular"],
    )
    assert abs(native.getlength("M") - 8) <= 1 / 32

    print("Goku raster audit passed")
    print(f"  sizes: {', '.join(map(str, SIZES))} px")
    print(f"  nonempty glyph masks checked: {checked_masks}")
    print("  advances remain monospaced across all four faces")
    print("  full blocks have no empty raster rows or columns")
    print("  terminal symbols remain pixel-identical in italic faces")
    print("  native 14px source cell rasterizes to an 8px advance")


if __name__ == "__main__":
    main()
