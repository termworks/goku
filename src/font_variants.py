"""Create static Goku RIBBI faces with consistent terminal metrics."""

from __future__ import annotations

import math

from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from design import (
    ASCENT,
    CELL_WIDTH,
    DESCENT,
    FONT_TIMESTAMP,
    ITALIC_OVERHANG,
    POWERLINE_RANGES,
    VERSION,
)
from icon_optical_policy import OPTICAL_SCALE_BY_CODEPOINT


ITALIC_ANGLE = 12.0


def is_private_use(codepoint: int) -> bool:
    return (
        0xE000 <= codepoint <= 0xF8FF
        or 0xF0000 <= codepoint <= 0xFFFFD
        or 0x100000 <= codepoint <= 0x10FFFD
    )


def is_powerline(codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in POWERLINE_RANGES)


def transform_glyph_x(
    font: TTFont,
    name: str,
    scale: float,
    offset: float,
) -> None:
    """Apply a horizontal transform and refresh the glyph's side bearing."""
    transform_glyph(font, name, (scale, 0, 0, 1, offset, 0))


def transform_glyph(
    font: TTFont,
    name: str,
    matrix: tuple[float, float, float, float, float, float],
) -> None:
    """Replace a glyph with a transformed outline and refresh its bearing."""
    glyf = font["glyf"]
    pen = TTGlyphPen(font.getGlyphSet())
    transform = TransformPen(pen, matrix)
    font.getGlyphSet()[name].draw(transform)
    glyph = pen.glyph()
    glyph.recalcBounds(glyf)
    glyf[name] = glyph
    advance, _ = font["hmtx"].metrics[name]
    font["hmtx"].metrics[name] = (advance, glyph.xMin)


def apply_optical_icon_policy(font: TTFont) -> int:
    """Uniformly shrink measured upper-size outliers around the cell center."""
    cmap = font.getBestCmap()
    center_x = CELL_WIDTH / 2
    center_y = (ASCENT + DESCENT) / 2
    changed = 0
    missing: list[int] = []
    for codepoint, scale in sorted(OPTICAL_SCALE_BY_CODEPOINT.items()):
        name = cmap.get(codepoint)
        if name is None:
            missing.append(codepoint)
            continue
        assert 0 < scale <= 1
        transform_glyph(
            font,
            name,
            (
                scale,
                0,
                0,
                scale,
                center_x * (1 - scale),
                center_y * (1 - scale),
            ),
        )
        changed += 1
    if missing:
        labels = ", ".join(f"U+{codepoint:04X}" for codepoint in missing)
        raise ValueError(f"optical policy glyphs missing from patched font: {labels}")
    print(f"  optically normalized {changed} measured icon outliers", flush=True)
    return changed


def fit_glyphs_horizontally(
    font: TTFont,
    glyph_names: set[str],
    left: int,
    right: int,
) -> int:
    """Fit selected outlines into a horizontal safety region."""
    changed = 0
    glyf = font["glyf"]
    # Leave one font unit of rounding headroom on either side. TransformPen
    # ultimately quantizes coordinates to integers, and an exact-edge fit can
    # otherwise land one unit outside the requested envelope.
    safe_left = left + 1
    safe_right = right - 1
    target_width = safe_right - safe_left
    target_center = (safe_left + safe_right) / 2
    for name in sorted(glyph_names):
        glyph = glyf[name]
        if glyph.numberOfContours == 0:
            continue
        glyph.recalcBounds(glyf)
        if glyph.xMin >= left and glyph.xMax <= right:
            continue
        width = glyph.xMax - glyph.xMin
        scale = min(1.0, target_width / width)
        center = (glyph.xMin + glyph.xMax) / 2
        offset = target_center - scale * center
        transform_glyph_x(font, name, scale, offset)
        fitted = glyf[name]
        fitted.recalcBounds(glyf)
        assert left <= fitted.xMin and fitted.xMax <= right, (
            f"failed to fit {name}: {fitted.xMin}..{fitted.xMax} "
            f"outside {left}..{right}"
        )
        changed += 1
    return changed


def normalize_nerd_icons(font: TTFont) -> int:
    """Fit ordinary Nerd icons to one cell while preserving Powerline bleed."""
    cmap = font.getBestCmap()
    protected = {
        name for codepoint, name in cmap.items() if is_powerline(codepoint)
    }
    icons = {
        name
        for codepoint, name in cmap.items()
        if is_private_use(codepoint) and name not in protected
    }
    changed = fit_glyphs_horizontally(font, icons, 0, CELL_WIDTH)
    print(f"  normalized {changed} overflowing Nerd icons", flush=True)
    return changed


def set_name(font: TTFont, name_id: int, value: str) -> None:
    table = font["name"]
    destinations = {
        (record.platformID, record.platEncID, record.langID)
        for record in table.names
        if record.nameID == name_id
    } or {(3, 1, 0x409)}
    for platform_id, encoding_id, language_id in destinations:
        table.setName(value, name_id, platform_id, encoding_id, language_id)


