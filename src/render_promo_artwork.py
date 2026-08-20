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
    """Render contiguous Powerline modules with real color-transition cells."""
    font = faces.get(600, size)
    cursor = x
    height = size + 22
    text_y = y + 7

    if opening:
        opening_width = draw.textlength("", font=font)
        draw.text((cursor, text_y), "", font=font, fill=segments[0][1])
        cursor += opening_width

    for index, (value, background, foreground) in enumerate(segments):
        value_width = draw.textlength(value, font=font)
        draw.rectangle((cursor, y, cursor + value_width + 1, y + height), fill=background)
        draw.text((cursor, text_y), value, font=font, fill=foreground)
        cursor += value_width

        separator = ""
        separator_width = draw.textlength(separator, font=font)
        next_background = segments[index + 1][1] if index + 1 < len(segments) else BG
        draw.rectangle((cursor, y, cursor + separator_width + 1, y + height), fill=next_background)
        draw.text((cursor, text_y), separator, font=font, fill=background)
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
    image = specimen_canvas(1180)
    draw = ImageDraw.Draw(image)
    draw.text((88, 56), "GOKU / WEIGHT PROOF", font=faces.get(800, 64), fill=INK)
    draw.text((92, 133), "The same terminal line at every shipped weight. No synthetic names.", font=faces.get(200, 29), fill=BLUE)
    line(draw, (92, 190, 1708, 190), ORANGE, 3)
    draw.text((92, 215), "WEIGHT", font=faces.get(600, 24), fill=MUTED)
    draw.text((242, 215), "UPRIGHT / CODE + AMBIGUOUS GLYPHS", font=faces.get(600, 24), fill=MUTED)
    draw.text((1415, 215), "MATCHING ITALIC", font=faces.get(600, 24), fill=MUTED)

    row_top = 270
    row_height = 91
    accents = ["#7887a8", "#8297bd", "#78a9d8", "#72c4d4", "#73e0d1", "#a6df79", "#ffd166", "#ff9f43", "#ff6b5f"]
    for row, weight in enumerate(range(100, 1000, 100)):
        y = row_top + row * row_height
        if weight in (400, 700):
            draw.rectangle((70, y - 8, 1730, y + 70), fill=(16, 21, 35, 205))
        line(draw, (92, y + 72, 1708, y + 72), "#20283b", 1)
        draw.text((92, y + 10), f"{weight}", font=faces.get(700, 30), fill=accents[row])
        draw.text((242, y), "Goku  Agjy  0O  1Il  {}[]  =>", font=faces.get(weight, 51), fill=INK)
        draw.text((1415, y + 13), f"// italic {weight}", font=faces.get(weight, 33, True), fill=accents[row])

    draw.text((92, 1110), "SOURCE ANCHORS", font=faces.get(700, 24), fill=MUTED)
    draw.text((342, 1106), "400 / GOHU REGULAR", font=faces.get(400, 28), fill=CYAN)
    draw.text((790, 1106), "700 / REAL GOHU BOLD", font=faces.get(700, 28), fill=ORANGE)
    draw.text((1360, 1106), "18 FACES / ONE TTC", font=faces.get(300, 25), fill=MUTED)
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
    for i, value in enumerate(nerd_rows):
        draw.text((92, 305 + i * 78), value, font=faces.get(500, 48), fill=(INK, ORANGE, BLUE)[i])

    dev_rows = [
        "          ",
        "          ",
        "          ",
    ]
    for i, value in enumerate(dev_rows):
        draw.text((958, 305 + i * 78), value, font=faces.get(500, 55), fill=(PINK, CYAN, PURPLE)[i])

    section_heading(draw, faces, 92, 585, "TERMINAL GEOMETRY", BLUE, 742)
    section_heading(draw, faces, 958, 585, "POWERLINE CELLS", PURPLE, 750)
    terminal_rows = [
        "┌──────────┬──────────┐",
        "│ blocks   │ ░▒▓█ ▌   │",
        "├──────────┼──────────┤",
        "│ braille  │ ⠋⠙⠹⠸⠼ │",
        "└──────────┴──────────┘",
    ]
    for index, value in enumerate(terminal_rows):
        draw.text((92, 657 + index * 51), value, font=faces.get(400, 36), fill=BLUE if index in (0, 2, 4) else INK)
    draw.text((92, 930), "▁▂▃▄▅▆▇█  ▏▎▍▌▋▊▉█", font=faces.get(500, 39), fill=CYAN)

    draw.text((958, 675), "        ", font=faces.get(500, 62), fill=PURPLE)
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
    draw.text((92, 1105), "← ↑ → ↓  ↔ ↕  ⇐ ⇒ ⇔", font=faces.get(400, 39), fill=CYAN)
    draw.text((92, 1168), "∃ ∅ ∆ ∈ ∊  − ∙ √ ∞ ∟", font=faces.get(500, 39), fill=INK)
    draw.text((92, 1231), "∧ ∨ ∩ ∪  ≈ ≠ ≡ ≤ ≥", font=faces.get(500, 39), fill=ORANGE)
    draw.text((958, 1102), "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏", font=faces.get(300, 48), fill=ORANGE)
    draw.text((958, 1170), "🯰🯱🯲🯳🯴🯵🯶🯷🯸🯹", font=faces.get(500, 45), fill=INK)
    draw.text((958, 1238), "🬀🬁🬂🬃🬄🬅  🮐🮑🮒🮔", font=faces.get(400, 45), fill=BLUE)

    draw.text((92, 1360), "EVERY GLYPH ABOVE IS PRESENT IN GOKU.TTC / FIXED 1170-UNIT CELL", font=faces.get(300, 25), fill=MUTED)
    save_png(image, output, "Goku symbols and Nerd Font icon specimen")


