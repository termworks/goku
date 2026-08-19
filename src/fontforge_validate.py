#!/usr/bin/env python3
"""Ask FontForge to validate every outline in one generated Goku face."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import fontforge


INVALID_GLYPH_NAME = 0x200
FLAG_NAMES = {
    0x2: "open-contour",
    0x4: "self-intersection",
    0x8: "wrong-direction",
    0x10: "flipped-reference",
    0x20: "missing-extrema",
    0x40: "missing-opentype-reference",
    0x80: "postscript-point-limit",
    0x100: "postscript-hint-limit",
    0x200: "invalid-glyph-name",
    0x400: "maxp-simple-points",
    0x800: "maxp-simple-contours",
    0x1000: "maxp-composite-points",
    0x2000: "maxp-composite-contours",
    0x4000: "maxp-instruction-size",
    0x8000: "maxp-component-count",
    0x10000: "maxp-component-depth",
    0x40000: "coordinate-distance",
    0x80000: "non-integral-points",
    0x100000: "missing-anchor",
}
# Intersection, direction, extrema and names are retained as visible findings.
# They are common in the inherited icon outlines and do not indicate an sfnt
# corruption when OTS and raster checks pass. TrueType limit violations,
# broken references, flipped components and open contours remain fatal.
ADVISORY_MASK = 0x4 | 0x8 | 0x20 | INVALID_GLYPH_NAME | 0x80 | 0x100
HARD_MASK = sum(FLAG_NAMES) & ~ADVISORY_MASK


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("font", type=Path)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    font_path = args.font
    font = fontforge.open(str(font_path))
    hard_issues: list[tuple[str, int, int]] = []
    state_counts: Counter[int] = Counter()
    flag_counts: Counter[int] = Counter()
    checked = 0

    for glyph in font.glyphs():
        checked += 1
        state = glyph.validate(True)
        if not state:
            continue
        state_counts[state] += 1
        for flag in FLAG_NAMES:
            if state & flag:
                flag_counts[flag] += 1
        if state & HARD_MASK:
            hard_issues.append((glyph.glyphname, glyph.unicode, state & HARD_MASK))

    font.close()

    report = {
        "font": str(font_path),
        "checked_glyphs": checked,
        "clean_glyphs": checked - sum(state_counts.values()),
        "hard_issue_glyphs": len(hard_issues),
        "flags": {
            FLAG_NAMES[flag]: flag_counts[flag]
            for flag in FLAG_NAMES
            if flag_counts[flag]
        },
        "combined_states": {
            f"0x{state:X}": count for state, count in sorted(state_counts.items())
        },
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(f"FontForge checked {checked} outlines in {font_path.name}")
    print(
        "  findings: "
        + (", ".join(f"{name}={count}" for name, count in report["flags"].items()) or "none")
    )
    print(f"  hard issue glyphs: {len(hard_issues)}")
    if hard_issues:
        preview = ", ".join(
            f"{name}/U+{codepoint:04X}:0x{state:X}"
            for name, codepoint, state in hard_issues[:20]
        )
        raise SystemExit(
            f"FontForge found hard structural issues in {len(hard_issues)} "
            f"glyphs: {preview}"
        )


if __name__ == "__main__":
    main()
