#!/usr/bin/env python3
"""Render several font files at terminal-scale sizes for weight comparison."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


SAMPLE = "Goku weight: if (ready) return value_42; 0O1Il | {} [] <>"


def load_font(spec: str, size: int) -> ImageFont.FreeTypeFont:
    path_text, separator, index_text = spec.rpartition("#")
    if separator and index_text.isdigit():
        return ImageFont.truetype(path_text, size, index=int(index_text))
    return ImageFont.truetype(spec, size)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", action="append", nargs=2, metavar=("LABEL", "PATH"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--size", type=int, default=10)
    parser.add_argument("--zoom", type=int, default=5)
    parser.add_argument("--text", default=SAMPLE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.font:
        raise SystemExit("at least one --font LABEL PATH is required")

    margin = 8
    label_width = 78
    row_height = max(18, args.size + 8)
    sample_width = 520
    image = Image.new(
        "RGB",
        (margin * 2 + label_width + sample_width, margin * 2 + row_height * len(args.font)),
        "#121212",
    )
    draw = ImageDraw.Draw(image)
    label_font = ImageFont.load_default()

    for row, (label, path) in enumerate(args.font):
        y = margin + row * row_height
        font = load_font(path, args.size)
        draw.text((margin, y + 2), label, font=label_font, fill="#9a9a9a")
        draw.text((margin + label_width, y), args.text, font=font, fill="#eeeeee")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.zoom > 1:
        image = image.resize(
            (image.width * args.zoom, image.height * args.zoom),
            Image.Resampling.NEAREST,
        )
    image.save(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
