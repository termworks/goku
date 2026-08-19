# Goku development plan

Last updated: 2026-08-19
Current release candidate: 1.200
Active milestone: publish the validated numeric-weight release
Active task: commit the final release-gate fixes, tag, and publish the GitHub release

## Mission

Build Goku into an unusually clear, compact, dependable coding font without
erasing the character of Gohu. Goku should look deliberate at tiny terminal
sizes, remain useful in editors, contain first-class terminal graphics and
developer icons, and never surprise users with an accidental metric or shaping
change.

"Best" will be treated as a set of measurable properties:

- Legible and stable from 7 px through 29 px, with special attention to the
  9–14 px range used by compact terminals.
- Every encoded character remains in one 1170-unit cell except intentional
  Powerline seam overlap and opt-in multi-cell ligatures.
- Numeric weights 100–900 and their matching italics are real static faces;
  weights 400 and 700 retain the handcrafted source anchors exactly.
- Coding ambiguities (`0/O`, `1/I/l/|`, `5/S`, `2/Z`, punctuation pairs) are
  reviewable in specimens and can be addressed without silently changing the
  default design.
- Box drawing, blocks, braille, Powerline, and legacy terminal graphics join
  without gaps or broken complements.
- Builds are deterministic, source-pinned, license-audited, and validated by
  more than one font engine.
- The release remains one installable file: `build/Goku.ttc`.

## Design constitution

These rules apply to every milestone.

1. Preserve Gohu's default letterforms unless a default change is explicitly
   approved from a side-by-side specimen.
2. Keep the 2048 UPM, 1170-unit advance, 1609/-439 vertical metrics, zero line
   gap, and 8x14 source-grid relationship.
3. Keep Gohu's handcrafted Regular and Bold as the source of truth. Do not
   mechanically embolden Regular and call it Bold.
4. Keep symbols and developer icons upright in italic faces unless a symbol's
   meaning specifically requires an italic form.
5. Add experimental typography as opt-in OpenType features first. Defaults
   change only after sustained use and explicit approval.
6. Do not solve font geometry with terminal-specific width or height overrides.
7. Never replace the installed font until the candidate passes structural,
   raster, shaping, and visual gates. Retain one rollback build outside the
   font-discovery path.
8. No additional release variants such as "pruned", "complete", or
   Nerd-suffixed files. Internal faces and optional features belong in the one
   TTC.

## Per-milestone workflow

Every milestone follows the same sequence. A step is checked only when its
evidence exists in the repository or build log.

1. Measure the current release and record a machine-readable baseline.
2. Implement the smallest coherent candidate without changing the installed
   font.
3. Run `make clean all`, structural validation, raster validation, shaping
   tests, and a second clean reproducibility build.
4. Generate labeled specimens at 10, 14, 20, and 29 px, including the numeric
   weight range and relevant symbols.
5. Compare old and new output. Reject changes that improve one case by damaging
   another.
6. Get visual approval, bump the version, install, refresh Fontconfig, and
   verify the exact faces selected by Kitty.
7. Update this file and `CHANGELOG.md` before beginning the next milestone.

## Foundation — version 1.100

Status: complete.

- [x] One TTC containing Regular, Bold, Italic, and Bold Italic.
- [x] Native Gohu 8x14 geometry restored from pinned Regular and Bold BDFs.
- [x] Baseline moved into the center of a one-em terminal line.
- [x] Small-size text hinting bounded to 6–13 px.
- [x] Per-glyph hints removed from terminal symbols and Nerd icons.
- [x] Italic text bounded to a one-source-pixel overhang envelope.
- [x] Ordinary PUA icons constrained horizontally to the cell.
- [x] Optional dotted zero available as `ss01`.
- [x] Deterministic timestamps and byte-for-byte reproducible builds.
- [x] Structural checks plus raster checks at 7–29 px.
- [x] Kitty resolves all four installed faces without synthetic styles.

Baseline artifact:

- File: `build/Goku.ttc`
- SHA-256: `b784156edd9c1cef9fa85a3e93db74d20b637c2b63956659d2eb7460e5eb2d62`
- Faces: 4
- Glyphs per face: 11,297
- Encoded mappings per face: 11,293
- File size: 9,355,356 bytes

## P1 — Optical icon consistency

Target release: 1.200. This is the next milestone.

The present build prevents ordinary Nerd icons from escaping horizontally, but
containment alone does not make icons look equally sized or centered. This
milestone adds class-aware optical normalization without touching text,
Powerline separators, box drawing, or block elements.

- [x] **P1.1 Inventory:** record outline bounds, ink centroid, visual area,
  source set, aliases, and raster bounds at 10/14/20 px for every PUA glyph.
- [x] **P1.2 Classification:** separate square icons, wide icons, tall icons,
  circular icons, logos, weather symbols, and intentional edge-touching forms.
- [x] **P1.3 Policy:** derive class-specific optical boxes from measurements;
  do not impose one arbitrary scale on all 10,000+ glyphs.
- [x] **P1.4 Transform:** center and scale only outliers. Preserve aliases and
  identical geometry across roman/italic pairs.
- [x] **P1.5 Regression:** add icon centroid, raster-size, clipping, and
  representative source-set tests.
- [x] **P1.6 Review:** generate old/new icon atlases at 10, 14, and 20 px.
- [x] **P1.7 Release gate:** approve, version, reproducibility-check, install,
  and verify in Kitty prompts, tabs, file listings, and status lines.

P1.1 evidence:

- Command: `make icon-inventory`
- Report: `build/reports/icon-inventory.json`
- Coverage: 10,397 PUA mappings and 10,397 unique glyphs
- Sources: 13 identified source sets; zero unknown mappings
- Geometry: simplified filled-outline bounds, area, and centroid
- Raster measurements: 10, 14, and 20 px
- Baseline exception: Codicons `U+EC03` (`blank`) is intentionally empty

P1.2 evidence:

- Command: `make icon-classes`
- Report: `build/reports/icon-classes.json`
- Aspect classes: 7,887 square, 1,413 wide, 1,096 tall, and one blank
- Semantic classes: 817 logos, 228 weather symbols, 338 declared circular
  forms, 40 Powerline forms, and 12 progress indicators
- Edge classes: 52 intentional edge-touching forms separated from 8,629
  observed edge-touching outlines
- Optical review set: 751 statistically exceptional glyphs after applying
  practical visual-delta floors; these are candidates, not automatic edits

P1.3–P1.6 evidence:

- Policy: `build/reports/icon-policy.json`
- Policy result: 9,644 preserved, 734 review-only, and 19 safe scale-down
  actions; no enlargement or translation
- Candidate: `/tmp/Goku-p1-candidate.ttc`
- Candidate SHA-256:
  `2b1664a23d05dada54ba2033baf25b17baed78dcfe6aade53a3da15fa5fbcb9d`
- Reproducibility: a second independent build produced the same SHA-256 and was
  byte-identical
- Scope regression: exactly 19 changed outlines per face; every other outline,
  all Gohu text, and all Powerline glyphs byte-identical to 1.100
- Raster regression: 31,191 full-PUA comparisons at 10/14/20 px; no new
  blanks; roman/italic icon masks identical
- Optical result: class-relative outlier set reduced from 751 to 732, exactly
  matching the 19 declared actions
- Atlases: `build/reports/icon-atlas/icon-atlas-{10,14,20}px.png`

Acceptance criteria:

- No ordinary icon escapes the cell.
- Powerline geometry is byte-identical to 1.100.
- Textual Gohu glyphs are byte-identical to 1.100 before hinting.
- No icon becomes empty at any audited size.
- Roman/italic icon masks remain identical.
- Optical outlier counts decrease according to the recorded class policy; no
  icon is transformed merely to make a statistic look tidy.

## P2 — Pixel-perfect terminal graphics

Target release: 1.300.

Create Goku-native, parameterized terminal graphics rather than depending on
whatever geometry arrives through the icon patcher.

