#!/usr/bin/env python3
"""Render a labeled old/new terminal-graphics comparison sheet."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


BACKGROUND = 18
FOREGROUND = 238
LABEL = 150
SIZES = (10, 14, 20, 29)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", required=True, type=Path)
    parser.add_argument("--new", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def sample_lines() -> list[str]:
    single_dots = "".join(chr(0x2800 + (1 << bit)) for bit in range(8))
    braille_run = "".join(chr(codepoint) for codepoint in range(0x2801, 0x2811))
    braille_dense = "".join(
        chr(codepoint)
        for codepoint in (0x2807, 0x283F, 0x287F, 0x28FF, 0x28F6, 0x28DB)
    )
    sextants = "".join(chr(codepoint) for codepoint in range(0x1FB00, 0x1FB10))
    diagonal_mosaics = [
        "".join(chr(codepoint) for codepoint in range(start, start + 22))
        for start in (0x1FB3C, 0x1FB52)
    ]
    eighths = "".join(chr(codepoint) for codepoint in range(0x1FB70, 0x1FB82))
    triangles = "".join(chr(codepoint) for codepoint in range(0x1FB68, 0x1FB70))
    shades_fills = "".join(
        chr(codepoint)
        for codepoint in (*range(0x1FB8C, 0x1FB93), *range(0x1FB94, 0x1FBA0))
    )
    diagonal_boxes = "".join(chr(codepoint) for codepoint in range(0x1FBA0, 0x1FBB0))
    extended_diagonals = "".join(chr(codepoint) for codepoint in range(0x1FBD0, 0x1FBE0))
    geometric = "".join(chr(codepoint) for codepoint in range(0x1FBE0, 0x1FBF0))
    segmented_digits = "".join(chr(codepoint) for codepoint in range(0x1FBF0, 0x1FBFA))
    separated_quadrants = "".join(chr(codepoint) for codepoint in range(0x1CC21, 0x1CC30))
    return [
        "BOX DASH / ARC / DIAGONAL",
        "┄┅┆┇  ╌╍╎╏  ╭╮╯╰  ╱╲╳",
        "╴╵╶╷ ╸╹╺╻ ╼╽╾╿",
        "BLOCKS / FRACTIONS / SHADES",
        "▁▂▃▄▅▆▇█ ▉▊▋▌▍▎▏",
        "▀▄▌▐▔▕  ░▒▓█",
        "▖▗▘▙▚▛▜▝▞▟",
        "BRAILLE DOT MAPPING",
        single_dots,
        braille_run,
        braille_dense,
        "⣿⣷⣯⣟⡿⢿⠿⠛⠉",
        "LEGACY SEXTANTS / EIGHTHS / TRIANGLES",
        sextants,
        *diagonal_mosaics,
        eighths,
        triangles,
        "SHADES / FILLS / DIAGONAL BOX",
        shades_fills,
        diagonal_boxes,
        extended_diagonals,
        "THIRDS / CIRCLE GEOMETRY",
        chr(0x1FBCE) + chr(0x1FBCF) + "  " + geometric,
        segmented_digits,
        "UNICODE 17 SEPARATED QUADRANTS",
        separated_quadrants,
    ]


def panel(
    body_path: Path,
    label_path: Path,
    size: int,
    title: str,
) -> Image.Image:
    lines = sample_lines()
    font = ImageFont.truetype(str(body_path), size=size, index=0)
    label_font = ImageFont.truetype(str(label_path), size=max(10, size), index=0)
    line_height = size + max(4, size // 3)
    padding = 12
    widths = [font.getlength(line) for line in lines]
    title_width = label_font.getlength(title)
    width = math.ceil(max([title_width, *widths])) + padding * 2
    height = padding * 2 + line_height * (len(lines) + 1)
    image = Image.new("L", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text((padding, padding), title, font=label_font, fill=LABEL)
    y = padding + line_height
    for line in lines:
        draw.text((padding, y), line, font=font, fill=FOREGROUND)
        y += line_height
    return image


def main() -> None:
    args = parse_args()
    rows: list[Image.Image] = []
    gap = 10
    for size in SIZES:
        old = panel(args.old, args.new, size, f"Goku 1.100 — {size}px")
        new = panel(args.new, args.new, size, f"P2 native graphics — {size}px")
        height = max(old.height, new.height)
        row = Image.new("L", (old.width + gap + new.width, height), BACKGROUND)
        row.paste(old, (0, 0))
        row.paste(new, (old.width + gap, 0))
        rows.append(row)

    width = max(row.width for row in rows)
    height = sum(row.height for row in rows) + gap * (len(rows) - 1)
    sheet = Image.new("L", (width, height), BACKGROUND)
    y = 0
    for row in rows:
        sheet.paste(row, (0, y))
        y += row.height + gap
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output, optimize=True)
    print(f"Rendered {args.output} ({sheet.width}x{sheet.height})")


if __name__ == "__main__":
    main()
