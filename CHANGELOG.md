# Changelog

## 1.300 — pending GitHub release

- Added explicit cell-edge clearance for all 600 ordinary Gohu text glyphs in
  Regular, Bold, and their italics.
- Shortened only the descender zone instead of shrinking whole letter bodies.
- Centered or fitted edge-reaching upright text with a half-source-pixel side
  margin; kept italic overhang bounded separately.
- Protected em dash and horizontal bar as intentional edge-spanning forms.
- Restricted numeric weight generation to Gohu text so segmented digits and
  other Unicode terminal graphics can never be mistaken for prose.
- Added structural audits for text clearance across the source faces and exact
  non-text preservation across all 18 numeric faces.
- Rebalanced weight 600 after the clearance adjustment and retained distinct,
  monotonic rasters for every 100-unit step.

## 1.200

- Promoted the numeric `100`–`900` family to the sole release collection.
- Added matching italic faces at every numeric weight, for 18 faces total.
- Kept `400` and `700` byte-for-byte faithful to the approved Regular and real
  Bold source faces after release renaming.
- Balanced `500` and `600` between the two real source anchors for a smoother
  visual progression.
- Re-hinted generated text faces while keeping icons and terminal graphics
  unhinted and identical across every weight.
- Added strict audits for glyph substitutions, icon raster equality, numeric
  weight monotonicity, exact PostScript names, and release reproducibility.
- Replaced the temporary `Goku Weight Test` / named-weight distribution with
  one `Goku.ttc` artifact.

### Compatibility

Configurations using names such as `Thin`, `Light`, `Medium`, `SemiBold`, or
`Bold` must switch to numeric PostScript names such as `Goku-200` or
`Goku-700`. The previous named-weight test collection is not part of this
release.
