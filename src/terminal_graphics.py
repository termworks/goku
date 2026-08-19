"""Goku-native, grid-aligned terminal graphics."""

from __future__ import annotations

from dataclasses import dataclass
import math

from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.removeOverlaps import removeOverlaps

from design import ASCENT, CELL_WIDTH, DESCENT, SOURCE_CELL_HEIGHT, UPM, scale_grid


@dataclass(frozen=True)
class GraphicsResult:
    added: int
    replaced: int
    preserved: int
    box_drawing: int
    blocks: int
    braille: int
    legacy: int
    legacy_supplement: int


def rectangle_glyph(rectangles: list[tuple[int, int, int, int]]):
    pen = TTGlyphPen(None)
    for x0, y0, x1, y1 in rectangles:
        if not (x0 < x1 and y0 < y1):
            raise ValueError(f"invalid terminal rectangle {(x0, y0, x1, y1)}")
        pen.moveTo((x0, y0))
        pen.lineTo((x0, y1))
        pen.lineTo((x1, y1))
        pen.lineTo((x1, y0))
        pen.closePath()
    return pen.glyph()


def x_fraction(eighths: int) -> int:
    return scale_grid(eighths, 8, CELL_WIDTH)


def y_fraction(eighths: int) -> int:
    return DESCENT + scale_grid(eighths, 8, UPM)


def pixel_rectangle(x: int, y: int) -> tuple[int, int, int, int]:
    """Map one bottom-origin 8x14 source pixel to the Goku em."""
    return (
        scale_grid(x, 8, CELL_WIDTH),
        DESCENT + scale_grid(y, SOURCE_CELL_HEIGHT, UPM),
        scale_grid(x + 1, 8, CELL_WIDTH),
        DESCENT + scale_grid(y + 1, SOURCE_CELL_HEIGHT, UPM),
    )


def source_rectangle(x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int, int]:
    return (
        scale_grid(x0, 8, CELL_WIDTH),
        DESCENT + scale_grid(y0, SOURCE_CELL_HEIGHT, UPM),
        scale_grid(x1, 8, CELL_WIDTH),
        DESCENT + scale_grid(y1, SOURCE_CELL_HEIGHT, UPM),
    )


def shade_rectangles(level: int) -> list[tuple[int, int, int, int]]:
    """Return exact 25/50/75% nested 2x2 pixel patterns."""
    selected = {
        1: {0},
        2: {0, 3},
        3: {0, 1, 3},
    }[level]
    return [
        pixel_rectangle(x, y)
        for y in range(SOURCE_CELL_HEIGHT)
        for x in range(8)
        if (((y & 1) << 1) | (x & 1)) in selected
    ]


def pixel_pattern_rectangles(predicate) -> list[tuple[int, int, int, int]]:
    """Fill native 8x14 pixels selected by ``predicate(x, y)``."""
    return [
        pixel_rectangle(x, y)
        for y in range(SOURCE_CELL_HEIGHT)
        for x in range(8)
        if predicate(x, y)
    ]


def medium_shade_pixel(x: int, y: int, *, inverse: bool = False) -> bool:
    selected = (((y & 1) << 1) | (x & 1)) in {0, 3}
    return not selected if inverse else selected


def directional_triangle_pixel(direction: str, x: int, y: int) -> bool:
    """Select a cell-centred pixel inside a cardinal quarter triangle."""
    # Work in doubled coordinates so the test is symmetric despite the even
    # 8x14 grid. Positive y points upward, matching font coordinates.
    px = 2 * x + 1 - 8
    py = 2 * y + 1 - SOURCE_CELL_HEIGHT
    x_scaled = px * SOURCE_CELL_HEIGHT
    y_scaled = py * 8
    if direction == "left":
        return x_scaled <= -abs(y_scaled)
    if direction == "right":
        return x_scaled >= abs(y_scaled)
    if direction == "upper":
        return y_scaled >= abs(x_scaled)
    if direction == "lower":
        return y_scaled <= -abs(x_scaled)
    raise ValueError(f"unknown triangle direction: {direction}")


def diagonal_half_triangle_pixel(corner: str, x: int, y: int) -> bool:
    """Select a diagonal half-cell triangle such as U+25E4..U+25E3."""
    # Compare normalized pixel centres without floating point. The diagonals
    # run precisely from cell corner to cell corner.
    x_scaled = (2 * x + 1) * SOURCE_CELL_HEIGHT
    y_scaled = (2 * y + 1) * 8
    extent = 2 * 8 * SOURCE_CELL_HEIGHT
    if corner == "upper_left":
        return y_scaled >= x_scaled
    if corner == "upper_right":
        return y_scaled >= extent - x_scaled
    if corner == "lower_right":
        return y_scaled <= x_scaled
    if corner == "lower_left":
        return y_scaled <= extent - x_scaled
    raise ValueError(f"unknown half triangle corner: {corner}")


