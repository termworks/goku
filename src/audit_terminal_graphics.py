#!/usr/bin/env python3
"""Inventory Goku terminal-graphics coverage and outline geometry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fontTools.ttLib import TTCollection

from bdf import load_bdf


RANGES = {
    "box_drawing": list(range(0x2500, 0x2580)),
    "block_elements": list(range(0x2580, 0x25A0)),
    "braille": list(range(0x2800, 0x2900)),
    "legacy_computing": list(range(0x1FB00, 0x1FC00)),
    "legacy_computing_supplement": list(range(0x1CC00, 0x1CEC0)),
    "powerline": [
        *range(0xE0A0, 0xE0A4),
        *range(0xE0B0, 0xE0D8),
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", required=True, type=Path)
    parser.add_argument("--gohu-bdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def bounds(font, glyph_name: str) -> list[int] | None:
    glyph = font["glyf"][glyph_name]
    if glyph.numberOfContours == 0:
        return None
    glyph.recalcBounds(font["glyf"])
    return [glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax]


def main() -> None:
    args = parse_args()
    collection = TTCollection(args.collection)
    font = collection.fonts[0]
    cmap = font.getBestCmap()
    gohu = {glyph.encoding for glyph in load_bdf(args.gohu_bdf).glyphs}
    report = {
        "collection": str(args.collection),
        "face_index": 0,
        "ranges": {},
    }
    for label, codepoints in RANGES.items():
        glyphs = []
        for codepoint in codepoints:
            glyph_name = cmap.get(codepoint)
            glyphs.append(
                {
                    "codepoint": f"U+{codepoint:04X}",
                    "encoded": glyph_name is not None,
                    "gohu_source": codepoint in gohu,
                    "glyph": glyph_name,
                    "bounds": bounds(font, glyph_name) if glyph_name else None,
                }
            )
        encoded = sum(item["encoded"] for item in glyphs)
        source = sum(item["gohu_source"] for item in glyphs)
        report["ranges"][label] = {
            "total": len(codepoints),
            "encoded": encoded,
            "missing": len(codepoints) - encoded,
            "gohu_source": source,
            "glyphs": glyphs,
        }
    collection.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("Terminal-graphics inventory")
    for label, item in report["ranges"].items():
        print(
            f"  {label}: {item['encoded']}/{item['total']} encoded; "
            f"{item['gohu_source']} from Gohu"
        )
    print(f"  report: {args.output}")


if __name__ == "__main__":
    main()
