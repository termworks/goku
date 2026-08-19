#!/usr/bin/env python3
"""Render nearest-neighbor old/new atlases for Goku icon policy changes."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from fontTools.ttLib import TTCollection
from PIL import Image, ImageDraw, ImageFont

from design import ASCENT, DESCENT, UPM


BACKGROUND = "#16181d"
CELL_BACKGROUND = "#20242b"
GRID = "#3c424d"
FOREGROUND = "#f4f4f5"
MUTED = "#9ca3af"
ACCENT = "#7dd3fc"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--sizes", type=int, nargs="+", default=(10, 14, 20))
    parser.add_argument("--scale", type=int, default=7)
    return parser.parse_args()


def regular_index(path: Path) -> int:
    collection = TTCollection(path)
    for index, font in enumerate(collection.fonts):
        styles = {
            record.toUnicode()
            for record in font["name"].names
            if record.nameID == 2
        }
        if "Regular" in styles:
            return index
    raise ValueError(f"no Regular face in {path}")


def glyph_names(path: Path, codepoints: list[int]) -> dict[int, str]:
    collection = TTCollection(path)
    font = collection.fonts[regular_index(path)]
    cmap = font.getBestCmap()
    return {codepoint: cmap[codepoint] for codepoint in codepoints}


def render_cell(
    font: ImageFont.FreeTypeFont,
    character: str,
    size: int,
    scale: int,
) -> Image.Image:
    margin = 2
    cell_width = math.ceil(font.getlength(character))
    cell_height = math.ceil(size * (ASCENT - DESCENT) / UPM)
    baseline = margin + round(size * ASCENT / UPM)
    raw = Image.new(
        "RGB",
        (cell_width + margin * 2, cell_height + margin * 2),
        CELL_BACKGROUND,
    )
    draw = ImageDraw.Draw(raw)
    draw.rectangle(
        (margin, margin, margin + cell_width - 1, margin + cell_height - 1),
        outline=GRID,
    )
    draw.text(
        (margin, baseline),
        character,
        font=font,
        fill=FOREGROUND,
        anchor="ls",
    )
    return raw.resize(
        (raw.width * scale, raw.height * scale),
        Image.Resampling.NEAREST,
    )


def main() -> None:
    args = parse_args()
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    actions = [
        action for action in policy["actions"] if action["action"] == "scale_down"
    ]
    codepoints = [int(action["codepoint"][2:], 16) for action in actions]
    names = glyph_names(args.baseline, codepoints)
    baseline_index = regular_index(args.baseline)
    candidate_index = regular_index(args.candidate)
    label_font = ImageFont.load_default(size=14)
    small_font = ImageFont.load_default(size=12)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for size in sorted(set(args.sizes)):
        old_font = ImageFont.truetype(
            str(args.baseline), size=size, index=baseline_index
        )
        new_font = ImageFont.truetype(
            str(args.candidate), size=size, index=candidate_index
        )
        sample = render_cell(old_font, chr(codepoints[0]), size, args.scale)
        label_width = 330
        gap = 18
        margin = 20
        header_height = 54
        row_gap = 12
        row_height = max(sample.height, 70) + row_gap
        canvas = Image.new(
            "RGB",
            (
                label_width + sample.width * 2 + gap + margin * 2,
                header_height + row_height * len(actions) + margin,
            ),
            BACKGROUND,
        )
        draw = ImageDraw.Draw(canvas)
        draw.text(
            (margin, 12),
            f"Goku P1 icon comparison — {size}px (nearest-neighbor {args.scale}x)",
            font=label_font,
            fill=FOREGROUND,
        )
        old_x = margin + label_width
        new_x = old_x + sample.width + gap
        draw.text((old_x, 34), "v1.100", font=small_font, fill=MUTED)
        draw.text((new_x, 34), "candidate", font=small_font, fill=ACCENT)

        for row, (action, codepoint) in enumerate(zip(actions, codepoints)):
            y = header_height + row * row_height
            old_cell = render_cell(old_font, chr(codepoint), size, args.scale)
            new_cell = render_cell(new_font, chr(codepoint), size, args.scale)
            label = f"{action['codepoint']}  {names[codepoint]}"
            detail = f"{action['source']}   scale {action['scale']:.3f}"
            draw.text((margin, y + 10), label, font=label_font, fill=FOREGROUND)
            draw.text((margin, y + 31), detail, font=small_font, fill=MUTED)
            canvas.paste(old_cell, (old_x, y))
            canvas.paste(new_cell, (new_x, y))

        output = args.output_dir / f"icon-atlas-{size}px.png"
        canvas.save(output, optimize=True)
        print(f"Rendered {output} ({canvas.width}x{canvas.height})")


if __name__ == "__main__":
    main()
