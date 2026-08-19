# Goku source provenance

Goku is a derivative font. Its new family name distinguishes its metrics,
metadata, restored glyph pipeline, numeric weight family, and italic behavior
from upstream Gohu.

## GohuFont

The pinned `vendor/gohufont` submodule provides both handcrafted 8x14 Unicode
bitmap anchors:

- `gohufont-uni-14.bdf` (Regular), SHA-256
  `cf5cdf71cb1a7237ea2ac3b9aade781f5f3d87144ec95c36a1bfd24e1c8591a0`
- `gohufont-uni-14b.bdf` (Bold), SHA-256
  `2d302820ea663a0f49d188a49759b18e8fc4f03ee982783ac629a940053523ac`
- Submodule commit: `cc36b8c9fed7141763e55dcee0a97abffcf08224`
- Upstream license: WTFPL version 2, recorded in
  `vendor/gohufont/COPYING-LICENSE`

The 400 and 700 release faces preserve these two real source anchors. Other
numeric text weights are generated from the nearest anchor; icons and terminal
graphics are not weight-transformed.

## Nerd Fonts patcher

The complete Nerd glyph set is generated with Nerd Fonts Patcher 3.4.0 from
the flake-locked Nix environment. No font from the building machine's home
directory is used.

Icon source projects and their licenses are listed by Nerd Fonts at:

<https://github.com/ryanoasis/nerd-fonts/tree/v3.4.0/src/glyphs>

See `THIRD_PARTY_NOTICES.md` for release attribution.
