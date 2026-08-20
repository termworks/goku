"""Shared design constants for the Goku terminal font."""

from __future__ import annotations


FAMILY = "Goku"
POSTSCRIPT_STEM = "Goku"
VERSION = "1.301"

# A fixed timestamp makes clean builds byte-for-byte reproducible. TrueType
# timestamps count seconds from 1904-01-01; SOURCE_DATE_EPOCH is Unix time.
SOURCE_DATE_EPOCH = 1704067200  # 2024-01-01 00:00:00 UTC
TRUETYPE_EPOCH_OFFSET = 2082844800
FONT_TIMESTAMP = TRUETYPE_EPOCH_OFFSET + SOURCE_DATE_EPOCH

UPM = 2048
CELL_WIDTH = 1170
SOURCE_CELL_WIDTH = 8
SOURCE_CELL_HEIGHT = 14
SOURCE_ASCENT = 11
SOURCE_DESCENT = 3


def scale_grid(value: int, source_span: int, target_span: int) -> int:
    """Round a bitmap-grid coordinate without ties-to-even behavior."""
    numerator = value * target_span
    if numerator >= 0:
        return (numerator + source_span // 2) // source_span
    return -((-numerator + source_span // 2) // source_span)


# Preserve Gohu's native 11/3 baseline split and make one terminal line equal
# exactly one em. The old 1730/-502 metrics made a 2232-unit line and placed
# the source grid about one raster pixel too low in terminal cells.
ASCENT = scale_grid(SOURCE_ASCENT, SOURCE_CELL_HEIGHT, UPM)
DESCENT = -scale_grid(SOURCE_DESCENT, SOURCE_CELL_HEIGHT, UPM)
assert ASCENT - DESCENT == UPM

X_HEIGHT = scale_grid(7, SOURCE_CELL_HEIGHT, UPM)
CAP_HEIGHT = scale_grid(9, SOURCE_CELL_HEIGHT, UPM)
PIXEL_SIZE = scale_grid(1, SOURCE_CELL_HEIGHT, UPM)
ITALIC_OVERHANG = PIXEL_SIZE
TEXT_HORIZONTAL_MARGIN = PIXEL_SIZE // 2

# Nerd Fonts' Powerline separators intentionally bleed slightly beyond the
# nominal cell to prevent hairline seams. Ordinary icons should not.
POWERLINE_RANGES = (
    (0xE0A0, 0xE0A3),
    (0xE0B0, 0xE0D7),
)

HINTING_RANGE_MIN = 6
HINTING_RANGE_MAX = 13
HINTING_LIMIT = 13
