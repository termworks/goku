"""Minimal, strict BDF reader used by the GohuFont build."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BDFGlyph:
    name: str
    encoding: int
    dwidth: int
    width: int
    height: int
    x_offset: int
    y_offset: int
    pixels: frozenset[tuple[int, int]]


@dataclass(frozen=True)
class BDFFont:
    bounding_box: tuple[int, int, int, int]
    glyphs: tuple[BDFGlyph, ...]


def _parse_glyph(lines: list[str]) -> BDFGlyph:
    name = lines[0].split(maxsplit=1)[1]
    encoding = dwidth = None
    box = None
    bitmap_start = None

    for index, line in enumerate(lines):
        if line.startswith("ENCODING "):
            encoding = int(line.split()[1])
        elif line.startswith("DWIDTH "):
            dwidth = int(line.split()[1])
        elif line.startswith("BBX "):
            box = tuple(map(int, line.split()[1:5]))
        elif line == "BITMAP":
            bitmap_start = index + 1
            break

    if encoding is None or dwidth is None or box is None or bitmap_start is None:
        raise ValueError(f"incomplete BDF glyph: {name}")
    if encoding < 0:
        raise ValueError(f"unencoded glyph is unsupported: {name}")

    width, height, x_offset, y_offset = box
    bitmap = lines[bitmap_start : bitmap_start + height]
    if len(bitmap) != height:
        raise ValueError(f"wrong bitmap height for {name}")

    pixels: set[tuple[int, int]] = set()
    encoded_width = ((width + 7) // 8) * 8
    for row_index, row in enumerate(bitmap):
        bits = int(row, 16)
        for column in range(width):
            mask = 1 << (encoded_width - column - 1)
            if bits & mask:
                x = x_offset + column
                y = y_offset + height - row_index - 1
                pixels.add((x, y))

    return BDFGlyph(
        name=name,
        encoding=encoding,
        dwidth=dwidth,
        width=width,
        height=height,
        x_offset=x_offset,
        y_offset=y_offset,
        pixels=frozenset(pixels),
    )


def load_bdf(path: str | Path) -> BDFFont:
    lines = Path(path).read_text(encoding="ascii").splitlines()
    bounding_box = None
    glyphs: list[BDFGlyph] = []
    current: list[str] | None = None

    for line in lines:
        if line.startswith("FONTBOUNDINGBOX "):
            bounding_box = tuple(map(int, line.split()[1:5]))
        if line.startswith("STARTCHAR "):
            if current is not None:
                raise ValueError("nested STARTCHAR")
            current = [line]
        elif current is not None:
            current.append(line)
            if line == "ENDCHAR":
                glyphs.append(_parse_glyph(current))
                current = None

    if current is not None:
        raise ValueError("unterminated glyph")
    if bounding_box is None:
        raise ValueError("BDF has no FONTBOUNDINGBOX")
    if not glyphs:
        raise ValueError("BDF has no glyphs")

    return BDFFont(
        bounding_box=bounding_box,
        glyphs=tuple(glyphs),
    )