def vertical_bounds(font: TTFont) -> tuple[int, int]:
    glyf = font["glyf"]
    minima: list[int] = []
    maxima: list[int] = []
    for name in font.getGlyphOrder():
        glyph = glyf[name]
        if glyph.numberOfContours == 0:
            continue
        glyph.recalcBounds(glyf)
        minima.append(glyph.yMin)
        maxima.append(glyph.yMax)
    return min(minima), max(maxima)


def set_vertical_metrics(font: TTFont) -> None:
    """Use native Gohu line metrics and a non-clipping Windows rectangle."""
    hhea = font["hhea"]
    hhea.ascent = ASCENT
    hhea.descent = DESCENT
    hhea.lineGap = 0

    os2 = font["OS/2"]
    os2.sTypoAscender = ASCENT
    os2.sTypoDescender = DESCENT
    os2.sTypoLineGap = 0
    minimum, maximum = vertical_bounds(font)
    os2.usWinAscent = max(ASCENT, maximum)
    os2.usWinDescent = max(-DESCENT, -minimum)
    os2.fsSelection |= (1 << 7) | (1 << 8)


def set_style(
    font: TTFont,
    family: str,
    postscript_stem: str,
    *,
    bold: bool,
    italic: bool,
) -> None:
    if bold and italic:
        style = "Bold Italic"
        ps_style = "BoldItalic"
    elif bold:
        style = "Bold"
        ps_style = "Bold"
    elif italic:
        style = "Italic"
        ps_style = "Italic"
    else:
        style = "Regular"
        ps_style = "Regular"
    postscript = f"{postscript_stem}-{ps_style}"
    for name_id, value in {
        0: (
            "Goku is derived from GohuFont by Hugo Chargois and includes "
            "glyphs from Nerd Fonts."
        ),
        1: family,
        2: style,
        3: f"{VERSION};GOKU;{postscript}",
        4: f"{family} {style}",
        5: f"Version {VERSION}; Goku",
        6: postscript,
        9: "Hugo Chargois; Goku derivative build by Bresilla",
        10: "Vector 8x14 terminal font derived from GohuFont.",
        13: (
            "Gohu-derived outlines: WTFPL. Nerd Fonts glyphs retain their "
            "respective upstream licenses."
        ),
        16: family,
        17: style,
    }.items():
        set_name(font, name_id, value)

    os2 = font["OS/2"]
    os2.usWeightClass = 700 if bold else 400
    os2.fsSelection &= ~((1 << 0) | (1 << 5) | (1 << 6) | (1 << 9))
    if italic:
        os2.fsSelection |= 1 << 0
    if bold:
        os2.fsSelection |= 1 << 5
    if not bold and not italic:
        os2.fsSelection |= 1 << 6
    font["head"].macStyle = (1 if bold else 0) | (2 if italic else 0)
    font["post"].italicAngle = -ITALIC_ANGLE if italic else 0
    font["hhea"].caretSlopeRise = 1000 if italic else 1
    font["hhea"].caretSlopeRun = (
        round(math.tan(math.radians(ITALIC_ANGLE)) * 1000) if italic else 0
    )
    font["hhea"].caretOffset = 0
    set_vertical_metrics(font)
    font["head"].created = FONT_TIMESTAMP
    font["head"].modified = FONT_TIMESTAMP
    font.recalcTimestamp = False
    if "DSIG" in font:
        del font["DSIG"]


def italicize(font: TTFont, glyph_names: set[str]) -> None:
    """Slant text glyphs while preserving terminal symbols and Nerd icons."""
    skew = math.tan(math.radians(ITALIC_ANGLE))
    # Shear around the vertical center of the em rather than the baseline.
    # This distributes monospace overhang across both sides of the cell.
    x_offset = -round(skew * ((ASCENT + DESCENT) / 2))
    glyf = font["glyf"]
    metrics = font["hmtx"].metrics

    order = font.getGlyphOrder()
    changed = 0
    for name in order:
        if name not in glyph_names:
            continue
        source = glyf[name]
        if source.numberOfContours == 0:
            continue
        if source.isComposite():
            pen = TTGlyphPen(font.getGlyphSet())
            transform = TransformPen(pen, (1, 0, skew, 1, x_offset, 0))
            font.getGlyphSet()[name].draw(transform)
            target = pen.glyph()
            glyf[name] = target
        else:
            source.expand(glyf)
            source.removeHinting()
            for point_index, (x, y) in enumerate(source.coordinates):
                source.coordinates[point_index] = (
                    round(x + skew * y + x_offset),
                    y,
                )
            target = source
        target.recalcBounds(glyf)
        advance, _ = metrics[name]
        metrics[name] = (advance, target.xMin)
        changed += 1

    fitted = fit_glyphs_horizontally(
        font,
        glyph_names,
        -ITALIC_OVERHANG,
        CELL_WIDTH + ITALIC_OVERHANG,
    )
    font.recalcBBoxes = True
    font.recalcTimestamp = False
    print(
        f"  italicized {changed} text glyphs; fitted {fitted} overhangs; "
        "kept symbols upright",
        flush=True,
    )
