#!/usr/bin/env python3
"""Validate Goku's TTC faces and OpenType substitutions with HarfBuzz."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from fontTools.ttLib import TTCollection

from ligatures import LIGATURES


CELL_WIDTH = 1170
EXPECTED_STYLES = [
    str(weight) + (" Italic" if italic else "")
    for weight in range(100, 1000, 100)
    for italic in (False, True)
]
PLAIN_TEXT = "0O1Il|{}[]()->!="
SYMBOL_TEXT = "\ue0b0\uf015\U000f0001"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def names(font, name_id: int) -> set[str]:
    return {
        record.toUnicode()
        for record in font["name"].names
        if record.nameID == name_id
    }


def shape(collection: Path, index: int, text: str, features: str) -> list[dict]:
    output = subprocess.run(
        (
            "hb-shape",
            f"--face-index={index}",
            f"--features={features}",
            "--output-format=json",
            f"--text={text}",
            str(collection),
        ),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(output)


def assert_cells(glyphs: list[dict], expected_count: int) -> None:
    assert len(glyphs) == expected_count, (len(glyphs), expected_count, glyphs)
    assert all(item["ax"] == CELL_WIDTH for item in glyphs), glyphs
    assert all(item["ay"] == 0 for item in glyphs), glyphs


def main() -> None:
    args = parse_args()
    collection = TTCollection(args.collection)
    styles: list[str] = []
    results: list[dict] = []

    for index, font in enumerate(collection.fonts):
        style_matches = names(font, 17) & set(EXPECTED_STYLES)
        assert len(style_matches) == 1, style_matches
        style = style_matches.pop()
        styles.append(style)

        default_zero = shape(args.collection, index, "0", "-ss01")
        dotted_zero = shape(args.collection, index, "0", "ss01")
        plain = shape(args.collection, index, PLAIN_TEXT, "-ss01,-calt")
        symbols = shape(args.collection, index, SYMBOL_TEXT, "-ss01,-calt")

        assert_cells(default_zero, 1)
        assert_cells(dotted_zero, 1)
        assert default_zero[0]["g"] == "zero", default_zero
        assert dotted_zero[0]["g"] == "zero.ss01", dotted_zero
        assert_cells(plain, len(PLAIN_TEXT))
        assert_cells(symbols, len(SYMBOL_TEXT))
        assert all(item["g"] != ".notdef" for item in plain + symbols)

        shaped_ligatures = []
        for ligature in LIGATURES:
            disabled = shape(args.collection, index, ligature.sequence, "-calt")
            enabled = shape(args.collection, index, ligature.sequence, "calt")
            assert_cells(disabled, ligature.cells)
            assert len(enabled) == 1, (ligature.sequence, enabled)
            assert enabled[0]["g"] == ligature.name, (
                ligature.sequence,
                enabled,
            )
            assert enabled[0]["ax"] == ligature.cells * CELL_WIDTH, enabled
            shaped_ligatures.append(ligature.sequence)

        results.append(
            {
                "face_index": index,
                "style": style,
                "default_zero": default_zero[0]["g"],
                "ss01_zero": dotted_zero[0]["g"],
                "plain_glyphs": len(plain),
                "symbol_glyphs": [item["g"] for item in symbols],
                "ligatures": shaped_ligatures,
                "advance": CELL_WIDTH,
            }
        )

    collection.close()
    assert styles == EXPECTED_STYLES, styles
    report = {
        "collection": str(args.collection),
        "harfbuzz": subprocess.run(
            ("hb-shape", "--version"),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "faces": results,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print("HarfBuzz shaping audit passed")
    for result in results:
        print(
            f"  face {result['face_index']} {result['style']}: "
            f"zero -> {result['default_zero']}/{result['ss01_zero']}; "
            f"{len(result['ligatures'])} ligatures; advance {result['advance']}"
        )


if __name__ == "__main__":
    main()