- [x] Audit coverage and geometry for Box Drawing (`U+2500–U+257F`), Block
  Elements (`U+2580–U+259F`), Braille (`U+2800–U+28FF`), Symbols for Legacy
  Computing (`U+1FB00–U+1FBFF`), and the relevant Unicode 17 Legacy Computing
  Supplement characters (`U+1CC00–U+1CEBF`).
- [ ] Build reusable grid primitives for light/heavy/double strokes, corners,
  diagonals, quadrants, eighth blocks, sextants, shades, and braille dots.
- [x] Replace patched glyphs only where the Goku generator is demonstrably
  more complete or joins more accurately.
- [x] Add complement and composition invariants: paired fractional blocks must
  form a full cell, adjacent line glyphs must meet, and shade densities must be
  ordered.
- [x] Raster-test joins at 7–29 px with no empty rows, columns, or one-pixel
  seams.
- [ ] Test in Kitty and Alacritty because terminals may choose different paths
  for box-drawing characters.

Acceptance criteria:

- All supported graphic primitives are generated from documented parameters.
- Horizontal and vertical joins are continuous at every audited size.
- Complementary block pairs cover exactly one cell in outline space.
- Braille follows the Unicode dot mapping and remains readable at small sizes.
- Existing coding text and icon geometry does not change.

P2 evidence to date:

- The generator now owns 27 formerly patched Box Drawing glyphs, all 32 Block
  Elements, all 256 Braille patterns, 219 Symbols for Legacy Computing, and
  15 Unicode 17 separated-quadrant symbols. Every generated terminal glyph is
  upright and outline-identical across all four faces.
- The 219 legacy symbols include all sextants, all 44 diagonal mosaics,
  eighth-position blocks,
  cardinal triangular blocks, partial/inverse shades, checker and diagonal
  fills, smooth mosaic triangles, both legacy diagonal-box sets, third blocks,
  circle/quarter-circle geometry, and segmented digits.
- Thirty-seven full-cell complement pairs, thirteen line/shape compositions,
  thirty sextant complements, seven separated-quadrant complements, shade
  ordering, every Braille dot combination, and visibility of every generated
  glyph in every face pass 31,952 FreeType checks at
  7–29 px. The general Goku raster audit, HarfBuzz audit, structural validator,
  and OpenType Sanitizer also pass.
- The current candidate has 11,787 glyphs and 11,783 cmap mappings per face at
  SHA-256 `a3816acc3c21575604ae424c04a1c662b07df2666bb451d37ff03bd1c529dd02`.
  It remains uninstalled pending visual approval; installed Goku 1.100 is
  byte-identical to the baseline.

## P3 — Coding character alternatives

Target release: 1.400.

Add choices without turning personal taste into a forced default. Use
registered character-variant features (`cv01`–`cv99`) for individual glyphs and
stylistic sets for coherent bundles. Keep `ss01` as a compatibility alias for
the existing dotted zero if its canonical feature changes.

Candidate experiments:

- [ ] Dotted and unslashed zero alternatives.
- [ ] Distinct forms for `1`, uppercase `I`, lowercase `l`, and vertical bar.
- [ ] Alternate braces, ampersand, asterisk, dollar, at sign, and underscore.
- [ ] Disambiguation specimen for `0OQ`, `1Il|`, `5S`, `2Z`, `8B`, `rn/m`,
  quotes/backticks, colons/semicolons, and all bracket pairs.
- [ ] Human-readable OpenType feature names so Kitty's font chooser can show
  what each feature does.
- [ ] A documented "maximum disambiguation" stylistic set assembled from the
  best approved variants.

Acceptance criteria:

- Default glyphs remain unchanged unless separately approved.
- Every feature works in all four faces through HarfBuzz and Kitty.
- Feature substitutions preserve the one-cell advance.
- Bold alternatives are intentionally drawn from the bold grid, not copied
  from Regular.
- The README includes exact Kitty configuration examples.

## P4 — Optional coding ligatures

