#!/usr/bin/env python3
"""Render release artwork with the real Goku TTC faces.

The hero illustration is an input.  Every letter, symbol, and icon layered on
top of it is rendered from Goku.ttc, so specimen images stay truthful to
the font users actually install.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, PngImagePlugin


WIDTH = 1800
INK = "#f6f2df"
MUTED = "#8d99b5"
ORANGE = "#ff7a18"
BLUE = "#79a9ff"
CYAN = "#73e0d1"
PURPLE = "#b58cff"
PINK = "#ff78b4"
BG = "#070a14"
VERSION = "1.300"


class Faces:
    def __init__(self, path: Path) -> None:
        self.path = str(path)
        self.cache: dict[tuple[int, int, bool], ImageFont.FreeTypeFont] = {}

    def get(self, weight: int, size: int, italic: bool = False) -> ImageFont.FreeTypeFont:
        key = (weight, size, italic)
        if key not in self.cache:
            if weight not in range(100, 1000, 100):
                raise ValueError(f"unsupported weight: {weight}")
            index = ((weight // 100) - 1) * 2 + int(italic)
            self.cache[key] = ImageFont.truetype(
                self.path,
                size=size,
                index=index,
                layout_engine=ImageFont.Layout.RAQM,
            )
        return self.cache[key]


def canvas(height: int, upper: tuple[int, int, int], lower: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(1, height - 1)
        eased = t * t * (3 - 2 * t)
        color = tuple(round(a + (b - a) * eased) for a, b in zip(upper, lower))
        draw.line((0, y, WIDTH, y), fill=color)
    for x in range(0, WIDTH, 64):
        draw.line((x, 0, x, height), fill=(20, 27, 49), width=1)
    for y in range(0, height, 64):
        draw.line((0, y, WIDTH, y), fill=(20, 27, 49), width=1)
    return image


def add_grain(image: Image.Image, opacity: float = 0.05) -> None:
    noise = Image.effect_noise(image.size, 18).convert("RGB")
    neutral = Image.new("RGB", image.size, (126, 126, 126))
    noise = Image.blend(neutral, noise, 0.35)
    Image.blend(image, noise, opacity).save("/tmp/goku-artwork-grain.png")
    grained = Image.open("/tmp/goku-artwork-grain.png").convert("RGB")
    image.paste(grained)


def line(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], fill: str, width: int = 2) -> None:
    draw.line(xy, fill=fill, width=width)


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def terminal_cell_height(font: ImageFont.FreeTypeFont) -> int:
    """Return the real line cell implied by the TTC's ascent and descent."""
    ascent, descent = font.getmetrics()
    return ascent + descent


def draw_cell_text(
    draw: ImageDraw.ImageDraw,
    position: tuple[float, float],
    value: str,
    font: ImageFont.FreeTypeFont,
    fill: str | tuple[int, ...],
    *,
    cell_height: int | None = None,
    **kwargs: object,
) -> None:
    """Draw from a measured terminal baseline instead of a guessed y offset."""
    x, y = position
    ascent, descent = font.getmetrics()
    natural_height = ascent + descent
    top = y if cell_height is None else y + (cell_height - natural_height) / 2
    draw.text(
        (x, top + ascent),
        value,
        font=font,
        fill=fill,
        anchor="ls",
        **kwargs,
    )


def fill_terminal_row(
    draw: ImageDraw.ImageDraw,
    left: float,
    right: float,
    top: float,
    height: int,
    fill: str | tuple[int, ...],
) -> None:
    """Fill exactly one terminal row, with no overlap or gap at its edges."""
    x0 = round(left)
    x1 = max(x0, round(right) - 1)
    y0 = round(top)
    y1 = y0 + height - 1
    draw.rectangle((x0, y0, x1, y1), fill=fill)