def render_terminal_lab(faces: Faces, output: Path) -> None:
    image = specimen_canvas(1380)
    draw = ImageDraw.Draw(image)
    draw.text((88, 56), "GOKU / REAL PROMPT TEST", font=faces.get(800, 64), fill=INK)
    draw.text((92, 133), "Actual module order, contiguous separators, and two-line prompt behavior.", font=faces.get(200, 29), fill=BLUE)
    line(draw, (92, 190, 1708, 190), ORANGE, 3)

    section_heading(draw, faces, 92, 222, "STARSHIP / PASTEL POWERLINE", PINK, 1616)
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
        size=35,
    )
    draw.text((92, 377), "❯ make all", font=faces.get(300, 34), fill=INK)
    draw.text((92, 429), "Built build/Goku.ttc with 18 faces", font=faces.get(200, 29), fill=CYAN)
    draw.text((92, 473), "HarfBuzz shaping audit passed / 28 ligatures", font=faces.get(200, 29), fill=CYAN)
    draw.text((92, 517), "Validated 212346 non-empty glyph instances", font=faces.get(200, 29), fill=CYAN)

    section_heading(draw, faces, 92, 585, "STARSHIP / DEFAULT MODULE FLOW", BLUE, 1616)
    draw_segments(
        draw,
        faces,
        92,
        660,
        [
            ("~/fontmake", 600, False, CYAN),
            (" on ", 200, False, MUTED),
            (" main", 600, False, PURPLE),
            (" [!?]", 600, False, PINK),
        ],
        size=36,
    )
    draw.text((92, 715), "❯ git status --short", font=faces.get(300, 34), fill=INK)
    draw.text((92, 766), " M src/ligatures.py", font=faces.get(200, 29), fill=ORANGE)
    draw.text((92, 808), " M artwork/05-goku-terminal.png", font=faces.get(200, 29), fill=ORANGE)

    section_heading(draw, faces, 92, 880, "POWERLEVEL10K / RAINBOW · TWO LINE", PURPLE, 1616)
    draw_powerline_prompt(
        draw,
        faces,
        92,
        950,
        [
            ("  ", "#2E5D9F", INK),
            (" ~/fontmake ", "#3465A4", INK),
            ("  main !2 ", "#2E8B57", INK),
            ("  1.88.0 ", "#8057A6", INK),
        ],
        size=35,
        opening=False,
    )
    right_prompt = "14:32:08    86%"
    right_width = draw.textlength(right_prompt, font=faces.get(300, 29))
    draw.text((1708 - right_width, 966), right_prompt, font=faces.get(300, 29), fill=MUTED)
    draw.text((92, 1033), "❯ cargo test", font=faces.get(400, 35), fill=CYAN)
    draw.text((92, 1086), "test result: ok. 28 passed; 0 failed", font=faces.get(200, 29), fill=INK)

    section_heading(draw, faces, 92, 1160, "POWERLEVEL10K / LEAN · TRANSIENT", CYAN, 1616)
    draw_segments(
        draw,
        faces,
        92,
        1232,
        [
            ("~/fontmake", 600, False, BLUE),
            ("  ", 200, False, INK),
            ("main", 600, False, PURPLE),
            (" !2", 600, False, ORANGE),
            ("  ❯", 500, False, CYAN),
        ],
        size=34,
    )
    draw.text((92, 1290), "❯", font=faces.get(500, 35), fill=CYAN)
    draw.text((135, 1290), "make release", font=faces.get(200, 34), fill=INK)
    draw.text((92, 1340), "PROMPTS RENDERED FROM GOKU.TTC / POWERLINE GLYPHS SHARE THE TEXT BASELINE", font=faces.get(300, 23), fill=MUTED)

    save_png(image, output, "Goku real Starship and Powerlevel10k prompt specimen")


