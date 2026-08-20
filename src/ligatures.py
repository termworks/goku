"""Native-grid programming ligatures for Goku.

The ligatures are original Goku pixel drawings, not borrowed outlines.  Each
replacement keeps exactly as many terminal cells as its input sequence, so
cursor movement, selection, and column geometry remain predictable.
"""

from __future__ import annotations

from dataclasses import dataclass

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont

from bdf import BDFGlyph
from build_bdf_face import make_outline
from design import CELL_WIDTH, SOURCE_CELL_HEIGHT, SOURCE_CELL_WIDTH, UPM


@dataclass(frozen=True)
class Ligature:
    sequence: str
    name: str

    @property
    def cells(self) -> int:
        return len(self.sequence)


LIGATURES = (
    Ligature("!==", "lig.exclam_equal_equal"),
    Ligature("<=>", "lig.less_equal_greater"),
    Ligature("===", "lig.equal_equal_equal"),
    Ligature("<<<", "lig.less_less_less"),
    Ligature(">>>", "lig.greater_greater_greater"),
    Ligature("...", "lig.period_period_period"),
    Ligature("->", "lig.hyphen_greater"),
    Ligature("<-", "lig.less_hyphen"),
    Ligature("=>", "lig.equal_greater"),
    Ligature("<=", "lig.less_equal"),
    Ligature(">=", "lig.greater_equal"),
    Ligature("!=", "lig.exclam_equal"),
    Ligature("==", "lig.equal_equal"),
    Ligature("<>", "lig.less_greater"),
    Ligature("::", "lig.colon_colon"),
    Ligature(":=", "lig.colon_equal"),
    Ligature("&&", "lig.ampersand_ampersand"),
    Ligature("||", "lig.bar_bar"),
    Ligature("++", "lig.plus_plus"),
    Ligature("--", "lig.hyphen_hyphen"),
    Ligature("..", "lig.period_period"),
    Ligature("//", "lig.slash_slash"),
    Ligature("/*", "lig.slash_asterisk"),
    Ligature("*/", "lig.asterisk_slash"),
    Ligature("</", "lig.less_slash"),
    Ligature("/>", "lig.slash_greater"),
    Ligature("<<", "lig.less_less"),
    Ligature(">>", "lig.greater_greater"),
)

LIGATURE_NAMES = frozenset(item.name for item in LIGATURES)
LIGATURE_ADVANCES = {
    item.name: item.cells * CELL_WIDTH
    for item in LIGATURES
}


def add_horizontal(
    pixels: set[tuple[int, int]], x0: int, x1: int, y: int, thickness: int
) -> None:
    for row in range(y, y + thickness):
        for x in range(x0, x1 + 1):
            pixels.add((x, row))


def add_vertical(
    pixels: set[tuple[int, int]], x: int, y0: int, y1: int, thickness: int
) -> None:
    for column in range(x, x + thickness):
        for y in range(y0, y1 + 1):
            pixels.add((column, y))


def add_diagonal(
    pixels: set[tuple[int, int]],
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    thickness: int,
) -> None:
    steps = max(abs(x1 - x0), abs(y1 - y0))
    for index in range(steps + 1):
        x = round(x0 + (x1 - x0) * index / max(1, steps))
        y = round(y0 + (y1 - y0) * index / max(1, steps))
        for offset in range(thickness):
            pixels.add((x, y + offset))


def add_chevron(
    pixels: set[tuple[int, int]],
    center_x: int,
    center_y: int,
    direction: int,
    thickness: int,
    radius: int = 3,
) -> None:
    tip_x = center_x + direction * radius
    tail_x = center_x - direction * radius
    add_diagonal(pixels, tail_x, center_y + radius, tip_x, center_y, thickness)
    add_diagonal(pixels, tip_x, center_y, tail_x, center_y - radius, thickness)


