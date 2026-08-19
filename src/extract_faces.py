#!/usr/bin/env python3
"""Extract deterministic audit-only TTFs from a Goku TTC collection."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from fontTools.ttLib import TTCollection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def style_name(font) -> str:
    names = {
        record.toUnicode()
        for record in font["name"].names
        if record.nameID == 17
    }
    expected = {
        str(weight) + (" Italic" if italic else "")
        for weight in range(100, 1000, 100)
        for italic in (False, True)
    }
    styles = names & expected
    if len(styles) != 1:
        raise ValueError(f"cannot determine one Goku style from {sorted(names)}")
    return styles.pop()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    collection = TTCollection(args.collection)
    outputs: list[Path] = []
    for font in collection.fonts:
        style = style_name(font)
        suffix = re.sub(r"[^A-Za-z0-9]+", "", style)
        output = args.output_dir / f"Goku-{suffix}.ttf"
        font.save(output, reorderTables=False)
        outputs.append(output)
    collection.close()

    if len(outputs) != 18:
        raise SystemExit(f"expected 18 numeric faces, extracted {len(outputs)}")
    print("Extracted audit faces:")
    for output in outputs:
        print(f"  {output}")


if __name__ == "__main__":
    main()
