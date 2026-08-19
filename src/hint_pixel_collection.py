#!/usr/bin/env python3
"""Regenerate small-size text hinting after universal pixel quantization."""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

from fontTools.ttLib import TTCollection, TTFont

from design import SOURCE_DATE_EPOCH
from text_glyphs import text_glyph_names


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--regular-bdf", required=True, type=Path)
    parser.add_argument("--bold-bdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error("--source and --output must be different files")
    return args


def retain_only_text_hinting(font: TTFont, text_names: set[str]) -> int:
    removed = 0
    for name in font.getGlyphOrder():
        if name in text_names:
            continue
        glyph = font["glyf"][name]
        if (
            hasattr(glyph, "program")
            and glyph.program is not None
            and glyph.program.getBytecode()
        ):
            glyph.removeHinting()
            removed += 1
    return removed


def autohint_face(
    source: TTFont,
    source_path: Path,
    output_path: Path,
    reference_path: Path,
    text_names: set[str],
) -> TTFont:
    source.save(source_path, reorderTables=False)
    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = str(SOURCE_DATE_EPOCH)
    command = (
        "ttfautohint",
        "--no-info",
        "--increase-x-height=0",
        "--windows-compatibility",
        "--stem-width-mode=qqq",
        "--hinting-range-min=6",
        "--hinting-range-max=13",
        "--hinting-limit=13",
        "--fallback-script=none",
        "--fallback-scaling",
        f"--reference={reference_path}",
        str(source_path),
        str(output_path),
    )
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        env=environment,
    )
    if completed.returncode:
        style = source["name"].getDebugName(17) or source_path.stem
        raise RuntimeError(
            f"ttfautohint failed for {style}:\n"
            f"{completed.stdout}\n{completed.stderr}"
        )

    hinted = TTFont(output_path, recalcTimestamp=False)
    removed = retain_only_text_hinting(hinted, text_names)
    hinted["head"].created = source["head"].created
    hinted["head"].modified = source["head"].modified
    hinted.recalcTimestamp = False
    style = source["name"].getDebugName(17) or source_path.stem
    print(
        f"  hinted {style}; stripped programs from {removed} non-text glyphs",
        flush=True,
    )
    return hinted


def main() -> None:
    args = parse_args()
    source = TTCollection(args.source)
    hinted_fonts: list[TTFont] = []

    with tempfile.TemporaryDirectory(prefix="goku-pixel-hints-") as directory:
        temporary = Path(directory)
        reference_path = temporary / "Goku-Pixel-400-reference.ttf"
        reference = TTFont(args.source, fontNumber=6, recalcTimestamp=False)
        reference.save(reference_path, reorderTables=False)
        reference.close()

        for index, font in enumerate(source.fonts):
            weight = font["OS/2"].usWeightClass
            bdf_path = args.regular_bdf if weight <= 500 else args.bold_bdf
            text_names = text_glyph_names(font, bdf_path)
            hinted_fonts.append(
                autohint_face(
                    font,
                    temporary / f"{index:02}-unhinted.ttf",
                    temporary / f"{index:02}-hinted.ttf",
                    reference_path,
                    text_names,
                )
            )

        args.output.parent.mkdir(parents=True, exist_ok=True)
        candidate = TTCollection()
        candidate.fonts = hinted_fonts
        candidate.save(args.output, shareTables=True)
        candidate.close()
        for font in hinted_fonts:
            font.close()

    source.close()
    print(f"Built hinted pixel collection: {args.output}", flush=True)


if __name__ == "__main__":
    main()