def add_plus(
    pixels: set[tuple[int, int]],
    x: int,
    y: int,
    thickness: int,
    radius: int = 3,
) -> None:
    add_horizontal(pixels, x - radius, x + radius, y, thickness)
    add_vertical(pixels, x, y - radius, y + radius, thickness)


def add_star(
    pixels: set[tuple[int, int]], x: int, y: int, thickness: int
) -> None:
    add_horizontal(pixels, x - 2, x + 2, y, thickness)
    add_vertical(pixels, x, y - 2, y + 2, thickness)
    add_diagonal(pixels, x - 2, y - 2, x + 2, y + 2, thickness)
    add_diagonal(pixels, x - 2, y + 2, x + 2, y - 2, thickness)


def add_arrow(
    pixels: set[tuple[int, int]],
    width: int,
    direction: int,
    thickness: int,
    double: bool = False,
) -> None:
    center_y = 4
    start = 2
    end = width - 3
    head_center = end - 1 if direction > 0 else start + 1
    shaft_start = start if direction > 0 else head_center
    shaft_end = head_center if direction > 0 else end
    rows = (center_y - 1, center_y + 1) if double else (center_y,)
    for y in rows:
        add_horizontal(pixels, shaft_start, shaft_end, y, thickness)
    add_chevron(pixels, head_center, center_y, direction, thickness)