def block_rectangles() -> dict[int, list[tuple[int, int, int, int]]]:
    full = (0, DESCENT, CELL_WIDTH, ASCENT)
    rectangles: dict[int, list[tuple[int, int, int, int]]] = {
        0x2580: [(0, y_fraction(4), CELL_WIDTH, ASCENT)],
        0x2588: [full],
        0x2590: [(x_fraction(4), DESCENT, CELL_WIDTH, ASCENT)],
        0x2591: shade_rectangles(1),
        0x2592: shade_rectangles(2),
        0x2593: shade_rectangles(3),
        0x2594: [(0, y_fraction(7), CELL_WIDTH, ASCENT)],
        0x2595: [(x_fraction(7), DESCENT, CELL_WIDTH, ASCENT)],
    }
    # Lower one through seven eighths.
    for codepoint, eighths in zip(range(0x2581, 0x2588), range(1, 8)):
        rectangles[codepoint] = [
            (0, DESCENT, CELL_WIDTH, y_fraction(eighths))
        ]
    # Left seven through one eighth.
    for codepoint, eighths in zip(range(0x2589, 0x2590), range(7, 0, -1)):
        rectangles[codepoint] = [
            (0, DESCENT, x_fraction(eighths), ASCENT)
        ]

    x_mid = x_fraction(4)
    y_mid = y_fraction(4)
    quadrants = {
        "ul": (0, y_mid, x_mid, ASCENT),
        "ur": (x_mid, y_mid, CELL_WIDTH, ASCENT),
        "ll": (0, DESCENT, x_mid, y_mid),
        "lr": (x_mid, DESCENT, CELL_WIDTH, y_mid),
    }
    quadrant_sets = {
        0x2596: ("ll",),
        0x2597: ("lr",),
        0x2598: ("ul",),
        0x2599: ("ul", "ll", "lr"),
        0x259A: ("ul", "lr"),
        0x259B: ("ul", "ur", "ll"),
        0x259C: ("ul", "ur", "lr"),
        0x259D: ("ur",),
        0x259E: ("ur", "ll"),
        0x259F: ("ur", "ll", "lr"),
    }
    for codepoint, names in quadrant_sets.items():
        rectangles[codepoint] = [quadrants[name] for name in names]
    assert set(rectangles) == set(range(0x2580, 0x25A0))
    return rectangles


def braille_rectangles(pattern: int) -> list[tuple[int, int, int, int]]:
    """Draw Unicode dots 1–8 as separated 2x2 native-grid squares."""
    # Bit order is 1,2,3,4,5,6,7,8. Coordinates are bottom-origin source
    # pixels; Unicode dots 1/4 are the visual top row.
    positions = (
        (1, 11),
        (1, 8),
        (1, 5),
        (5, 11),
        (5, 8),
        (5, 5),
        (1, 2),
        (5, 2),
    )
    rectangles: list[tuple[int, int, int, int]] = []
    for bit, (x, y) in enumerate(positions):
        if pattern & (1 << bit):
            for dy in range(2):
                for dx in range(2):
                    rectangles.append(pixel_rectangle(x + dx, y + dy))
    return rectangles


def bridge(x: int, y: int) -> tuple[int, int, int, int]:
    return (x - 1, y - 1, x + 1, y + 1)


def dashed_rectangles(
    *,
    horizontal: bool,
    heavy: bool,
    dashes: int,
) -> list[tuple[int, int, int, int]]:
    x = [scale_grid(value, 8, CELL_WIDTH) for value in range(9)]
    y = [
        DESCENT + scale_grid(value, SOURCE_CELL_HEIGHT, UPM)
        for value in range(SOURCE_CELL_HEIGHT + 1)
    ]
    if horizontal:
        start, end = 0, CELL_WIDTH
        gap = x[1]
        cross_start, cross_end = (y[6], y[8]) if heavy else (y[7], y[8])
    else:
        start, end = DESCENT, ASCENT
        gap = y[1] - y[0]
        cross_start, cross_end = (x[3], x[5]) if heavy else (x[3], x[4])
    dash = ((end - start) - dashes * gap) / dashes
    rectangles = []
    for index in range(dashes):
        segment_start = round(start + gap / 2 + index * (dash + gap))
        segment_end = round(start + gap / 2 + index * (dash + gap) + dash)
        rectangles.append(
            (segment_start, cross_start, segment_end, cross_end)
            if horizontal
            else (cross_start, segment_start, cross_end, segment_end)
        )
    return rectangles


