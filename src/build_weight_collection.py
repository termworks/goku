#!/usr/bin/env python3
"""Derive a numeric nine-weight family while preserving Goku's approved art."""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTCollection, TTFont

from design import (
    CELL_WIDTH,
    FONT_TIMESTAMP,
    ITALIC_OVERHANG,
    SOURCE_DATE_EPOCH,
    TEXT_HORIZONTAL_MARGIN,
    VERSION,
)
from font_variants import fit_glyphs_horizontally
from text_glyphs import text_glyph_names


@dataclass(frozen=True)
class Weight:
    name: str
    value: int
    source: str
    delta: int
    keep_hints: bool = False


WEIGHTS = (
    Weight("100", 100, "Regular", -60),
    Weight("200", 200, "Regular", -40),
    Weight("300", 300, "Regular", -20),
    Weight("400", 400, "Regular", 0, keep_hints=True),
    Weight("500", 500, "Regular", 30),
    Weight("600", 600, "Bold", -15),
    Weight("700", 700, "Bold", 0, keep_hints=True),
    Weight("800", 800, "Bold", 20),
    Weight("900", 900, "Bold", 40),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--regular-bdf", required=True, type=Path)
    parser.add_argument("--bold-bdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--family", default="Goku")
    return parser.parse_args()


def get_name(font: TTFont, name_id: int) -> str:
    value = font["name"].getDebugName(name_id)
    if not value:
        raise ValueError(f"font has no usable name ID {name_id}")
    return value


def source_faces(path: Path) -> dict[str, int]:
    collection = TTCollection(path, lazy=True)
    result: dict[str, int] = {}
    try:
        for index, font in enumerate(collection.fonts):
            style = get_name(font, 17) or get_name(font, 2)
            result[style.replace(" ", "")] = index
    finally:
        collection.close()
    required = {"Regular", "Italic", "Bold", "BoldItalic"}
    if not required <= result.keys():
        raise ValueError(f"source collection lacks faces: {sorted(required - result.keys())}")
    return result


def open_face(path: Path, index: int) -> TTFont:
    return TTFont(path, fontNumber=index, recalcTimestamp=False)


def remove_glyph_hinting(font: TTFont, glyph_names: set[str]) -> None:
    glyf = font["glyf"]
    for name in glyph_names:
        glyph = glyf[name]
        if hasattr(glyph, "program"):
            glyph.removeHinting()


def retain_only_text_hinting(font: TTFont, glyph_names: set[str]) -> int:
    removed = 0
    glyf = font["glyf"]
    for name in font.getGlyphOrder():
        if name in glyph_names:
            continue
        glyph = glyf[name]
        if (
            hasattr(glyph, "program")
            and glyph.program is not None
            and glyph.program.getBytecode()
        ):
            glyph.removeHinting()
            removed += 1
    return removed


def change_text_weight(
    source: TTFont,
    delta: int,
    glyph_names: set[str],
    temporary: Path,
    label: str,
    italic: bool,
) -> TTFont:
    if delta == 0:
        remove_glyph_hinting(source, glyph_names)
        source.recalcTimestamp = False
        return source

    source_path = temporary / f"{label}-source.ttf"
    changed_path = temporary / f"{label}-fontforge.ttf"
    selection_path = temporary / f"{label}-selection.txt"
    source.save(source_path, reorderTables=False)
    codepoints_by_name: dict[str, list[int]] = {}
    for codepoint, name in source.getBestCmap().items():
        if name in glyph_names:
            codepoints_by_name.setdefault(name, []).append(codepoint)
    unencoded_names = glyph_names - codepoints_by_name.keys()
    if unencoded_names - {"zero.ss01"}:
        raise ValueError(f"unexpected unencoded text glyphs: {sorted(unencoded_names)}")
    selection_lines = [
        f"U+{codepoint:04X}"
        for codepoints in codepoints_by_name.values()
        for codepoint in codepoints
    ]
    selection_lines.extend(f"name:{name}" for name in sorted(unencoded_names))
    selection_path.write_text(
        "\n".join(sorted(selection_lines)) + "\n", encoding="utf-8"
    )
    command = (
        "fontforge",
        "-quiet",
        "-script",
        str(Path(__file__).with_name("fontforge_change_text_weight.py")),
        str(source_path),
        str(changed_path),
        str(delta),
        str(selection_path),
    )
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(
            f"FontForge weight change failed for {label}:\n"
            f"{completed.stdout}\n{completed.stderr}"
        )

    changed = TTFont(changed_path, recalcTimestamp=False)
    try:
        source_glyf = source["glyf"]
        changed_set = changed.getGlyphSet()
        changed_cmap = changed.getBestCmap()
        for name in glyph_names:
            codepoints = codepoints_by_name.get(name, [])
            if codepoints:
                changed_names = {changed_cmap[codepoint] for codepoint in codepoints}
                changed_name = changed_cmap[min(codepoints)]
                reference_outline = None
                for alias_name in changed_names:
                    recording = DecomposingRecordingPen(changed_set)
                    changed_set[alias_name].draw(recording)
                    if reference_outline is None:
                        reference_outline = recording.value
                    elif recording.value != reference_outline:
                        raise ValueError(
                            f"FontForge split aliases for {name}: {sorted(changed_names)}"
                        )
            else:
                changed_name = name
            source_advance, _ = source["hmtx"].metrics[name]
            changed_advance, _ = changed["hmtx"].metrics[changed_name]
            x_shift = round((source_advance - changed_advance) / 2)
            recording = DecomposingRecordingPen(changed_set)
            changed_set[changed_name].draw(recording)
            pen = TTGlyphPen(None)
            recording.replay(TransformPen(pen, (1, 0, 0, 1, x_shift, 0)))
            source_glyf[name] = pen.glyph()
            source["hmtx"].metrics[name] = (source_advance, 0)
        for name in glyph_names:
            glyph = source_glyf[name]
            if glyph.numberOfContours != 0:
                glyph.recalcBounds(source_glyf)
                source["hmtx"].metrics[name] = (
                    source["hmtx"].metrics[name][0],
                    glyph.xMin,
                )
    finally:
        changed.close()
    remove_glyph_hinting(source, glyph_names)
    left = -ITALIC_OVERHANG if italic else TEXT_HORIZONTAL_MARGIN
    right = (
        CELL_WIDTH + ITALIC_OVERHANG
        if italic
        else CELL_WIDTH - TEXT_HORIZONTAL_MARGIN
    )
    fitted = fit_glyphs_horizontally(
        source,
        glyph_names,
        left,
        right,
        minimal_shift=True,
    )
    if fitted:
        print(f"  fitted {fitted} weighted text glyphs inside the cell", flush=True)
    source.recalcBBoxes = True
    source.recalcTimestamp = False
    return source


def autohint_weighted_face(
    font: TTFont,
    glyph_names: set[str],
    temporary: Path,
    label: str,
    reference: Path,
) -> TTFont:
    """Grid-fit generated text without collapsing its designed stem weight."""
    source_path = temporary / f"{label}-weighted.ttf"
    hinted_path = temporary / f"{label}-hinted.ttf"
    font.save(source_path, reorderTables=False)
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
        f"--reference={reference}",
        str(source_path),
        str(hinted_path),
    )
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        env=environment,
    )
    if completed.returncode:
        raise RuntimeError(
            f"ttfautohint failed for {label}:\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    font.close()
    hinted = TTFont(hinted_path, recalcTimestamp=False)
    stripped = retain_only_text_hinting(hinted, glyph_names)
    hinted.recalcTimestamp = False
    print(f"  hinted {label}; stripped hints from {stripped} symbols", flush=True)
    return hinted


def set_name(font: TTFont, name_id: int, value: str) -> None:
    table = font["name"]
    destinations = {
        (record.platformID, record.platEncID, record.langID)
        for record in table.names
        if record.nameID == name_id
    } or {(3, 1, 0x409)}
    for platform_id, encoding_id, language_id in destinations:
        table.setName(value, name_id, platform_id, encoding_id, language_id)


def rename_face(
    font: TTFont,
    family: str,
    weight: Weight,
    italic: bool,
) -> None:
    style = weight.name + (" Italic" if italic else "")
    ps_family = "".join(character for character in family if character.isalnum())
    postscript = f"{ps_family}-{weight.value}{'Italic' if italic else ''}"
    for name_id, value in {
        1: family,
        2: style,
        3: f"{VERSION};GOKU;{postscript}",
        4: f"{family}-{weight.value}{' Italic' if italic else ''}",
        6: postscript,
        16: family,
        17: style,
    }.items():
        set_name(font, name_id, value)

    os2 = font["OS/2"]
    os2.usWeightClass = weight.value
    os2.fsSelection &= ~((1 << 0) | (1 << 5) | (1 << 6) | (1 << 9))
    if italic:
        os2.fsSelection |= 1 << 0
    if weight.value >= 700:
        os2.fsSelection |= 1 << 5
    if weight.value == 400 and not italic:
        os2.fsSelection |= 1 << 6
    font["head"].macStyle = (1 if weight.value >= 700 else 0) | (2 if italic else 0)
    if italic:
        font["post"].italicAngle = -12.0
        font["hhea"].caretSlopeRise = 1000
        font["hhea"].caretSlopeRun = round(math.tan(math.radians(12.0)) * 1000)
    else:
        font["post"].italicAngle = 0
        font["hhea"].caretSlopeRise = 1
        font["hhea"].caretSlopeRun = 0
    font["hhea"].caretOffset = 0
    font["head"].created = FONT_TIMESTAMP
    font["head"].modified = FONT_TIMESTAMP
    font.recalcTimestamp = False
    if "DSIG" in font:
        del font["DSIG"]


def main() -> None:
    args = parse_args()
    indexes = source_faces(args.source)
    built: list[TTFont] = []
    with tempfile.TemporaryDirectory(prefix="goku-weights-") as directory:
        temporary = Path(directory)
        reference_font = open_face(args.source, indexes["Regular"])
        reference_path = temporary / "Goku-Regular-reference.ttf"
        reference_font.save(reference_path, reorderTables=False)
        reference_font.close()
        for weight in WEIGHTS:
            for italic in (False, True):
                source_style = (
                    "Italic"
                    if italic and weight.source == "Regular"
                    else weight.source + ("Italic" if italic else "")
                )
                font = open_face(args.source, indexes[source_style])
                bdf_path = (
                    args.regular_bdf if weight.source == "Regular" else args.bold_bdf
                )
                glyph_names = text_glyph_names(font, bdf_path)
                if not weight.keep_hints:
                    label = weight.name + ("Italic" if italic else "")
                    font = change_text_weight(
                        font,
                        weight.delta,
                        glyph_names,
                        temporary,
                        label,
                        italic,
                    )
                    font = autohint_weighted_face(
                        font,
                        glyph_names,
                        temporary,
                        label,
                        reference_path,
                    )
                rename_face(font, args.family, weight, italic)
                built.append(font)
                print(f"Built {weight.name}{' Italic' if italic else ''}", flush=True)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        collection = TTCollection()
        collection.fonts = built
        collection.save(args.output, shareTables=True)
        collection.close()
        for font in built:
            font.close()

    print(f"Built {args.output} with {len(WEIGHTS) * 2} faces")


if __name__ == "__main__":
    main()
