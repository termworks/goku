#!/usr/bin/env python3
"""Render release artwork with the real Goku Pixel TTC faces.

The hero illustration is an input.  Every letter, symbol, and icon layered on
top of it is rendered from Goku-Pixel.ttc, so specimen images stay truthful to
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
            self.cache[key] = ImageFont.truetype(self.path, size=size, index=index)
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
    info.add_text("Font", f"Goku Pixel {VERSION}")
    info.add_text("Typography", "Rendered directly from Goku-Pixel.ttc")
    image.convert("RGB").save(path, format="PNG", optimize=True, pnginfo=info)


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
    image = canvas(1120, (8, 10, 23), (15, 12, 31)).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.text((92, 66), "NINE LEVELS OF POWER", font=faces.get(800, 68), fill=INK)
    draw.text((96, 145), "Every 100. Every face. One monospace system.", font=faces.get(200, 31), fill=BLUE)
    line(draw, (96, 202, 1704, 202), ORANGE, 4)

    row_top = 235
    row_height = 91
    accents = ["#7887a8", "#8297bd", "#78a9d8", "#72c4d4", "#73e0d1", "#a6df79", "#ffd166", "#ff9f43", "#ff6b5f"]
    for row, weight in enumerate(range(100, 1000, 100)):
        y = row_top + row * row_height
        if row % 2 == 0:
            draw.rounded_rectangle((82, y - 7, 1718, y + 72), radius=10, fill=(18, 23, 42, 205))
        draw.rounded_rectangle((100, y + 6, 195, y + 55), radius=8, fill=accents[row])
        label_font = faces.get(700, 30)
        label_w, _ = text_size(draw, str(weight), label_font)
        draw.text((147 - label_w / 2, y + 16), str(weight), font=label_font, fill="#07101a")

        sample = "Goku  Agjy  0O  1Il  {}[]  =>"
        draw.text((236, y), sample, font=faces.get(weight, 53), fill=INK)
        italic = "italic"
        italic_font = faces.get(weight, 35, True)
        italic_w, _ = text_size(draw, italic, italic_font)
        draw.text((1668 - italic_w, y + 14), italic, font=italic_font, fill=accents[row])

    draw.text((96, 1065), "100 / whisper                                                   900 / impact", font=faces.get(300, 25), fill=MUTED)
    save_png(image, output, "Goku weight and italic specimen")


def card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, faces: Faces, accent: str) -> None:
    draw.rounded_rectangle(box, radius=18, fill=(13, 18, 36, 235), outline=(42, 54, 88, 255), width=2)
    x1, y1, x2, _ = box
    draw.rounded_rectangle((x1 + 22, y1 + 20, x1 + 52, y1 + 50), radius=7, fill=accent)
    draw.text((x1 + 70, y1 + 22), title, font=faces.get(700, 30), fill=INK)
    line(draw, (x1 + 22, y1 + 68, x2 - 22, y1 + 68), accent, 2)


def render_symbols(faces: Faces, output: Path) -> None:
    image = canvas(1480, (5, 11, 24), (12, 18, 34)).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.text((88, 62), "THE WHOLE GLYPH UNIVERSE", font=faces.get(800, 64), fill=INK)
    draw.text((92, 140), "Icons, dev logos, terminal graphics, Powerline, math, braille, and legacy computing.", font=faces.get(200, 30), fill=CYAN)

    boxes = [
        (80, 220, 875, 575),
        (925, 220, 1720, 575),
        (80, 615, 875, 970),
        (925, 615, 1720, 970),
        (80, 1010, 875, 1365),
        (925, 1010, 1720, 1365),
    ]
    card(draw, boxes[0], "NERD ICONS", faces, ORANGE)
    card(draw, boxes[1], "DEV STACK", faces, PINK)
    card(draw, boxes[2], "BOX + BLOCK", faces, BLUE)
    card(draw, boxes[3], "POWERLINE + PROMPT", faces, PURPLE)
    card(draw, boxes[4], "MATH + MOTION", faces, CYAN)
    card(draw, boxes[5], "BRAILLE + LEGACY", faces, ORANGE)

    nerd_rows = [
        "              ",
        "              ",
        "              ",
    ]
    for i, value in enumerate(nerd_rows):
        draw.text((122, 312 + i * 78), value, font=faces.get(500, 48), fill=(INK, ORANGE, BLUE)[i])

    dev_rows = [
        "          ",
        "          ",
        "          ",
    ]
    for i, value in enumerate(dev_rows):
        draw.text((967, 312 + i * 78), value, font=faces.get(500, 55), fill=(PINK, CYAN, PURPLE)[i])

    draw.text((122, 710), "╭────┬────╮  ┏━━━━┳━━━━┓", font=faces.get(400, 42), fill=BLUE)
    draw.text((122, 768), "│ ░▒▓│█ ▌ │  ┃▖▗▘┃▙▚▟┃", font=faces.get(400, 42), fill=INK)
    draw.text((122, 826), "╰────┴────╯  ┗━━━━┻━━━━┛", font=faces.get(400, 42), fill=BLUE)
    draw.text((122, 893), "▁▂▃▄▅▆▇█  ▏▎▍▌▋▊▉█", font=faces.get(500, 39), fill=CYAN)

    draw.text((968, 707), "        ", font=faces.get(500, 69), fill=PURPLE)
    draw.rounded_rectangle((967, 832, 1668, 918), radius=12, fill="#4f3a82")
    draw.text((993, 851), "  ~/goku    main  ", font=faces.get(600, 38), fill=INK)

    draw.text((122, 1102), "← ↑ → ↓  ↔ ↕  ⇐ ⇒ ⇔", font=faces.get(400, 40), fill=CYAN)
    draw.text((122, 1165), "∃ ∅ ∆ ∈ ∊  − ∙ √ ∞ ∟", font=faces.get(500, 40), fill=INK)
    draw.text((122, 1228), "∧ ∨ ∩ ∪  ≈ ≠ ≡ ≤ ≥", font=faces.get(500, 40), fill=ORANGE)

    draw.text((968, 1096), "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏", font=faces.get(300, 50), fill=ORANGE)
    draw.text((968, 1163), "🯰🯱🯲🯳🯴🯵🯶🯷🯸🯹", font=faces.get(500, 47), fill=INK)
    draw.text((968, 1230), "🬀🬁🬂🬃🬄🬅  🮐🮑🮒🮔", font=faces.get(400, 47), fill=BLUE)

    draw.text((84, 1431), "11,000+ mapped codepoints // every showcased glyph is present in the shipped TTC // one-cell geometry", font=faces.get(300, 27), fill=MUTED)
    save_png(image, output, "Goku symbols and Nerd Font icon specimen")


def render_terminal_lab(faces: Faces, output: Path) -> None:
    image = canvas(1180, (7, 10, 22), (10, 17, 33)).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.text((86, 58), "PIXEL TERMINAL LAB", font=faces.get(800, 66), fill=INK)
    draw.text((91, 138), "A working terminal scene: text, status, plots, spinners, and native cell graphics.", font=faces.get(200, 29), fill=BLUE)

    panel = (72, 210, 1728, 1092)
    draw.rounded_rectangle(panel, radius=22, fill=(7, 11, 24, 250), outline=(52, 68, 108, 255), width=2)
    draw.rectangle((72, 210, 1728, 282), fill=(20, 27, 49, 255))
    for x, color in [(106, "#ff625f"), (143, "#ffbd44"), (180, "#00ca4e")]:
        draw.ellipse((x, 235, x + 19, 254), fill=color)
    draw.text((675, 231), "  goku@capsule:~/fontmake", font=faces.get(300, 28), fill=MUTED)

    draw.rounded_rectangle((100, 310, 810, 820), radius=14, fill=(14, 20, 38, 240), outline=(41, 57, 91, 255), width=2)
    draw.text((128, 340), "SYSTEM // ONLINE", font=faces.get(700, 34), fill=CYAN)
    line(draw, (128, 392, 782, 392), CYAN, 2)
    stats = [
        ("  CPU", "████████░░  82%", ORANGE),
        ("  RAM", "██████░░░░  61%", BLUE),
        ("  DISK", "████░░░░░░  43%", PURPLE),
        ("  NET", "███░░░░░░░  28%", CYAN),
    ]
    for row, (label, value, color) in enumerate(stats):
        y = 430 + row * 76
        draw.text((128, y), label, font=faces.get(500, 30), fill=color)
        draw.text((326, y), value, font=faces.get(300, 30), fill=INK)
    draw.text((128, 747), "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏  compiling", font=faces.get(400, 30), fill=ORANGE)

    draw.rounded_rectangle((846, 310, 1698, 820), radius=14, fill=(14, 20, 38, 240), outline=(41, 57, 91, 255), width=2)
    draw.text((875, 340), "SIGNAL // 14 CELLS", font=faces.get(700, 34), fill=PURPLE)
    line(draw, (875, 392, 1669, 392), PURPLE, 2)
    draw.text((884, 425), "▁▂▃▅▆█▇▅▃▂▄▆█▇", font=faces.get(500, 55), fill=CYAN)
    draw.text((884, 502), "⣀⣄⣤⣦⣶⣷⣿⣷⣶⣦⣤⣄⣀", font=faces.get(400, 49), fill=BLUE)
    draw.text((884, 575), "🯰🯱🯲🯳🯴🯵🯶🯷🯸🯹", font=faces.get(500, 53), fill=INK)
    draw.text((884, 652), "🬀🬁🬂🬃🬄🬅🬆🬇🬈🬉", font=faces.get(400, 53), fill=ORANGE)
    draw.text((884, 729), "←↑→↓  ⇐⇒  ≠≤≥  ∧∨∩∪", font=faces.get(400, 39), fill=PURPLE)

    draw.rounded_rectangle((100, 850, 1698, 1038), radius=14, fill=(13, 18, 35, 245), outline=(41, 57, 91, 255), width=2)
    draw.text((130, 879), "", font=faces.get(600, 52), fill=PURPLE)
    draw.rounded_rectangle((167, 886, 506, 943), radius=4, fill="#513b84")
    draw.text((187, 896), "  ~/fontmake", font=faces.get(600, 29), fill=INK)
    draw.text((510, 879), "", font=faces.get(600, 52), fill=PURPLE)
    draw.text((574, 895), "git:(main)    pixel-validate", font=faces.get(300, 30), fill=CYAN)
    draw.text((130, 967), "$ cargo run --release  # Agjy 0O 1Il", font=faces.get(200, 31), fill=INK)
    draw.text((1410, 970), "14ms", font=faces.get(700, 31), fill=ORANGE)

    save_png(image, output, "Goku Pixel terminal dashboard specimen")


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
    image = canvas(1080, (8, 9, 20), (11, 15, 30)).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw.text((83, 48), "GOKU // CODE AT FULL POWER", font=faces.get(800, 57), fill=INK)
    draw.text((88, 115), "200 for flow · 600 for structure · italics for thought", font=faces.get(200, 29), fill=BLUE)

    panel = (70, 178, 1730, 1005)
    draw.rounded_rectangle(panel, radius=24, fill=(8, 12, 25, 248), outline=(51, 63, 100, 255), width=2)
    draw.rounded_rectangle((70, 178, 1730, 249), radius=24, fill=(20, 26, 48, 255))
    draw.rectangle((70, 220, 1730, 249), fill=(20, 26, 48, 255))
    for x, color in [(108, "#ff625f"), (146, "#ffbd44"), (184, "#00ca4e")]:
        draw.ellipse((x, 203, x + 20, 223), fill=color)
    draw.text((690, 199), "~/goku/demo.rs", font=faces.get(300, 27), fill=MUTED)

    draw.rounded_rectangle((91, 517, 1709, 576), radius=8, fill=(37, 49, 79, 190))
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
    start_y = 282
    line_height = 62
    for number, segments in enumerate(code, 1):
        y = start_y + (number - 1) * line_height
        num = f"{number:02}"
        draw.text((108, y + 4), num, font=faces.get(200, 30), fill="#505c78")
        if segments:
            draw_segments(draw, faces, 190, y, segments)

    draw.rounded_rectangle((1170, 918, 1667, 974), radius=10, fill="#162842", outline=BLUE, width=1)
    draw.text((1203, 934), "  compiled in 14ms", font=faces.get(500, 27), fill=CYAN)
    draw.text((105, 941), "NORMAL 200", font=faces.get(200, 26), fill=INK)
    draw.text((332, 941), "BOLD 600", font=faces.get(600, 26), fill=INK)
    draw.text((535, 941), "ITALIC 200", font=faces.get(200, 26, True), fill=INK)
    draw.text((792, 941), "BOLD ITALIC 700", font=faces.get(700, 26, True), fill=INK)
    save_png(image, output, "Goku code and terminal specimen")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--hero", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    faces = Faces(args.font)
    render_header(faces, args.hero, args.output / "01-goku-header.png")
    render_weights(faces, args.output / "02-goku-weights.png")
    render_symbols(faces, args.output / "03-goku-symbols.png")
    render_code(faces, args.output / "04-goku-code.png")
    render_terminal_lab(faces, args.output / "05-goku-terminal.png")


if __name__ == "__main__":
    main()
