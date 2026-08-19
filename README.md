# Goku terminal font

<p align="center">
  <img src="artwork/01-goku-header.png" alt="Goku terminal font — code at full power" width="100%">
</p>

<p align="center"><sub>
Character artwork adapted from the official
<a href="https://dragonball-super.com/en/">Dragon Ball Super: Beerus</a>
key visual. © BIRD STUDIO/SHUEISHA, TOEI ANIMATION.
</sub></p>

Goku is a vector, monospaced terminal font derived from the handcrafted Gohu
uni14 bitmap design. The release is one portable TrueType Collection:
`Goku.ttc`.

## Preview

<p align="center">
  <img src="artwork/02-goku-weights.png" alt="Goku weights 100 through 900" width="100%">
</p>

<p align="center">
  <img src="artwork/03-goku-symbols.png" alt="Goku terminal symbols and Nerd Font icons" width="100%">
</p>

<p align="center">
  <img src="artwork/04-goku-code.png" alt="Goku code and terminal specimen" width="100%">
</p>

The collection contains 18 faces. Upright and italic variants are available at
every numeric weight from `100` through `900`:

| Weight | Upright PostScript name | Italic PostScript name |
| ---: | --- | --- |
| 100 | `Goku-100` | `Goku-100Italic` |
| 200 | `Goku-200` | `Goku-200Italic` |
| 300 | `Goku-300` | `Goku-300Italic` |
| 400 | `Goku-400` | `Goku-400Italic` |
| 500 | `Goku-500` | `Goku-500Italic` |
| 600 | `Goku-600` | `Goku-600Italic` |
| 700 | `Goku-700` | `Goku-700Italic` |
| 800 | `Goku-800` | `Goku-800Italic` |
| 900 | `Goku-900` | `Goku-900Italic` |

There are no Thin, Light, Medium, SemiBold, or Bold-named release faces. The
numeric face is the complete identity. Weight `400` preserves the approved
Gohu regular-derived outlines and hinting exactly; `700` preserves the real
Gohu bold-derived outlines and hinting exactly. The surrounding weights form a
visually monotonic scale around those two anchors.

## Terminal geometry

- 2048 units per em
- 1170-unit monospaced advance, corresponding to Gohu's 8-pixel width
- 1609-unit ascent and -439-unit descent, preserving the native 11/3 baseline
- zero line gap, so the 14-pixel source grid fills one complete terminal cell
- 1024-unit x-height and 1317-unit cap height

Do not compensate with Kitty's `modify_font cell_width`: compressing the
correct cell makes letters and bold strokes collide. Adjust `font_size` or
choose a different numeric weight instead.

## Rendering guarantees

- All 18 faces keep the same monospaced advances and character coverage.
- Text uses bounded TrueType hinting from 6 through 13 px.
- Nerd icons, box drawing, blocks, and Powerline symbols do not change size or
  shape between weights.
- Italic affects text while terminal symbols and icons remain upright.
- Every adjacent numeric weight produces a distinct, progressively darker
  raster at terminal sizes.
- `ss01` provides an optional dotted zero; the default zero remains slashed.
- Fixed metadata timestamps make clean builds byte-for-byte reproducible.

## Kitty

Select exact faces by PostScript name. This example uses weight 200 for normal
and italic text, and the real 700 weight for bold:

```conf
font_family      postscript_name=Goku-200
bold_font        postscript_name=Goku-700
italic_font      postscript_name=Goku-200Italic
bold_italic_font postscript_name=Goku-700Italic
```

Enable the dotted zero on the selected faces with:

```conf
font_features Goku-200 +ss01
font_features Goku-700 +ss01
font_features Goku-200Italic +ss01
font_features Goku-700Italic +ss01
```

## Build and verify

```sh
git submodule update --init --recursive --depth 1
nix develop path:$PWD
make clean all
```

`make all` builds `build/Goku.ttc` and validates the internal four-face source
anchors before auditing the 18-face numeric release. The audit verifies names,
weights, version metadata, glyph identity, hint isolation, unchanged icons,
monospaced metrics, the exact 400/700 reference rasters, and the visual order of
all nine weights.

Prepare upload-ready GitHub release assets with:

```sh
make release
```

The release gate also runs OpenType Sanitizer, HarfBuzz shaping, sfnt integrity,
and two independent clean builds. It writes one font binary plus its checksum,
machine-readable manifest, release notes, and third-party notices to `dist/`.

## Install

Linux user installation:

```sh
mkdir -p ~/.local/share/fonts/Goku
cp dist/Goku.ttc ~/.local/share/fonts/Goku/Goku.ttc
fc-cache -f ~/.local/share/fonts/Goku
```

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for source attribution and
license information.
