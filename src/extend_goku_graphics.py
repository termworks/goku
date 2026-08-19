#!/usr/bin/env python3
"""Extend a known-good Goku TTC without modifying any existing glyph."""

from __future__ import annotations

import argparse
from pathlib import Path

from fontTools.ttLib import TTCollection

from terminal_graphics import apply_native_terminal_graphics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    collection = TTCollection(args.baseline)
    results = [
        apply_native_terminal_graphics(font, preserve_existing=True)
        for font in collection.fonts
    ]
    assert all(result.replaced == 0 for result in results)
    assert len({result.added for result in results}) == 1
    assert len({result.preserved for result in results}) == 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    collection.save(args.output, shareTables=True)
    collection.close()
    print(f"Built additions-only candidate: {args.output}")
    print(
        f"  added {results[0].added} glyphs per face; "
        f"preserved {results[0].preserved} existing terminal glyphs"
    )


if __name__ == "__main__":
    main()