def diagonal_rectangles(ascending: bool) -> list[tuple[int, int, int, int]]:
    rectangles: list[tuple[int, int, int, int]] = []
    previous_x = None
    for y in range(SOURCE_CELL_HEIGHT):
        x = min(7, y * 8 // SOURCE_CELL_HEIGHT)
        if not ascending:
            x = 7 - x
        rectangles.append(pixel_rectangle(x, y))
        if previous_x is not None and x != previous_x:
            boundary_x = scale_grid(
                max(x, previous_x) if ascending else min(x, previous_x) + 1,
                8,
                CELL_WIDTH,
            )
            boundary_y = DESCENT + scale_grid(y, SOURCE_CELL_HEIGHT, UPM)
            rectangles.append(bridge(boundary_x, boundary_y))
        previous_x = x
    return rectangles


def native_box_rectangles() -> dict[int, list[tuple[int, int, int, int]]]:
    """Replace the 27 non-Gohu box glyphs with cell-contained pixel forms."""
    x = [scale_grid(value, 8, CELL_WIDTH) for value in range(9)]
    y = [
        DESCENT + scale_grid(value, SOURCE_CELL_HEIGHT, UPM)
        for value in range(SOURCE_CELL_HEIGHT + 1)
    ]
    light_h = (y[7], y[8])
    heavy_h = (y[6], y[8])
    light_v = (x[3], x[4])
    heavy_v = (x[3], x[5])
    rectangles = {
        0x2504: dashed_rectangles(horizontal=True, heavy=False, dashes=3),
        0x2505: dashed_rectangles(horizontal=True, heavy=True, dashes=3),
        0x2506: dashed_rectangles(horizontal=False, heavy=False, dashes=3),
        0x2507: dashed_rectangles(horizontal=False, heavy=True, dashes=3),
        0x254C: dashed_rectangles(horizontal=True, heavy=False, dashes=2),
        0x254D: dashed_rectangles(horizontal=True, heavy=True, dashes=2),
        0x254E: dashed_rectangles(horizontal=False, heavy=False, dashes=2),
        0x254F: dashed_rectangles(horizontal=False, heavy=True, dashes=2),
        # One-pixel-radius arcs. The tiny bridge joins only a diagonal corner
        # and is merged away below, keeping the final outline connected.
        0x256D: [
            (x[3], y[0], x[4], y[7]),
            (x[4], y[7], x[8], y[8]),
            bridge(x[4], y[7]),
        ],
        0x256E: [
            (x[3], y[0], x[4], y[7]),
            (x[0], y[7], x[3], y[8]),
            bridge(x[3], y[7]),
        ],
        0x256F: [
            (x[3], y[8], x[4], y[14]),
            (x[0], y[7], x[3], y[8]),
            bridge(x[3], y[8]),
        ],
        0x2570: [
            (x[3], y[8], x[4], y[14]),
            (x[4], y[7], x[8], y[8]),
            bridge(x[4], y[8]),
        ],
        0x2571: diagonal_rectangles(True),
        0x2572: diagonal_rectangles(False),
        0x2574: [(x[0], light_h[0], x[4], light_h[1])],
        0x2575: [(light_v[0], y[7], light_v[1], y[14])],
        0x2576: [(x[4], light_h[0], x[8], light_h[1])],
        0x2577: [(light_v[0], y[0], light_v[1], y[7])],
        0x2578: [(x[0], heavy_h[0], x[4], heavy_h[1])],
        0x2579: [(heavy_v[0], y[7], heavy_v[1], y[14])],
        0x257A: [(x[4], heavy_h[0], x[8], heavy_h[1])],
        0x257B: [(heavy_v[0], y[0], heavy_v[1], y[7])],
        0x257C: [
            (x[0], light_h[0], x[4], light_h[1]),
            (x[4], heavy_h[0], x[8], heavy_h[1]),
        ],
        0x257D: [
            (light_v[0], y[7], light_v[1], y[14]),
            (heavy_v[0], y[0], heavy_v[1], y[7]),
        ],
        0x257E: [
            (x[0], heavy_h[0], x[4], heavy_h[1]),
            (x[4], light_h[0], x[8], light_h[1]),
        ],
        0x257F: [
            (heavy_v[0], y[7], heavy_v[1], y[14]),
            (light_v[0], y[0], light_v[1], y[7]),
        ],
    }
    # U+2573 is the union of the two pixel diagonals.
    rectangles[0x2573] = [
        *diagonal_rectangles(True),
        *diagonal_rectangles(False),
    ]
    assert len(rectangles) == 27
    return rectangles


def sextant_patterns() -> list[int]:
    # Unicode allocates masks 1..62 in binary order, reusing existing Block
    # Elements for the left/right halves (21/42) and the full block (63).
    return [mask for mask in range(1, 63) if mask not in {21, 42}]


def sextant_rectangles(mask: int) -> list[tuple[int, int, int, int]]:
    x = (0, x_fraction(4), CELL_WIDTH)
    y = (
        DESCENT,
        DESCENT + scale_grid(1, 3, UPM),
        DESCENT + scale_grid(2, 3, UPM),
        ASCENT,
    )
    # Unicode sextants: 1/2 top, 3/4 middle, 5/6 bottom.
    positions = (
        (x[0], y[2], x[1], y[3]),
        (x[1], y[2], x[2], y[3]),
        (x[0], y[1], x[1], y[2]),
        (x[1], y[1], x[2], y[2]),
        (x[0], y[0], x[1], y[1]),
        (x[1], y[0], x[2], y[1]),
    )
    return [rectangle for bit, rectangle in enumerate(positions) if mask & (1 << bit)]


def diagonal_mosaic_rectangles(
    side: str,
    start: str,
    end: str,
) -> list[tuple[int, int, int, int]]:
    """Fill the named side of a Unicode smooth-mosaic diagonal."""
    # Coordinates are multiplied by six: thirds and pixel centres therefore
    # remain exact integers on the 8x14 source grid.
    points = {
        "lower_left": (0, 0),
        "lower_middle_left": (0, 28),
        "upper_middle_left": (0, 56),
        "upper_left": (0, 84),
        "lower_centre": (24, 0),
        "upper_centre": (24, 84),
        "lower_right": (48, 0),
        "lower_middle_right": (48, 28),
        "upper_middle_right": (48, 56),
        "upper_right": (48, 84),
    }
    side_points = {
        "lower_left": points["lower_left"],
        "lower_right": points["lower_right"],
        "upper_left": points["upper_left"],
        "upper_right": points["upper_right"],
    }
    x0, y0 = points[start]
    x1, y1 = points[end]

    def cross(x: int, y: int) -> int:
        return (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)

    side_cross = cross(*side_points[side])
    assert side_cross != 0, (side, start, end)
    def selected(x: int, y: int) -> bool:
        value = cross((2 * x + 1) * 3, (2 * y + 1) * 3) * side_cross
        # A source-pixel centre can land exactly on the mathematical diagonal.
        # Give that pixel to the lower member of each complementary pair so
        # the two mosaics tile the cell with neither a hole nor an overlap.
        return value > 0 or (value == 0 and side.startswith("lower"))

    return pixel_pattern_rectangles(selected)


def legacy_diagonal_mosaic_rectangles() -> dict[int, list[tuple[int, int, int, int]]]:
    """U+1FB3C..U+1FB67 diagonal mosaics from their Unicode endpoints."""
    specs = (
        ("lower_left", "lower_middle_left", "lower_centre"),
        ("lower_left", "lower_middle_left", "lower_right"),
        ("lower_left", "upper_middle_left", "lower_centre"),
        ("lower_left", "upper_middle_left", "lower_right"),
        ("lower_left", "upper_left", "lower_centre"),
        ("lower_right", "upper_middle_left", "upper_centre"),
        ("lower_right", "upper_middle_left", "upper_right"),
        ("lower_right", "lower_middle_left", "upper_centre"),
        ("lower_right", "lower_middle_left", "upper_right"),
        ("lower_right", "lower_left", "upper_centre"),
        ("lower_right", "lower_middle_left", "upper_middle_right"),
        ("lower_right", "lower_centre", "lower_middle_right"),
        ("lower_right", "lower_left", "lower_middle_right"),
        ("lower_right", "lower_centre", "upper_middle_right"),
        ("lower_right", "lower_left", "upper_middle_right"),
        ("lower_right", "lower_centre", "upper_right"),
        ("lower_left", "upper_centre", "upper_middle_right"),
        ("lower_left", "upper_left", "upper_middle_right"),
        ("lower_left", "upper_centre", "lower_middle_right"),
        ("lower_left", "upper_left", "lower_middle_right"),
        ("lower_left", "upper_centre", "lower_right"),
        ("lower_left", "upper_middle_left", "lower_middle_right"),
        ("upper_right", "lower_middle_left", "lower_centre"),
        ("upper_right", "lower_middle_left", "lower_right"),
        ("upper_right", "upper_middle_left", "lower_centre"),
        ("upper_right", "upper_middle_left", "lower_right"),
        ("upper_right", "upper_left", "lower_centre"),
        ("upper_left", "upper_middle_left", "upper_centre"),
        ("upper_left", "upper_middle_left", "upper_right"),
        ("upper_left", "lower_middle_left", "upper_centre"),
        ("upper_left", "lower_middle_left", "upper_right"),
        ("upper_left", "lower_left", "upper_centre"),
        ("upper_left", "lower_middle_left", "upper_middle_right"),
        ("upper_left", "lower_centre", "lower_middle_right"),
        ("upper_left", "lower_left", "lower_middle_right"),
        ("upper_left", "lower_centre", "upper_middle_right"),
        ("upper_left", "lower_left", "upper_middle_right"),
        ("upper_left", "lower_centre", "upper_right"),
        ("upper_right", "upper_centre", "upper_middle_right"),
        ("upper_right", "upper_left", "upper_middle_right"),
        ("upper_right", "upper_centre", "lower_middle_right"),
        ("upper_right", "upper_left", "lower_middle_right"),
        ("upper_right", "upper_centre", "lower_right"),
        ("upper_right", "upper_middle_left", "lower_middle_right"),
    )
    assert len(specs) == 44
    return {
        0x1FB3C + index: diagonal_mosaic_rectangles(*spec)
        for index, spec in enumerate(specs)
    }


def legacy_eighth_rectangles() -> dict[int, list[tuple[int, int, int, int]]]:
    rectangles: dict[int, list[tuple[int, int, int, int]]] = {}
    # Vertical strips 2..7; strips 1 and 8 already exist as U+258F/U+2595.
    for codepoint, position in zip(range(0x1FB70, 0x1FB76), range(2, 8)):
        rectangles[codepoint] = [
            (x_fraction(position - 1), DESCENT, x_fraction(position), ASCENT)
        ]
    # Horizontal strips 2..7, numbered top to bottom.
    for codepoint, position in zip(range(0x1FB76, 0x1FB7C), range(2, 8)):
        lower = 8 - position
        rectangles[codepoint] = [
            (0, y_fraction(lower), CELL_WIDTH, y_fraction(lower + 1))
        ]
    left = (0, DESCENT, x_fraction(1), ASCENT)
    right = (x_fraction(7), DESCENT, CELL_WIDTH, ASCENT)
    lower = (0, DESCENT, CELL_WIDTH, y_fraction(1))
    upper = (0, y_fraction(7), CELL_WIDTH, ASCENT)
    rectangles.update(
        {
            0x1FB7C: [left, lower],
            0x1FB7D: [left, upper],
            0x1FB7E: [right, upper],
            0x1FB7F: [right, lower],
            0x1FB80: [upper, lower],
            0x1FB81: [
                (0, y_fraction(7), CELL_WIDTH, y_fraction(8)),
                (0, y_fraction(5), CELL_WIDTH, y_fraction(6)),
                (0, y_fraction(3), CELL_WIDTH, y_fraction(4)),
                (0, y_fraction(0), CELL_WIDTH, y_fraction(1)),
            ],
        }
    )
    for codepoint, eighths in zip(range(0x1FB82, 0x1FB87), (2, 3, 5, 6, 7)):
        rectangles[codepoint] = [
            (0, y_fraction(8 - eighths), CELL_WIDTH, ASCENT)
        ]
    for codepoint, eighths in zip(range(0x1FB87, 0x1FB8C), (2, 3, 5, 6, 7)):
        rectangles[codepoint] = [
            (x_fraction(8 - eighths), DESCENT, CELL_WIDTH, ASCENT)
        ]
    assert len(rectangles) == 28
    return rectangles


def legacy_triangular_block_rectangles() -> dict[int, list[tuple[int, int, int, int]]]:
    """U+1FB68..U+1FB6F cardinal quarter and three-quarter triangles."""
    directions = ("left", "upper", "right", "lower")
    quarter: dict[str, list[tuple[int, int, int, int]]] = {
        direction: pixel_pattern_rectangles(
            lambda x, y, direction=direction: directional_triangle_pixel(
                direction, x, y
            )
        )
        for direction in directions
    }
    # The three-quarter forms are exact complements of the quarter triangle
    # named by the missing direction in the Unicode glyph.
    missing = ("left", "upper", "right", "lower")
    rectangles: dict[int, list[tuple[int, int, int, int]]] = {}
    for offset, direction in enumerate(missing):
        rectangles[0x1FB68 + offset] = pixel_pattern_rectangles(
            lambda x, y, direction=direction: not directional_triangle_pixel(
                direction, x, y
            )
        )
    for offset, direction in enumerate(directions):
        rectangles[0x1FB6C + offset] = quarter[direction]
    assert len(rectangles) == 8
    return rectangles


def legacy_shade_and_fill_rectangles() -> dict[int, list[tuple[int, int, int, int]]]:
    """U+1FB8C..U+1FB9F shade, fill and smooth-mosaic glyphs."""
    upper_half = lambda _x, y: y >= SOURCE_CELL_HEIGHT // 2
    lower_half = lambda _x, y: y < SOURCE_CELL_HEIGHT // 2
    left_half = lambda x, _y: x < 4
    right_half = lambda x, _y: x >= 4
    rectangles = {
        0x1FB8C: pixel_pattern_rectangles(
            lambda x, y: left_half(x, y) and medium_shade_pixel(x, y)
        ),
        0x1FB8D: pixel_pattern_rectangles(
            lambda x, y: right_half(x, y) and medium_shade_pixel(x, y)
        ),
        0x1FB8E: pixel_pattern_rectangles(
            lambda x, y: upper_half(x, y) and medium_shade_pixel(x, y)
        ),
        0x1FB8F: pixel_pattern_rectangles(
            lambda x, y: lower_half(x, y) and medium_shade_pixel(x, y)
        ),
        0x1FB90: pixel_pattern_rectangles(
            lambda x, y: medium_shade_pixel(x, y, inverse=True)
        ),
        0x1FB91: pixel_pattern_rectangles(
            lambda x, y: upper_half(x, y)
            or (lower_half(x, y) and medium_shade_pixel(x, y, inverse=True))
        ),
        0x1FB92: pixel_pattern_rectangles(
            lambda x, y: lower_half(x, y)
            or (upper_half(x, y) and medium_shade_pixel(x, y, inverse=True))
        ),
        0x1FB94: pixel_pattern_rectangles(
            lambda x, y: right_half(x, y)
            or (left_half(x, y) and medium_shade_pixel(x, y, inverse=True))
        ),
        # Checkerboard squares are two native pixels wide/high. This keeps the
        # pattern legible at Gohu's intended small terminal sizes.
        0x1FB95: pixel_pattern_rectangles(
            lambda x, y: ((x // 2) + (y // 2)) % 2 == 0
        ),
        0x1FB96: pixel_pattern_rectangles(
            lambda x, y: ((x // 2) + (y // 2)) % 2 == 1
        ),
        0x1FB97: pixel_pattern_rectangles(
            lambda _x, y: y in {1, 2, 6, 7, 11, 12}
        ),
        # Uniform one-pixel diagonal hatching at exactly 25% coverage.
        0x1FB98: pixel_pattern_rectangles(lambda x, y: (x - y) % 4 == 0),
        0x1FB99: pixel_pattern_rectangles(lambda x, y: (x + y) % 4 == 0),
        0x1FB9A: pixel_pattern_rectangles(
            lambda x, y: directional_triangle_pixel("upper", x, y)
            or directional_triangle_pixel("lower", x, y)
        ),
        0x1FB9B: pixel_pattern_rectangles(
            lambda x, y: directional_triangle_pixel("left", x, y)
            or directional_triangle_pixel("right", x, y)
        ),
    }
    for offset, corner in enumerate(
        ("upper_left", "upper_right", "lower_right", "lower_left")
    ):
        rectangles[0x1FB9C + offset] = pixel_pattern_rectangles(
            lambda x, y, corner=corner: diagonal_half_triangle_pixel(corner, x, y)
            and medium_shade_pixel(x, y)
        )
    assert len(rectangles) == 19
    return rectangles


def diagonal_segment_pixels(segment: str) -> list[tuple[int, int]]:
    """Return one of four edge-to-edge half-diagonal pixel paths."""
    if segment.startswith("upper"):
        rows = range(7, SOURCE_CELL_HEIGHT)
        left_x = lambda y: (y - 7) * 4 // 7
    else:
        rows = range(0, 7)
        left_x = lambda y: (6 - y) * 4 // 7
    pixels = [(left_x(y), y) for y in rows]
    if segment.endswith("right"):
        pixels = [(7 - x, y) for x, y in pixels]
    return pixels


def pixel_path_rectangles(pixels: list[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    """Turn diagonal pixels into a corner-connected vector path."""
    rectangles = [pixel_rectangle(x, y) for x, y in pixels]
    for (x0, y0), (x1, y1) in zip(pixels, pixels[1:]):
        if abs(x1 - x0) == 1 and abs(y1 - y0) == 1:
            boundary_x = scale_grid(max(x0, x1), 8, CELL_WIDTH)
            boundary_y = DESCENT + scale_grid(max(y0, y1), SOURCE_CELL_HEIGHT, UPM)
            rectangles.append(bridge(boundary_x, boundary_y))
    return rectangles


def legacy_diagonal_box_rectangles() -> dict[int, list[tuple[int, int, int, int]]]:
    """Complete U+1FBA0..U+1FBAF using Goku's native line grid."""
    segment_pixels = {
        "ul": diagonal_segment_pixels("upper_left"),
        "ur": diagonal_segment_pixels("upper_right"),
        "ll": diagonal_segment_pixels("lower_left"),
        "lr": diagonal_segment_pixels("lower_right"),
    }
    recipes = {
        0x1FBA0: ("ul",),
        0x1FBA1: ("ur",),
        0x1FBA2: ("ll",),
        0x1FBA3: ("lr",),
        0x1FBA4: ("ul", "ll"),
        0x1FBA5: ("ur", "lr"),
        0x1FBA6: ("ll", "lr"),
        0x1FBA7: ("ul", "ur"),
        0x1FBA8: ("ul", "lr"),
        0x1FBA9: ("ur", "ll"),
        0x1FBAA: ("ur", "lr", "ll"),
        0x1FBAB: ("ul", "ll", "lr"),
        0x1FBAC: ("ul", "ur", "lr"),
        0x1FBAD: ("ur", "ul", "ll"),
        0x1FBAE: ("ul", "ur", "ll", "lr"),
    }
    rectangles = {
        codepoint: [
            rectangle
            for name in names
            for rectangle in pixel_path_rectangles(segment_pixels[name])
        ]
        for codepoint, names in recipes.items()
    }
    y_mid = DESCENT + scale_grid(7, SOURCE_CELL_HEIGHT, UPM)
    x_mid = x_fraction(4)
    rectangles[0x1FBAF] = [
        (0, y_mid, CELL_WIDTH, y_mid + scale_grid(1, SOURCE_CELL_HEIGHT, UPM)),
        (
            x_mid - scale_grid(1, 8, CELL_WIDTH) // 2,
            y_mid - scale_grid(1, SOURCE_CELL_HEIGHT, UPM),
            x_mid + scale_grid(1, 8, CELL_WIDTH) // 2,
            y_mid + 2 * scale_grid(1, SOURCE_CELL_HEIGHT, UPM),
        ),
    ]
    assert len(rectangles) == 16
    return rectangles


def raster_line_pixels(
    start: tuple[int, int],
    end: tuple[int, int],
) -> list[tuple[int, int]]:
    """Sample an edge-to-edge source-grid line as an ordered pixel path."""
    x0, y0 = start
    x1, y1 = end
    steps = max(abs(x1 - x0), abs(y1 - y0)) * 4
    pixels: list[tuple[int, int]] = []
    for index in range(steps + 1):
        x = x0 + (x1 - x0) * index / steps
        y = y0 + (y1 - y0) * index / steps
        pixel = (
            min(7, max(0, math.floor(x))),
            min(SOURCE_CELL_HEIGHT - 1, max(0, math.floor(y))),
        )
        if not pixels or pixels[-1] != pixel:
            pixels.append(pixel)
    return pixels


def polyline_rectangles(
    points: tuple[tuple[int, int], ...],
) -> list[tuple[int, int, int, int]]:
    return [
        rectangle
        for start, end in zip(points, points[1:])
        for rectangle in pixel_path_rectangles(raster_line_pixels(start, end))
    ]


def legacy_extended_diagonal_box_rectangles() -> dict[int, list[tuple[int, int, int, int]]]:
    """U+1FBD0..U+1FBDF character-cell diagonals."""
    ul = (0, SOURCE_CELL_HEIGHT)
    uc = (4, SOURCE_CELL_HEIGHT)
    ur = (8, SOURCE_CELL_HEIGHT)
    ml = (0, 7)
    mc = (4, 7)
    mr = (8, 7)
    ll = (0, 0)
    lc = (4, 0)
    lr = (8, 0)
    recipes = (
        (mr, ll),
        (ur, ml),
        (ul, mr),
        (ml, lr),
        (ul, lc),
        (uc, lr),
        (ur, lc),
        (uc, ll),
        (ul, mc, ur),
        (ur, mc, lr),
        (ll, mc, lr),
        (ul, mc, ll),
        (ul, lc, ur),
        (ur, ml, lr),
        (ll, uc, lr),
        (ul, mr, ll),
    )
    return {
        0x1FBD0 + offset: polyline_rectangles(points)
        for offset, points in enumerate(recipes)
    }


def circle_pixel_rectangles(
    centre: tuple[int, int],
    *,
    outline: bool,
) -> list[tuple[int, int, int, int]]:
    """Draw a radius-four native-pixel disk or one-pixel circular outline."""
    cx, cy = centre
    outer_squared = 8 * 8
    inner_squared = 6 * 6

    def selected(x: int, y: int) -> bool:
        dx = 2 * x + 1 - 2 * cx
        dy = 2 * y + 1 - 2 * cy
        distance_squared = dx * dx + dy * dy
        return distance_squared <= outer_squared and (
            not outline or distance_squared >= inner_squared
        )

    return pixel_pattern_rectangles(selected)


def legacy_geometric_rectangles() -> dict[int, list[tuple[int, int, int, int]]]:
    """U+1FBCE/U+1FBCF thirds and U+1FBE0..U+1FBEF circles/quarters."""
    x_one_third = scale_grid(1, 3, CELL_WIDTH)
    x_two_thirds = scale_grid(2, 3, CELL_WIDTH)
    x_mid = x_fraction(4)
    y_mid = y_fraction(4)
    x_quarter = x_fraction(2)
    x_three_quarters = x_fraction(6)
    y_quarter = y_fraction(2)
    y_three_quarters = y_fraction(6)
    rectangles = {
        0x1FBCE: [(0, DESCENT, x_two_thirds, ASCENT)],
        0x1FBCF: [(0, DESCENT, x_one_third, ASCENT)],
        0x1FBE0: circle_pixel_rectangles((4, 14), outline=True),
        0x1FBE1: circle_pixel_rectangles((8, 7), outline=True),
        0x1FBE2: circle_pixel_rectangles((4, 0), outline=True),
        0x1FBE3: circle_pixel_rectangles((0, 7), outline=True),
        0x1FBE4: [(x_quarter, y_mid, x_three_quarters, ASCENT)],
        0x1FBE5: [(x_quarter, DESCENT, x_three_quarters, y_mid)],
        0x1FBE6: [(0, y_quarter, x_mid, y_three_quarters)],
        0x1FBE7: [(x_mid, y_quarter, CELL_WIDTH, y_three_quarters)],
        0x1FBE8: circle_pixel_rectangles((4, 14), outline=False),
        0x1FBE9: circle_pixel_rectangles((8, 7), outline=False),
        0x1FBEA: circle_pixel_rectangles((4, 0), outline=False),
        0x1FBEB: circle_pixel_rectangles((0, 7), outline=False),
        0x1FBEC: circle_pixel_rectangles((8, 14), outline=False),
        0x1FBED: circle_pixel_rectangles((0, 0), outline=False),
        0x1FBEE: circle_pixel_rectangles((8, 0), outline=False),
        0x1FBEF: circle_pixel_rectangles((0, 14), outline=False),
    }
    assert len(rectangles) == 18
    return rectangles


def segmented_digit_rectangles(digit: int) -> list[tuple[int, int, int, int]]:
    segments = {
        "a": source_rectangle(1, 12, 7, 13),
        "b": source_rectangle(6, 7, 7, 12),
        "c": source_rectangle(6, 2, 7, 7),
        "d": source_rectangle(1, 1, 7, 2),
        "e": source_rectangle(1, 2, 2, 7),
        "f": source_rectangle(1, 7, 2, 12),
        "g": source_rectangle(1, 6, 7, 7),
    }
    enabled = {
        0: "abcdef",
        1: "bc",
        2: "abdeg",
        3: "abcdg",
        4: "bcfg",
        5: "acdfg",
        6: "acdefg",
        7: "abc",
        8: "abcdefg",
        9: "abcdfg",
    }[digit]
    return [segments[name] for name in enabled]


def native_legacy_rectangles() -> dict[int, list[tuple[int, int, int, int]]]:
    rectangles = {
        0x1FB00 + index: sextant_rectangles(mask)
        for index, mask in enumerate(sextant_patterns())
    }
    rectangles.update(legacy_diagonal_mosaic_rectangles())
    rectangles.update(legacy_triangular_block_rectangles())
    rectangles.update(legacy_eighth_rectangles())
    rectangles.update(legacy_shade_and_fill_rectangles())
    rectangles.update(legacy_diagonal_box_rectangles())
    rectangles.update(legacy_geometric_rectangles())
    rectangles.update(legacy_extended_diagonal_box_rectangles())
    rectangles.update(
        {
            0x1FBF0 + digit: segmented_digit_rectangles(digit)
            for digit in range(10)
        }
    )
    assert len(rectangles) == 219
    return rectangles


def separated_quadrant_rectangles(mask: int) -> list[tuple[int, int, int, int]]:
    half_gap = scale_grid(1, SOURCE_CELL_HEIGHT, UPM) // 2
    x_mid = x_fraction(4)
    y_mid = y_fraction(4)
    positions = (
        (0, y_mid + half_gap, x_mid - half_gap, ASCENT),
        (x_mid + half_gap, y_mid + half_gap, CELL_WIDTH, ASCENT),
        (0, DESCENT, x_mid - half_gap, y_mid - half_gap),
        (x_mid + half_gap, DESCENT, CELL_WIDTH, y_mid - half_gap),
    )
    return [rectangle for bit, rectangle in enumerate(positions) if mask & (1 << bit)]


def native_legacy_supplement_rectangles() -> dict[int, list[tuple[int, int, int, int]]]:
    # Unicode 17 Legacy Computing Supplement separated quadrants.
    return {
        0x1CC20 + mask: separated_quadrant_rectangles(mask)
        for mask in range(1, 16)
    }


def canonical_glyph_name(codepoint: int) -> str:
    return f"uni{codepoint:04X}" if codepoint <= 0xFFFF else f"u{codepoint:05X}"


def add_unicode_mapping(font: TTFont, codepoint: int, glyph_name: str) -> None:
    added = False
    for subtable in font["cmap"].tables:
        if not subtable.isUnicode():
            continue
        if subtable.format == 4 and codepoint > 0xFFFF:
            continue
        subtable.cmap[codepoint] = glyph_name
        added = True
    if not added:
        raise ValueError(f"no cmap subtable can encode U+{codepoint:04X}")


def install_glyph(font: TTFont, codepoint: int, rectangles) -> tuple[bool, str]:
    cmap = font.getBestCmap()
    glyph_name = cmap.get(codepoint)
    added = glyph_name is None
    if added:
        glyph_name = canonical_glyph_name(codepoint)
        if glyph_name in font.getGlyphOrder():
            raise ValueError(f"unencoded glyph name already exists: {glyph_name}")
        font.setGlyphOrder([*font.getGlyphOrder(), glyph_name])
        add_unicode_mapping(font, codepoint, glyph_name)

    glyph = rectangle_glyph(rectangles)
    font["glyf"][glyph_name] = glyph
    if glyph.numberOfContours:
        glyph.recalcBounds(font["glyf"])
        left_side_bearing = glyph.xMin
    else:
        left_side_bearing = 0
    font["hmtx"].metrics[glyph_name] = (CELL_WIDTH, left_side_bearing)
    return added, glyph_name


def install_graphics_set(
    font: TTFont,
    glyphs: dict[int, list[tuple[int, int, int, int]]],
    *,
    preserve_existing: bool,
    clean_overlaps: bool = False,
) -> tuple[int, int, int]:
    """Install generated glyphs, optionally refusing to touch existing ones."""
    added = replaced = preserved = 0
    changed_names: list[str] = []
    for codepoint, rectangles in sorted(glyphs.items()):
        if preserve_existing and codepoint in font.getBestCmap():
            preserved += 1
            continue
        is_added, glyph_name = install_glyph(font, codepoint, rectangles)
        changed_names.append(glyph_name)
        if is_added:
            added += 1
        else:
            replaced += 1
    if clean_overlaps and changed_names:
        removeOverlaps(font, glyphNames=changed_names, removeHinting=True)
    return added, replaced, preserved


def apply_native_terminal_graphics(
    font: TTFont,
    *,
    preserve_existing: bool = False,
) -> GraphicsResult:
    """Generate terminal graphics, with an additions-only safety mode."""
    added = replaced = preserved = 0
    box = native_box_rectangles()
    blocks = block_rectangles()
    braille = {
        0x2800 + pattern: braille_rectangles(pattern)
        for pattern in range(256)
    }
    legacy = native_legacy_rectangles()
    legacy_supplement = native_legacy_supplement_rectangles()

    for glyphs, clean_overlaps in (
        (box, True),
        (blocks, False),
        (braille, False),
        (legacy, True),
        (legacy_supplement, False),
    ):
        set_added, set_replaced, set_preserved = install_graphics_set(
            font,
            glyphs,
            preserve_existing=preserve_existing,
            clean_overlaps=clean_overlaps,
        )
        added += set_added
        replaced += set_replaced
        preserved += set_preserved

    font.recalcBBoxes = True
    font.recalcTimestamp = False
    result = GraphicsResult(
        added=added,
        replaced=replaced,
        preserved=preserved,
        box_drawing=len(box),
        blocks=len(blocks),
        braille=256,
        legacy=len(legacy),
        legacy_supplement=len(legacy_supplement),
    )
    print(
        f"  native terminal graphics: {result.box_drawing} box, "
        f"{result.blocks} blocks, "
        f"{result.braille} braille, {result.legacy} legacy "
        f"and {result.legacy_supplement} Unicode 17 supplement "
        f"({result.added} added, "
        f"{result.replaced} replaced, {result.preserved} preserved)",
        flush=True,
    )
    return result
