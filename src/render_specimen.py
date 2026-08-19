#!/usr/bin/env python3
"""Render a deterministic FreeType specimen for visual comparison."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", required=True, type=Path)
    parser.add_argument("--text", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--size", type=int, default=29)
    parser.add_argument("--index", type=int, default=0, help="face index in a TTC")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    text = args.text.read_text(encoding="utf-8").rstrip()
    font = ImageFont.truetype(str(args.font), args.size, index=args.index)
    probe = Image.new("L", (1, 1))
    probe_draw = ImageDraw.Draw(probe)
    left, top, right, bottom = probe_draw.multiline_textbbox(
        (0, 0), text, font=font, spacing=7
    )
    margin = 16
    image = Image.new(
        "L",
        (right - left + margin * 2, bottom - top + margin * 2),
        color=18,
    )
    draw = ImageDraw.Draw(image)
    draw.multiline_text(
        (margin - left, margin - top),
        text,
        font=font,
        fill=238,
        spacing=7,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output, optimize=True)
    print(f"Rendered {args.output} ({image.width}x{image.height})")


if __name__ == "__main__":
    main()