def pixels_for(sequence: str, bold: bool) -> frozenset[tuple[int, int]]:
    width = len(sequence) * SOURCE_CELL_WIDTH
    thickness = 2 if bold else 1
    pixels: set[tuple[int, int]] = set()
    center_y = 4

    if sequence == "->":
        add_arrow(pixels, width, 1, thickness)
    elif sequence == "<-":
        add_arrow(pixels, width, -1, thickness)
    elif sequence == "=>":
        add_arrow(pixels, width, 1, thickness, double=True)
    elif sequence in {"<=", ">="}:
        direction = -1 if sequence == "<=" else 1
        add_chevron(pixels, width // 2, center_y + 1, direction, thickness)
        add_horizontal(pixels, 3, width - 4, 0, thickness)
    elif sequence in {"==", "==="}:
        rows = (3, 6) if sequence == "==" else (1, 4, 7)
        for y in rows:
            add_horizontal(pixels, 2, width - 3, y, thickness)
    elif sequence in {"!=", "!=="}:
        rows = (3, 6) if sequence == "!=" else (1, 4, 7)
        for y in rows:
            add_horizontal(pixels, 2, width - 3, y, thickness)
        add_diagonal(pixels, width // 2 - 3, -1, width // 2 + 3, 9, thickness)
    elif sequence == "<=>":
        add_chevron(pixels, 5, center_y, -1, thickness)
        add_chevron(pixels, width - 6, center_y, 1, thickness)
        add_horizontal(pixels, 5, width - 6, center_y - 1, thickness)
        add_horizontal(pixels, 5, width - 6, center_y + 1, thickness)
    elif sequence == "<>":
        add_chevron(pixels, 5, center_y, -1, thickness)
        add_chevron(pixels, width - 6, center_y, 1, thickness)
    elif sequence in {"<<", ">>", "<<<", ">>>"}:
        direction = -1 if sequence[0] == "<" else 1
        count = len(sequence)
        spacing = 6
        first = (width - spacing * (count - 1)) // 2
        for index in range(count):
            add_chevron(
                pixels,
                first + index * spacing,
                center_y,
                direction,
                thickness,
                radius=2,
            )
    elif sequence == "::":
        for x in (width // 2 - 2, width // 2 + 2):
            for y in (2, 6):
                add_horizontal(pixels, x, x + thickness - 1, y, thickness)
    elif sequence == ":=":
        for y in (2, 7):
            add_horizontal(pixels, 3, 3 + thickness - 1, y, thickness)
        add_horizontal(pixels, 7, width - 3, 3, thickness)
        add_horizontal(pixels, 7, width - 3, 6, thickness)
    elif sequence == "&&":
        add_diagonal(pixels, 3, 1, width // 2, 8, thickness)
        add_diagonal(pixels, width // 2, 8, width - 4, 1, thickness)
    elif sequence == "||":
        add_vertical(pixels, width // 2 - 2, 0, 8, thickness)
        add_vertical(pixels, width // 2 + 2, 0, 8, thickness)
    elif sequence == "++":
        add_plus(pixels, 4, center_y, thickness, radius=2)
        add_plus(pixels, width - 5, center_y, thickness, radius=2)
    elif sequence == "--":
        add_horizontal(pixels, 2, width - 3, center_y, thickness)
    elif sequence in {"..", "..."}:
        count = len(sequence)
        spacing = 4
        first = (width - spacing * (count - 1)) // 2
        for index in range(count):
            x = first + index * spacing
            add_horizontal(pixels, x, x + thickness - 1, 0, thickness)
    elif sequence == "//":
        add_diagonal(pixels, 3, -1, 7, 9, thickness)
        add_diagonal(pixels, width - 8, -1, width - 4, 9, thickness)
    elif sequence in {"/*", "*/"}:
        slash_x = 4 if sequence == "/*" else width - 8
        star_x = width - 5 if sequence == "/*" else 5
        add_diagonal(pixels, slash_x, -1, slash_x + 4, 9, thickness)
        add_star(pixels, star_x, center_y, thickness)
    elif sequence in {"</", "/>"}:
        if sequence == "</":
            add_chevron(pixels, 5, center_y, -1, thickness)
            add_diagonal(pixels, width - 8, -1, width - 4, 9, thickness)
        else:
            add_diagonal(pixels, 3, -1, 7, 9, thickness)
            add_chevron(pixels, width - 6, center_y, 1, thickness)
    else:
        raise ValueError(f"no Goku ligature drawing for {sequence!r}")

    return frozenset(
        (x, y)
        for x, y in pixels
        if 0 <= x < width and -3 <= y < 11
    )


def feature_text(font: TTFont) -> str:
    cmap = font.getBestCmap()
    rules = []
    for item in LIGATURES:
        inputs = []
        for character in item.sequence:
            codepoint = ord(character)
            if codepoint not in cmap:
                raise ValueError(
                    f"ligature {item.sequence!r} needs missing U+{codepoint:04X}"
                )
            inputs.append(cmap[codepoint])
        rules.append(f"  sub {' '.join(inputs)} by {item.name};")
    return (
        "feature ss01 { sub zero by zero.ss01; } ss01;\n"
        "feature calt {\n"
        + "\n".join(rules)
        + "\n} calt;"
    )


def add_programming_ligatures(font: TTFont, bold: bool) -> None:
    existing = set(font.getGlyphOrder())
    collisions = existing & LIGATURE_NAMES
    if collisions:
        raise ValueError(f"ligature glyph names already exist: {sorted(collisions)}")

    order = [*font.getGlyphOrder(), *(item.name for item in LIGATURES)]
    font.setGlyphOrder(order)
    glyf = font["glyf"]
    metrics = font["hmtx"].metrics
    for item in LIGATURES:
        width = item.cells * SOURCE_CELL_WIDTH
        source = BDFGlyph(
            name=item.name,
            encoding=-1,
            dwidth=width,
            width=width,
            height=SOURCE_CELL_HEIGHT,
            x_offset=0,
            y_offset=-3,
            pixels=pixels_for(item.sequence, bold),
        )
        advance = item.cells * CELL_WIDTH
        glyph = make_outline(source, width, SOURCE_CELL_HEIGHT, advance, UPM)
        glyf[item.name] = glyph
        glyph.recalcBounds(glyf)
        metrics[item.name] = (advance, glyph.xMin)

    addOpenTypeFeaturesFromString(font, feature_text(font))
    font.recalcBBoxes = True
    font.recalcTimestamp = False