Target release: 1.500.

Ligatures must be opt-in and must never alter stored text or cursor-cell
behavior. Start with the registered discretionary-ligature feature (`dlig`),
which applications normally leave disabled.

- [ ] Prototype a small set: `->`, `<-`, `=>`, `<=`, `!=`, `==`, `===`, `::`,
  `&&`, `||`, `++`, and selected comment markers.
- [ ] Draw ligatures from the same pixel grid rather than importing a smooth
  vector style.
- [ ] Give each ligature exactly the summed advance of its input cells.
- [ ] Add shaping tests for expected substitutions and false-positive contexts.
- [ ] Test cursor movement, selection, copy/paste, and line wrapping in Kitty,
  Alacritty, and at least one GUI editor.
- [ ] Publish a specimen with ligatures both off and on.

Acceptance criteria:

- Ligatures are disabled by default.
- Enabling them changes appearance only; underlying text and editing behavior
  remain correct.
- No substitution crosses whitespace, token boundaries outside the declared
  rules, or line boundaries.
- Terminals that do not support ligatures still receive ordinary glyphs.

## P5 — Additional weight research

Target: experimental; no promised release.

Gohu supplies real Regular and Bold bitmaps but no intermediate master. A
Medium face would be valuable only if it can be designed consistently; blind
outline interpolation or dilation is not acceptable.

- [ ] Measure Regular/Bold pixel decisions across ASCII and coding punctuation.
- [ ] Prototype Medium for a small diagnostic set.
- [ ] Decide whether a complete handcrafted Medium is feasible.
- [ ] If feasible, investigate Medium and Medium Italic as extra faces inside
  the same TTC with standards-compliant legacy and typographic naming.
- [ ] Do not begin a variable `wght` font unless compatible masters exist and
  interpolation tests pass.

Release gate: abandon this milestone if Medium is inconsistent, harms tiny-size
rendering, or complicates reliable four-face selection. Four excellent faces
are better than six uneven ones.

## P6 — Native bitmap-strike research

Target: experimental; no promised release.

- [ ] Determine whether current Kitty, Alacritty, FreeType, Windows, and macOS
  actually select monochrome embedded strikes from a TTC.
- [ ] Prototype exact 10, 12, and native 14 px strikes from Goku/Gohu geometry.
- [ ] Confirm OpenType feature substitution, style selection, and symbols still
  work when a strike is selected.
- [ ] Measure startup, memory, and file-size cost.

Release gate: include strikes only if at least the primary target applications
use them, they look better than bounded hinting, and the outline fallback stays
identical. Otherwise retain the research notes and ship no dead tables.

## P7 — Quality, portability, and performance

This work runs incrementally alongside P1–P6 and becomes a formal release gate
before 2.000.

- [x] Add OpenType Sanitizer checks.
- [x] Add FontBakery's Universal/OpenType profiles; document justified skips
  instead of hiding failures.
- [x] Run FontForge outline validation for every generated face.
- [x] Validate GSUB behavior with HarfBuzz and raster behavior with FreeType.
- [x] Add table checksums, duplicate-cmap detection, unreachable-glyph checks,
  and metadata/license assertions.
- [x] Add clean-build reproducibility as an automated target.
- [x] Establish file-size and build-time budgets and report changes per release.
- [ ] Test Linux Fontconfig/Kitty/Alacritty first, then record Windows and macOS
  installation/style-linking results when those systems are available.
- [x] Add CI using the pinned Nix environment.

P7 evidence to date:

- The flake keeps the release builder on pinned Python 3.14.7 and isolates
  FontBakery 1.1.0 on Python 3.13.15. FontBakery's two broken Nix dependency
  test derivations are narrowly overridden; Goku's own checks run in full.
- `make ots` passes OpenType Sanitizer 9.3.0 on both 1.100 and the P1
  candidate.
