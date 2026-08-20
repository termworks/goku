#!/usr/bin/env python3
"""Build one portable Goku TTC containing all four RIBBI faces."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fontTools.ttLib import TTCollection, TTFont

from design import (
    FAMILY,
    HINTING_LIMIT,
    HINTING_RANGE_MAX,
    HINTING_RANGE_MIN,
    POSTSCRIPT_STEM,
    SOURCE_DATE_EPOCH,
)
from font_variants import (
    add_text_cell_clearance,
    italicize,
    normalize_nerd_icons,
    set_style,
)
from terminal_graphics import apply_native_terminal_graphics
from text_glyphs import text_glyph_names


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--regular-bdf", required=True, type=Path)
    parser.add_argument("--bold-bdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def run(*command: str) -> None:
    subprocess.run(command, check=True)


def autohint_face(
    source: Path,
    output: Path,
    reference: Path,
    text_glyphs: set[str],
) -> TTFont:
    """Strongly hint small text while leaving terminal symbols untouched."""
    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = str(SOURCE_DATE_EPOCH)
    subprocess.run(
        (
            "ttfautohint",
            "--no-info",
            "--increase-x-height=0",
            "--windows-compatibility",
            "--stem-width-mode=sss",
            f"--hinting-range-min={HINTING_RANGE_MIN}",
            f"--hinting-range-max={HINTING_RANGE_MAX}",
            f"--hinting-limit={HINTING_LIMIT}",
            "--fallback-script=none",
            "--fallback-scaling",
            f"--reference={reference}",
            str(source),
            str(output),
        ),
        check=True,
        env=environment,
    )
    font = TTFont(output, recalcTimestamp=False)
    stripped = 0
    for name in font.getGlyphOrder():
        if name in text_glyphs:
            continue
        glyph = font["glyf"][name]
        if hasattr(glyph, "program") and glyph.program.getBytecode():
            glyph.removeHinting()
            stripped += 1
    print(f"  retained text hints; stripped hints from {stripped} symbols", flush=True)
    return font


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="goku-font-build-") as directory:
        temporary = Path(directory)
        source_dir = temporary / "source"
        patched_dir = temporary / "patched"
        source_dir.mkdir()
        patched_dir.mkdir()
        source_regular = source_dir / "Goku-Regular.ttf"

        run(
            sys.executable,
            str(Path(__file__).with_name("build_regular.py")),
            "--bdf",
            str(args.regular_bdf),
            "--output",
            str(source_regular),
        )
        run(
            "nerd-font-patcher",
            "--complete",
            "--mono",
            "--no-progressbars",
            "--quiet",
            "--outputdir",
            str(patched_dir),
            str(source_regular),
        )
        patched = list(patched_dir.glob("*.ttf"))
        if len(patched) != 1:
            raise ValueError(f"expected one Nerd-patched Goku TTF, found {patched}")
        patched_regular = patched[0]
        regular_path = temporary / "Goku-Regular.ttf"
        bold_path = temporary / "Goku-Bold.ttf"

        for bdf_path, style, output in (
            (args.regular_bdf, "Regular", regular_path),
            (args.bold_bdf, "Bold", bold_path),
        ):
            run(
                sys.executable,
                str(Path(__file__).with_name("build_bdf_face.py")),
                "--base",
                str(patched_regular),
                "--bdf",
                str(bdf_path),
                "--style",
                style,
                "--output",
                str(output),
            )

        regular = TTFont(regular_path, recalcTimestamp=False)
        bold = TTFont(bold_path, recalcTimestamp=False)
        normalize_nerd_icons(regular)
        normalize_nerd_icons(bold)
        italic = TTFont(regular_path, recalcTimestamp=False)
        bold_italic = TTFont(bold_path, recalcTimestamp=False)
        for font in (regular, bold, italic, bold_italic):
            # The established Goku glyphs are the visual baseline. Terminal
            # coverage is strictly additive: never rescale or replace a glyph
            # that users already approved in Kitty.
            apply_native_terminal_graphics(font, preserve_existing=True)
        normalize_nerd_icons(italic)
        normalize_nerd_icons(bold_italic)
        regular_text = text_glyph_names(regular, args.regular_bdf)
        bold_text = text_glyph_names(bold, args.bold_bdf)
        for font, text_glyphs in (
            (regular, regular_text),
            (bold, bold_text),
            (italic, regular_text),
            (bold_italic, bold_text),
        ):
            add_text_cell_clearance(font, text_glyphs)
        italicize(italic, regular_text)
        italicize(bold_italic, bold_text)
        face_data = (
            ("Regular", regular, False, False, regular_text),
            ("Bold", bold, True, False, bold_text),
            ("Italic", italic, False, True, regular_text),
            ("BoldItalic", bold_italic, True, True, bold_text),
        )
        unhinted_paths: dict[str, Path] = {}
        for label, font, is_bold, is_italic, _ in face_data:
            set_style(
                font,
                FAMILY,
                POSTSCRIPT_STEM,
                bold=is_bold,
                italic=is_italic,
            )
            path = temporary / f"Goku-{label}-unhinted.ttf"
            font.save(path, reorderTables=False)
            unhinted_paths[label] = path

        hinted_fonts: list[TTFont] = []
        reference = unhinted_paths["Regular"]
        for label, _, is_bold, is_italic, text_glyphs in face_data:
            hinted = autohint_face(
                unhinted_paths[label],
                temporary / f"Goku-{label}-hinted.ttf",
                reference,
                text_glyphs,
            )
            # Restore authoritative Goku metadata and deterministic timestamps
            # after the external hinter has added its bytecode tables.
            set_style(
                hinted,
                FAMILY,
                POSTSCRIPT_STEM,
                bold=is_bold,
                italic=is_italic,
            )
            hinted_fonts.append(hinted)

        collection = TTCollection()
        collection.fonts = hinted_fonts
        collection.save(args.output, shareTables=True)
        collection.close()

    print(f"Built {args.output}")
    print("Contained faces: Regular, Bold, Italic, Bold Italic")


if __name__ == "__main__":
    main()
