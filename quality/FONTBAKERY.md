# FontBakery policy

Goku runs FontBakery's complete Universal/OpenType profile against 18
audit-only TTFs extracted from the release TTC. The extracted files are build
artifacts, not additional releases.

`make fontbakery-report` records every result but exits nonzero only for a tool
error. `make fontbakery` is the release gate and exits nonzero on every
FontBakery `FAIL`. Reports are written below
`build/reports/quality/fontbakery/`.

No checks are currently excluded. If a check is eventually skipped, this file
must record its full check ID, the exact reason it does not apply, and the
replacement Goku-specific assertion. A warning caused by the pixel design or
large Nerd Font coverage is still retained in the report rather than hidden.

## Version 1.100 four-face baseline

FontBakery 1.1.0 executed 472 checks: 247 PASS, 160 SKIP, 12 INFO, 28 WARN,
25 FAIL, zero ERROR, and zero FATAL. The failures collapse to seven distinct
issues rather than 25 unrelated defects:

- missing OS/2 code-page bits in all four faces;
- no family STAT table;
- three missing Unicode case counterparts inherited from source coverage;
- missing integer-PPEM flag on hinted faces;
- blank `.notdef` glyphs;
- legacy Mac-platform name records;
- invalid glyph names inherited from the Nerd Fonts patcher.

These are historical baseline findings, not accepted skips. Version 1.200's
18-face numeric report must be regenerated before publishing and retained with
the release evidence.