def glow_text(
    image: Image.Image,
    position: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str,
    glow: str,
    glow_radius: int = 20,
    stroke_width: int = 0,
    stroke_fill: str | None = None,
) -> None:
    glow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    glow_draw.text(position, text, font=font, fill=glow, stroke_width=stroke_width + 2, stroke_fill=glow)
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(glow_radius))
    image.alpha_composite(glow_layer)
    ImageDraw.Draw(image).text(
        position,
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def crop_cover(image: Image.Image, width: int, height: int) -> Image.Image:
    scale = max(width / image.width, height / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def save_png(image: Image.Image, path: Path, description: str) -> None:
    info = PngImagePlugin.PngInfo()
    info.add_text("Title", description)
    info.add_text("Font", f"Goku {VERSION}")
    info.add_text("Typography", "Rendered directly from Goku.ttc")
    image.convert("RGB").save(path, format="PNG", optimize=True, pnginfo=info)


def specimen_canvas(height: int) -> Image.Image:
    """A restrained screen surface without fake window chrome or cards."""
    image = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(image)
    upper = (10, 13, 23)
    lower = (6, 8, 15)
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(upper, lower))
        draw.line((0, y, WIDTH, y), fill=color)
    draw.rectangle((48, 0, 52, height), fill=(29, 38, 61))
    return image.convert("RGBA")


def section_heading(
    draw: ImageDraw.ImageDraw,
    faces: Faces,
    x: int,
    y: int,
    label: str,
    color: str,
    width: int,
) -> None:
    draw.text((x, y), label, font=faces.get(700, 27), fill=color)
    line(draw, (x, y + 45, x + width, y + 45), color, 2)


def draw_powerline_prompt(
    draw: ImageDraw.ImageDraw,
    faces: Faces,
    x: float,
    y: float,
    segments: list[tuple[str, str, str]],
    size: int = 38,
    opening: bool = True,
) -> float:
    """Render modules on the TTC's exact line cell and baseline."""
    font = faces.get(600, size)
    cursor = x
    height = terminal_cell_height(font)
    top = round(y)
    bottom = round(y + height) - 1

    def fill_cell(start: float, end: float, color: str) -> None:
        left = round(start)
        right = max(left, round(end) - 1)
        draw.rectangle((left, top, right, bottom), fill=color)

    if opening:
        opening_width = draw.textlength("", font=font)
        draw_cell_text(draw, (cursor, y), "", font, segments[0][1])
        cursor += opening_width

    for index, (value, background, foreground) in enumerate(segments):
        value_width = draw.textlength(value, font=font)
        fill_cell(cursor, cursor + value_width, background)
        draw_cell_text(draw, (cursor, y), value, font, foreground)
        cursor += value_width

        separator = ""
        separator_width = draw.textlength(separator, font=font)
        next_background = segments[index + 1][1] if index + 1 < len(segments) else BG
        fill_cell(cursor, cursor + separator_width, next_background)
        draw_cell_text(draw, (cursor, y), separator, font, background)
        cursor += separator_width
    return cursor


def render_header(faces: Faces, hero_path: Path, output: Path) -> None:
    hero = crop_cover(Image.open(hero_path).convert("RGB"), WIDTH, 900)
    hero = ImageEnhance.Contrast(hero).enhance(1.08)
    image = hero.convert("RGBA")

    shade = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pixels = shade.load()
    for y in range(shade.height):
        for x in range(shade.width):
            left_alpha = max(0.0, 1.0 - x / 1180.0)
            bottom_alpha = max(0.0, (y - 600) / 300.0)
            alpha = min(215, round(185 * left_alpha + 50 * bottom_alpha))
            pixels[x, y] = (4, 6, 18, alpha)
    image.alpha_composite(shade)
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((104, 100, 520, 151), radius=9, fill=(8, 12, 30, 215), outline=ORANGE, width=2)
    draw.text((126, 113), f"PIXEL TERMINAL // {VERSION}", font=faces.get(600, 28), fill=INK)

    title_font = faces.get(900, 255)
    draw.text((116, 236), "GOKU", font=title_font, fill="#2a0c08", stroke_width=15, stroke_fill="#2a0c08")
    draw.text((101, 220), "GOKU", font=title_font, fill=INK, stroke_width=5, stroke_fill=ORANGE)
    line(draw, (110, 498, 760, 498), ORANGE, 7)
    line(draw, (110, 511, 560, 511), BLUE, 3)

    draw.text((110, 552), "CODE AT FULL POWER.", font=faces.get(600, 50), fill=INK)
    draw.text((110, 618), "Nine weights. True italics. Fresh small-size hinting.", font=faces.get(200, 34), fill="#c9d3ee")
    draw.text((110, 666), "Every outline pixel-built. Every descender protected.", font=faces.get(200, 30, True), fill=BLUE)

    x = 110
    for weight in range(100, 1000, 100):
        label = str(weight)
        w, _ = text_size(draw, label, faces.get(weight, 26))
        draw.rounded_rectangle((x, 750, x + 78, 798), radius=8, fill=(8, 12, 27, 210), outline=(65, 78, 115, 255), width=1)
        draw.text((x + (78 - w) / 2, 762), label, font=faces.get(weight, 26), fill=INK)
        x += 88

    draw.text((111, 830), "Agjy  0O  1Il  {}[]()  ->  !=  <=  >=   ", font=faces.get(400, 30), fill="#a8b7da")
    save_png(image, output, "Goku font hero header")


def render_weights(faces: Faces, output: Path) -> None:
    image = specimen_canvas(860)
    draw = ImageDraw.Draw(image)
    draw.text((88, 56), "GOKU / WEIGHT PROOF", font=faces.get(800, 64), fill=INK)
    draw.text((92, 133), "The same terminal line at every shipped weight. No synthetic names.", font=faces.get(200, 29), fill=BLUE)
    line(draw, (92, 190, 1708, 190), ORANGE, 3)
    draw.text((92, 215), "WEIGHT", font=faces.get(600, 24), fill=MUTED)
    draw.text((242, 215), "UPRIGHT / CODE + AMBIGUOUS GLYPHS", font=faces.get(600, 24), fill=MUTED)
    draw.text((1415, 215), "MATCHING ITALIC", font=faces.get(600, 24), fill=MUTED)

    row_top = 270
    sample_size = 51
    row_height = terminal_cell_height(faces.get(400, sample_size))
    accents = ["#7887a8", "#8297bd", "#78a9d8", "#72c4d4", "#73e0d1", "#a6df79", "#ffd166", "#ff9f43", "#ff6b5f"]
    for row, weight in enumerate(range(100, 1000, 100)):
        y = row_top + row * row_height
        if weight in (400, 700):
            fill_terminal_row(draw, 70, 1731, y, row_height, (16, 21, 35, 205))
        line(draw, (92, y + row_height - 1, 1708, y + row_height - 1), "#20283b", 1)
        draw_cell_text(draw, (92, y), f"{weight}", faces.get(700, 30), accents[row], cell_height=row_height)
        draw_cell_text(
            draw,
            (242, y),
            "Goku  Agjy  0O  1Il  {}[]  =>",
            faces.get(weight, sample_size),
            INK,
            cell_height=row_height,
        )
        draw_cell_text(
            draw,
            (1415, y),
            f"// italic {weight}",
            faces.get(weight, 33, True),
            accents[row],
            cell_height=row_height,
        )

    footer_y = row_top + 9 * row_height + 48
    draw.text((92, footer_y), "SOURCE ANCHORS", font=faces.get(700, 24), fill=MUTED)
    draw.text((342, footer_y - 4), "400 / GOHU REGULAR", font=faces.get(400, 28), fill=CYAN)
    draw.text((790, footer_y - 4), "700 / REAL GOHU BOLD", font=faces.get(700, 28), fill=ORANGE)
    draw.text((1360, footer_y - 4), "18 FACES / ONE TTC", font=faces.get(300, 25), fill=MUTED)
    save_png(image, output, "Goku weight and italic specimen")


def render_symbols(faces: Faces, output: Path) -> None:
    image = specimen_canvas(1420)
    draw = ImageDraw.Draw(image)
    draw.text((88, 56), "GOKU / GLYPH COVERAGE", font=faces.get(800, 64), fill=INK)
    draw.text((92, 133), "11,783 mapped codepoints rendered from the shipped TTC.", font=faces.get(200, 29), fill=CYAN)
    line(draw, (92, 190, 1708, 190), ORANGE, 3)
    line(draw, (900, 222, 900, 1302), "#25304a", 2)

    section_heading(draw, faces, 92, 225, "NERD ICONS / GENERAL", ORANGE, 742)
    section_heading(draw, faces, 958, 225, "DEVELOPMENT STACK", PINK, 750)

    nerd_rows = [
        "              ",
        "              ",
        "              ",
    ]
    nerd_font = faces.get(500, 48)
    nerd_line_height = terminal_cell_height(nerd_font)
    for i, value in enumerate(nerd_rows):
        draw_cell_text(draw, (92, 305 + i * nerd_line_height), value, nerd_font, (INK, ORANGE, BLUE)[i])

    dev_rows = [
        "          ",
        "          ",
        "          ",
    ]
    dev_font = faces.get(500, 55)
    dev_line_height = terminal_cell_height(dev_font)
    for i, value in enumerate(dev_rows):
        draw_cell_text(draw, (958, 305 + i * dev_line_height), value, dev_font, (PINK, CYAN, PURPLE)[i])

    section_heading(draw, faces, 92, 585, "TERMINAL GEOMETRY", BLUE, 742)
    section_heading(draw, faces, 958, 585, "POWERLINE CELLS", PURPLE, 750)
    terminal_rows = [
        "┌──────────┬──────────┐",
        "│ blocks   │ ░▒▓█ ▌   │",
        "├──────────┼──────────┤",
        "│ braille  │ ⠋⠙⠹⠸⠼    │",
        "└──────────┴──────────┘",
    ]
    expected_columns = len(terminal_rows[0])
    if any(len(value) != expected_columns for value in terminal_rows):
        raise ValueError("terminal geometry rows must have identical cell counts")
    terminal_font = faces.get(400, 36)
    terminal_line_height = terminal_cell_height(terminal_font)
    for index, value in enumerate(terminal_rows):
        draw_cell_text(
            draw,
            (92, 657 + index * terminal_line_height),
            value,
            terminal_font,
            BLUE if index in (0, 2, 4) else INK,
        )
    draw.text((92, 930), "▁▂▃▄▅▆▇█  ▏▎▍▌▋▊▉█", font=faces.get(500, 39), fill=CYAN)

    draw_cell_text(draw, (958, 675), "        ", faces.get(500, 62), PURPLE)
    draw_powerline_prompt(
        draw,
        faces,
        958,
        785,
        [
            ("  bresilla ", "#9A348E", INK),
            (" ~/goku ", "#DA627D", INK),
            ("  main ", "#FCA17D", "#161821"),
        ],
        size=34,
    )
    draw.text((958, 895), "CONTIGUOUS CELLS / NO GLYPH GAPS", font=faces.get(300, 25), fill=MUTED)

    section_heading(draw, faces, 92, 1030, "MATH / MOTION / LOGIC", CYAN, 742)
    section_heading(draw, faces, 958, 1030, "BRAILLE / LEGACY", ORANGE, 750)
    math_font = faces.get(400, 39)
    math_line_height = terminal_cell_height(math_font)
    math_rows = [
        ("← ↑ → ↓  ↔ ↕  ⇐ ⇒ ⇔", 400, CYAN),
        ("∃ ∅ ∆ ∈ ∊  − ∙ √ ∞ ∟", 500, INK),
        ("∧ ∨ ∩ ∪  ≈ ≠ ≡ ≤ ≥", 500, ORANGE),
    ]
    for index, (value, weight, color) in enumerate(math_rows):
        draw_cell_text(
            draw,
            (92, 1105 + index * math_line_height),
            value,
            faces.get(weight, 39),
            color,
            cell_height=math_line_height,
        )

    legacy_size = 45
    legacy_line_height = terminal_cell_height(faces.get(400, legacy_size))
    legacy_rows = [
        ("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏", 300, ORANGE),
        ("🯰🯱🯲🯳🯴🯵🯶🯷🯸🯹", 500, INK),
        ("🬀🬁🬂🬃🬄🬅  🮐🮑🮒🮔", 400, BLUE),
    ]
    for index, (value, weight, color) in enumerate(legacy_rows):
        draw_cell_text(
            draw,
            (958, 1105 + index * legacy_line_height),
            value,
            faces.get(weight, legacy_size),
            color,
            cell_height=legacy_line_height,
        )

    draw.text((92, 1360), "EVERY GLYPH ABOVE IS PRESENT IN GOKU.TTC / FIXED 1170-UNIT CELL", font=faces.get(300, 25), fill=MUTED)
    save_png(image, output, "Goku symbols and Nerd Font icon specimen")


def render_terminal_lab(faces: Faces, output: Path) -> None:
    image = specimen_canvas(1220)
    draw = ImageDraw.Draw(image)
    draw.text((88, 56), "GOKU / REAL PROMPT TEST", font=faces.get(800, 64), fill=INK)
    draw.text((92, 133), "Actual module order, contiguous separators, and two-line prompt behavior.", font=faces.get(200, 29), fill=BLUE)
    line(draw, (92, 190, 1708, 190), ORANGE, 3)

    section_heading(draw, faces, 92, 222, "STARSHIP / PASTEL POWERLINE", PINK, 1616)
    terminal_size = 35
    terminal_line_height = terminal_cell_height(faces.get(400, terminal_size))
    first_row = 292
    draw_powerline_prompt(
        draw,
        faces,
        92,
        292,
        [
            (" bresilla ", "#9A348E", INK),
            (" ~/fontmake ", "#DA627D", INK),
            ("  main +2 ", "#FCA17D", "#161821"),
            ("  v1.88.0 ", "#86BBD8", "#10151e"),
            ("  podman ", "#06969A", INK),
            (" ♥ 14:32 ", "#33658A", INK),
        ],
        size=terminal_size,
    )
    first_rows = [
        ("❯ make all", 300, INK),
        ("Built build/Goku.ttc with 18 faces", 200, CYAN),
        ("HarfBuzz audit passed / code operators stay separate", 200, CYAN),
        ("Validated 211842 non-empty glyph instances", 200, CYAN),
    ]
    for index, (value, weight, color) in enumerate(first_rows, 1):
        draw_cell_text(
            draw,
            (92, first_row + index * terminal_line_height),
            value,
            faces.get(weight, terminal_size),
            color,
            cell_height=terminal_line_height,
        )

    section_heading(draw, faces, 92, 520, "STARSHIP / DEFAULT MODULE FLOW", BLUE, 1616)
    second_row = 590
    draw_segments(
        draw,
        faces,
        92,
        second_row,
        [
            ("~/fontmake", 600, False, CYAN),
            (" on ", 200, False, MUTED),
            (" main", 600, False, PURPLE),
            (" [!?]", 600, False, PINK),
        ],
        size=terminal_size,
        cell_height=terminal_line_height,
    )
    second_rows = [
        ("❯ git status --short", 300, INK),
        (" M src/pixelate_collection.py", 200, ORANGE),
        (" M artwork/05-goku-terminal.png", 200, ORANGE),
    ]
    for index, (value, weight, color) in enumerate(second_rows, 1):
        draw_cell_text(
            draw,
            (92, second_row + index * terminal_line_height),
            value,
            faces.get(weight, terminal_size),
            color,
            cell_height=terminal_line_height,
        )

    section_heading(draw, faces, 92, 780, "POWERLEVEL10K / RAINBOW · TWO LINE", PURPLE, 1616)
    third_row = 850
    draw_powerline_prompt(
        draw,
        faces,
        92,
        third_row,
        [
            ("  ", "#2E5D9F", INK),
            (" ~/fontmake ", "#3465A4", INK),
            ("  main !2 ", "#2E8B57", INK),
            ("  1.88.0 ", "#8057A6", INK),
        ],
        size=terminal_size,
        opening=False,
    )
    right_prompt = "14:32:08    86%"
    right_font = faces.get(300, 29)
    right_width = draw.textlength(right_prompt, font=right_font)
    draw_cell_text(
        draw,
        (1708 - right_width, third_row),
        right_prompt,
        right_font,
        MUTED,
        cell_height=terminal_line_height,
    )
    draw_cell_text(
        draw,
        (92, third_row + terminal_line_height),
        "❯ cargo test",
        faces.get(400, terminal_size),
        CYAN,
        cell_height=terminal_line_height,
    )
    draw_cell_text(
        draw,
        (92, third_row + 2 * terminal_line_height),
        "test result: ok. 28 passed; 0 failed",
        faces.get(200, terminal_size),
        INK,
        cell_height=terminal_line_height,
    )

    section_heading(draw, faces, 92, 1000, "POWERLEVEL10K / LEAN · TRANSIENT", CYAN, 1616)
    fourth_row = 1070
    draw_segments(
        draw,
        faces,
        92,
        fourth_row,
        [
            ("~/fontmake", 600, False, BLUE),
            ("  ", 200, False, INK),
            ("main", 600, False, PURPLE),
            (" !2", 600, False, ORANGE),
            ("  ❯", 500, False, CYAN),
        ],
        size=terminal_size,
        cell_height=terminal_line_height,
    )
    draw_segments(
        draw,
        faces,
        92,
        fourth_row + terminal_line_height,
        [("❯", 500, False, CYAN), (" make release", 200, False, INK)],
        size=terminal_size,
        cell_height=terminal_line_height,
    )
    draw.text((92, 1175), "PROMPTS RENDERED FROM GOKU.TTC / POWERLINE GLYPHS SHARE THE TEXT BASELINE", font=faces.get(300, 23), fill=MUTED)

    save_png(image, output, "Goku real Starship and Powerlevel10k prompt specimen")


def draw_segments(
    draw: ImageDraw.ImageDraw,
    faces: Faces,
    x: float,
    y: float,
    segments: list[tuple[str, int, bool, str]],
    size: int = 39,
    cell_height: int | None = None,
) -> None:
    cursor = x
    for value, weight, italic, color in segments:
        font = faces.get(weight, size, italic)
        draw_cell_text(draw, (cursor, y), value, font, color, cell_height=cell_height)
        cursor += draw.textlength(value, font=font)


def render_code(faces: Faces, output: Path) -> None:
    image = specimen_canvas(740)
    draw = ImageDraw.Draw(image)
    draw.text((88, 50), "src/render.rs", font=faces.get(600, 31), fill=INK)
    draw.text((1450, 54), "GOKU 200 / RUST", font=faces.get(300, 24), fill=MUTED)
    line(draw, (72, 112, 1728, 112), "#29344f", 2)
    draw.text((88, 135), "200 for flow · 600 for structure · 200 italic for comments", font=faces.get(200, 27), fill=BLUE)
    code = [
        [("use", 600, False, PINK), (" goku::{Frame, Scene};", 200, False, INK)],
        [("// The quick brown fox jumps over the lazy dog.", 200, True, MUTED)],
        [("fn", 600, False, PINK), (" render_frame", 500, False, CYAN), ("(scene: &Scene) -> Result<Frame> {", 200, False, INK)],
        [("    let", 600, False, PINK), (" fps = scene.target_fps().clamp(", 200, False, INK), ("30", 500, False, ORANGE), (", ", 200, False, INK), ("240", 500, False, ORANGE), (");", 200, False, INK)],
        [("    // Zero ambiguity: 0O 1Il | [] {} ()", 200, True, MUTED)],
        [("    if", 600, False, PINK), (" scene.is_ready() {", 200, False, INK)],
        [("        Ok", 500, False, CYAN), ("(Frame::new(fps))", 200, False, INK)],
        [("    } else {", 200, False, INK)],
        [("        Err", 500, False, ORANGE), ("(\"charge the renderer\".into())", 200, False, INK)],
        [("    }", 200, False, INK)],
        [("}", 200, False, INK)],
    ]
    start_y = 220
    code_size = 39
    line_height = terminal_cell_height(faces.get(200, code_size))
    active_line = 6
    fill_terminal_row(
        draw,
        70,
        1731,
        start_y + (active_line - 1) * line_height,
        line_height,
        (27, 36, 58, 205),
    )
    line(draw, (152, start_y, 152, start_y + len(code) * line_height), "#25304a", 2)
    for number, segments in enumerate(code, 1):
        y = start_y + (number - 1) * line_height
        num = f"{number:02}"
        draw_cell_text(
            draw,
            (91, y),
            num,
            faces.get(200, 28),
            "#505c78",
            cell_height=line_height,
        )
        if segments:
            draw_segments(draw, faces, 184, y, segments, size=code_size, cell_height=line_height)

    status_top = 700
    fill_terminal_row(draw, 52, 1800, status_top, line_height, (15, 21, 34, 255))
    status_items = [
        (88, "NORMAL 200", 200, False, INK),
        (318, "BOLD 600", 600, False, INK),
        (520, "ITALIC 200", 200, True, INK),
        (775, "BOLD ITALIC 700", 700, True, INK),
        (1375, "  0 ERRORS  ·  14ms", 500, False, CYAN),
    ]
    for x, value, weight, italic, color in status_items:
        draw_cell_text(
            draw,
            (x, status_top),
            value,
            faces.get(weight, 25, italic),
            color,
            cell_height=line_height,
        )
    save_png(image, output, "Goku code and terminal specimen")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--hero", type=Path)
    parser.add_argument(
        "--include-header",
        action="store_true",
        help="also regenerate 01-goku-header.png from --hero",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.include_header and args.hero is None:
        parser.error("--include-header requires --hero")
    args.output.mkdir(parents=True, exist_ok=True)
    faces = Faces(args.font)
    if args.include_header:
        render_header(faces, args.hero, args.output / "01-goku-header.png")
    render_weights(faces, args.output / "02-goku-weights.png")
    render_symbols(faces, args.output / "03-goku-symbols.png")
    render_code(faces, args.output / "04-goku-code.png")
    render_terminal_lab(faces, args.output / "05-goku-terminal.png")


if __name__ == "__main__":
    main()