def draw_segments(
    draw: ImageDraw.ImageDraw,
    faces: Faces,
    x: float,
    y: float,
    segments: list[tuple[str, int, bool, str]],
    size: int = 39,
) -> None:
    cursor = x
    for value, weight, italic, color in segments:
        font = faces.get(weight, size, italic)
        draw.text((cursor, y), value, font=font, fill=color)
        cursor += draw.textlength(value, font=font)


def render_code(faces: Faces, output: Path) -> None:
    image = specimen_canvas(1120)
    draw = ImageDraw.Draw(image)
    draw.text((88, 50), "src/render.rs", font=faces.get(600, 31), fill=INK)
    draw.text((1450, 54), "GOKU 200 / RUST", font=faces.get(300, 24), fill=MUTED)
    line(draw, (72, 112, 1728, 112), "#29344f", 2)
    draw.text((88, 135), "200 for flow · 600 for structure · 200 italic for comments", font=faces.get(200, 27), fill=BLUE)
    line(draw, (152, 195, 152, 1000), "#25304a", 2)
    draw.rectangle((70, 500, 1730, 558), fill=(27, 36, 58, 205))
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
    line_height = 64
    for number, segments in enumerate(code, 1):
        y = start_y + (number - 1) * line_height
        num = f"{number:02}"
        draw.text((91, y + 4), num, font=faces.get(200, 28), fill="#505c78")
        if segments:
            draw_segments(draw, faces, 184, y, segments)

    draw.rectangle((52, 1018, 1800, 1120), fill=(15, 21, 34, 255))
    draw.text((88, 1040), "NORMAL 200", font=faces.get(200, 25), fill=INK)
    draw.text((318, 1040), "BOLD 600", font=faces.get(600, 25), fill=INK)
    draw.text((520, 1040), "ITALIC 200", font=faces.get(200, 25, True), fill=INK)
    draw.text((775, 1040), "BOLD ITALIC 700", font=faces.get(700, 25, True), fill=INK)
    draw.text((1375, 1040), "  0 ERRORS  ·  14ms", font=faces.get(500, 25), fill=CYAN)
    save_png(image, output, "Goku code and terminal specimen")


def render_ligatures(faces: Faces, output: Path) -> None:
    image = specimen_canvas(1160)
    draw = ImageDraw.Draw(image)
    draw.text((88, 56), "GOKU / LIGATURE SHAPING", font=faces.get(800, 62), fill=INK)
    draw.text(
        (92, 133),
        "Real code lines with CALT enabled. Every substitution preserves cursor width.",
        font=faces.get(200, 29),
        fill=CYAN,
        features=["calt"],
    )
    line(draw, (92, 190, 1708, 190), ORANGE, 3)
    draw.text((92, 220), "LANG", font=faces.get(600, 24), fill=MUTED)
    draw.text((270, 220), "SOURCE / SHAPED BY GOKU", font=faces.get(600, 24), fill=MUTED)

    rows = [
        ("TS", "if (cache !== null && count >= limit) return next;", PINK),
        ("RUST", "let edge = lhs != rhs && depth <= max;", ORANGE),
        ("C++", "node->next = ptr != nullptr ? value : fallback;", BLUE),
        ("SHELL", "build && test || exit 1", CYAN),
        ("HTML", "<Panel />  </main>  <!-- content -->", PURPLE),
        ("BIT", "let packed = (value << 2) | (mask >>> 1);", ORANGE),
        ("LOGIC", "a === b  c !== d  left <=> right  x <> y", CYAN),
    ]
    for index, (label, sample, color) in enumerate(rows):
        y = 275 + index * 91
        if index == 2:
            draw.rectangle((70, y - 12, 1730, y + 62), fill=(25, 34, 55, 205))
        line(draw, (92, y + 67, 1708, y + 67), "#20283b", 1)
        draw.text((92, y + 9), label, font=faces.get(600, 25), fill=color)
        draw.text(
            (270, y),
            sample,
            font=faces.get(200, 39),
            fill=INK,
            features=["calt"],
        )

    line(draw, (92, 960, 1708, 960), "#33415f", 2)
    comparison = "->  =>  !=  !==  ===  <=>  ::  &&  //"
    draw.text((92, 995), "CALT ON", font=faces.get(700, 24), fill=CYAN)
    draw.text((270, 980), comparison, font=faces.get(300, 43), fill=INK, features=["calt"])
    draw.text((92, 1062), "CALT OFF", font=faces.get(700, 24), fill=MUTED)
    draw.text((270, 1047), comparison, font=faces.get(300, 43), fill=MUTED, features=["-calt"])
    draw.text((92, 1120), "28 NATIVE LIGATURES / EXACT TWO- OR THREE-CELL ADVANCES", font=faces.get(300, 23), fill=MUTED)
    save_png(image, output, "Goku native programming ligature specimen")


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
    render_ligatures(faces, args.output / "06-goku-ligatures.png")


if __name__ == "__main__":
    main()