- `make fontbakery-report` executes 472 Universal/OpenType checks per
  four-face family. Both artifacts report 247 PASS, 160 SKIP, 12 INFO, 28
  WARN, 25 FAIL, zero ERROR, and zero FATAL. No check is excluded; the seven
  distinct failure groups and skip policy are recorded in
  `quality/FONTBAKERY.md`.
- `make fontforge` checks all 11,297 outlines in every face. Both artifacts
  have zero hard TrueType issues. The P1 candidate reduces inherited
  self-intersection and missing-extrema advisories by one per face.
- `make harfbuzz` passes HarfBuzz 13.2.1 shaping for all TTC face indexes,
  including default/`ss01` zero, coding text, BMP/supplementary icons,
  Powerline, and the 1170-unit advance. `make validate` retains the existing
  FreeType raster audit at 7–29 px.
- `make sfnt-audit-report` verifies all 64 table-directory checksums, detects
  no duplicate cmap records or conflicting mappings, reaches all 11,297
  glyphs per face through cmap/GSUB/composite closure, and verifies source and
  embedded license records. Its strict form currently exposes one genuine
  family-wide defect: inherited `OS/2.fsType=0x4` must become installable
  embedding (`0x0`) in a reviewed candidate.
- `make reproducible` performs two isolated builds. The P1 candidate is
  byte-identical at SHA-256
  `2b1664a23d05dada54ba2033baf25b17baed78dcfe6aade53a3da15fa5fbcb9d`,
  is 9,355,244 bytes (-112 from 1.100), and built in 56.741/58.156 seconds.
  Budgets are 12,582,912 bytes and 300 seconds per clean build.
- `.github/workflows/ci.yml` builds and validates through `flake.lock`, runs
  every reporting engine, repeats the clean build, and uploads the evidence.
- `make quality-report` is the complete non-suppressing baseline reporter.
  `make quality` is the strict release gate and deliberately remains red while
  the remaining recorded FontBakery defects exist.

## P8 — Specimens, documentation, and releases

- [ ] Add `make specimen` for a deterministic all-face, multi-size coding sheet.
- [ ] Add `make icon-atlas` and `make compare OLD=... NEW=...`.
- [x] Add `CHANGELOG.md` with visible, metric, coverage, and compatibility
  changes for every release.
- [ ] Document every OpenType feature with its tag, default state, and Kitty
  example.
- [ ] Generate a coverage report grouped by Unicode block and icon source.
- [x] Add a release target that produces only `Goku.ttc` plus its checksum and
  validation report; do not produce alternate font binaries.

## Ideas deliberately deferred

- Color emoji: use a dedicated fallback font; it is outside Goku's pixel coding
  identity and would drastically inflate the font.
- Proportional UI faces: a separate design problem that conflicts with Goku's
  terminal guarantees.
- Automatic synthetic bold or italic: prohibited by the design constitution.
- Default-on ligatures: reconsider only after the opt-in implementation has
  been used successfully for a full milestone.
- Arbitrary global stretching in Kitty: font geometry must be solved in Goku.

## Authoritative references

- OpenType specification and registered features:
  <https://learn.microsoft.com/en-us/typography/opentype/spec/>
- OpenType naming and four-face style-linking guidance:
  <https://learn.microsoft.com/en-us/typography/opentype/spec/name>
- Unicode 17 names-list charts:
  <https://www.unicode.org/charts/nameslist/mainList.html>
- Unicode Symbols for Legacy Computing:
  <https://www.unicode.org/charts/nameslist/c_1FB00.html>
- Unicode Symbols for Legacy Computing Supplement:
  <https://www.unicode.org/charts/PDF/U1CC00.pdf>
- FontTools feature builder and variation tooling:
  <https://fonttools.readthedocs.io/en/latest/feaLib/>
- FontBakery Universal profile:
  <https://fontbakery.readthedocs.io/en/stable/fontbakery/profiles/universal.html>
- Nerd Fonts patcher and glyph-set documentation:
  <https://github.com/ryanoasis/nerd-fonts>
- Kitty font selection and OpenType-feature controls:
  <https://sw.kovidgoyal.net/kitty/kittens/choose-fonts/>
