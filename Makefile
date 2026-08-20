GOHU_REGULAR_BDF ?= vendor/gohufont/gohufont-uni-14.bdf
GOHU_BOLD_BDF ?= vendor/gohufont/gohufont-uni-14b.bdf
GOKU_BASE_OUTPUT := build/intermediate/Goku-Base.ttc
GOKU_VECTOR_OUTPUT := build/intermediate/Goku-Vector.ttc
GOKU_UNHINTED_OUTPUT := build/intermediate/Goku-unhinted.ttc
GOKU_OUTPUT := build/Goku.ttc
GOKU_FAMILY ?= Goku
PIXEL_COLUMNS ?= 20
PIXEL_ROWS ?= 35
ICON_PIXEL_COLUMNS ?= 8
ICON_PIXEL_ROWS ?= 14
ICON_PIXEL_THRESHOLD ?= 0.25
ICON_PIXEL_FALLBACK_THRESHOLD ?= 0.05
PIXEL_THRESHOLD ?= 0.5
PIXEL_WEIGHT_CONTRAST ?= 0.0
PIXEL_REPORT := build/reports/pixelation.json
PIXEL_QUALITY_DIR := build/reports/pixel-quality
RELEASE_DIR ?= dist
ICON_INVENTORY := build/reports/icon-inventory.json
ICON_CLASSES := build/reports/icon-classes.json
ICON_POLICY := build/reports/icon-policy.json
TERMINAL_INVENTORY := build/reports/terminal-graphics.json
AUDIT_FONT ?= $(GOKU_OUTPUT)
QUALITY_FONT ?= $(GOKU_OUTPUT)
QUALITY_DIR ?= build/reports/quality
QUALITY_FACES := $(QUALITY_DIR)/faces

.PHONY: all build base weights pixel pixel-validate base-validate weight-audit validate release terminal-inventory terminal-graphics-audit terminal-compare quality-report quality quality-faces ots fontbakery-report fontbakery fontforge harfbuzz sfnt-audit-report sfnt-audit reproducible icon-inventory icon-classes icon-policy p1-regression icon-atlas clean

all: validate

build: $(GOKU_OUTPUT)

base: $(GOKU_BASE_OUTPUT)

weights: $(GOKU_VECTOR_OUTPUT)

pixel: build

$(GOKU_UNHINTED_OUTPUT): $(GOKU_VECTOR_OUTPUT) src/pixelate_collection.py
	mkdir -p "$(dir $@)" "$(dir $(PIXEL_REPORT))"
	python src/pixelate_collection.py --source "$(GOKU_VECTOR_OUTPUT)" --output "$@" --columns "$(PIXEL_COLUMNS)" --rows "$(PIXEL_ROWS)" --icon-columns "$(ICON_PIXEL_COLUMNS)" --icon-rows "$(ICON_PIXEL_ROWS)" --icon-threshold "$(ICON_PIXEL_THRESHOLD)" --icon-fallback-threshold "$(ICON_PIXEL_FALLBACK_THRESHOLD)" --threshold "$(PIXEL_THRESHOLD)" --weight-contrast "$(PIXEL_WEIGHT_CONTRAST)" --family "$(GOKU_FAMILY)" --report "$(PIXEL_REPORT)"

$(GOKU_OUTPUT): $(GOKU_UNHINTED_OUTPUT) src/hint_pixel_collection.py src/text_glyphs.py src/bdf.py src/design.py $(GOHU_REGULAR_BDF) $(GOHU_BOLD_BDF)
	mkdir -p "$(dir $@)"
	python src/hint_pixel_collection.py --source "$(GOKU_UNHINTED_OUTPUT)" --regular-bdf "$(GOHU_REGULAR_BDF)" --bold-bdf "$(GOHU_BOLD_BDF)" --output "$@"

pixel-validate: build weight-audit
	python src/validate_pixelated_collection.py --source "$(GOKU_VECTOR_OUTPUT)" --candidate "$(GOKU_OUTPUT)" --regular-bdf "$(GOHU_REGULAR_BDF)" --bold-bdf "$(GOHU_BOLD_BDF)" --columns "$(PIXEL_COLUMNS)" --rows "$(PIXEL_ROWS)" --icon-columns "$(ICON_PIXEL_COLUMNS)" --icon-rows "$(ICON_PIXEL_ROWS)"
	mkdir -p "$(PIXEL_QUALITY_DIR)/ots"
	ots-sanitize "$(GOKU_OUTPUT)" "$(PIXEL_QUALITY_DIR)/ots/Goku-sanitized.ttc"
	python src/shaping_audit.py --collection "$(GOKU_OUTPUT)" --report "$(PIXEL_QUALITY_DIR)/harfbuzz.json"
	python src/sfnt_audit.py --collection "$(GOKU_OUTPUT)" --sources SOURCES.md --gohu-license vendor/gohufont/COPYING-LICENSE --report "$(PIXEL_QUALITY_DIR)/sfnt.json"

$(GOKU_BASE_OUTPUT): src/build_goku_collection.py src/build_regular.py src/build_bdf_face.py src/design.py src/font_variants.py src/icon_optical_policy.py src/ligatures.py src/terminal_graphics.py src/text_glyphs.py $(GOHU_REGULAR_BDF) $(GOHU_BOLD_BDF)
	mkdir -p "$(dir $@)"
	python src/build_goku_collection.py --regular-bdf "$(GOHU_REGULAR_BDF)" --bold-bdf "$(GOHU_BOLD_BDF)" --output "$@"

$(GOKU_VECTOR_OUTPUT): $(GOKU_BASE_OUTPUT) src/build_weight_collection.py src/fontforge_change_text_weight.py src/text_glyphs.py
	mkdir -p "$(dir $@)"
	python src/build_weight_collection.py --source "$(GOKU_BASE_OUTPUT)" --regular-bdf "$(GOHU_REGULAR_BDF)" --bold-bdf "$(GOHU_BOLD_BDF)" --output "$@" --family "$(GOKU_FAMILY)"

base-validate: base
	python src/validate_font.py --collection "$(GOKU_BASE_OUTPUT)" --regular-bdf "$(GOHU_REGULAR_BDF)" --bold-bdf "$(GOHU_BOLD_BDF)"
	python src/raster_audit.py --collection "$(GOKU_BASE_OUTPUT)"

weight-audit: weights base-validate
	python src/audit_weight_collection.py --source "$(GOKU_BASE_OUTPUT)" --candidate "$(GOKU_VECTOR_OUTPUT)" --regular-bdf "$(GOHU_REGULAR_BDF)" --bold-bdf "$(GOHU_BOLD_BDF)" --family "$(GOKU_FAMILY)"

validate: pixel-validate
	fc-scan --format='family=%{family}\nstyle=%{style}\nweight=%{weight}\nspacing=%{spacing}\npostscript=%{postscriptname}\n---\n' "$(GOKU_OUTPUT)"

terminal-inventory:
	python src/audit_terminal_graphics.py --collection "$(AUDIT_FONT)" --gohu-bdf "$(GOHU_REGULAR_BDF)" --output "$(TERMINAL_INVENTORY)"

terminal-graphics-audit:
	python src/terminal_graphics_audit.py --collection "$(AUDIT_FONT)"

terminal-compare:
	python src/render_terminal_comparison.py --old "$(OLD)" --new "$(NEW)" --output build/reports/terminal-graphics-comparison.png

# `quality-report` captures known findings without hiding them. `quality` is
# the strict release gate and currently fails until every recorded FAIL is
# fixed or explicitly justified in quality/FONTBAKERY.md.
quality-report: validate ots harfbuzz fontforge sfnt-audit-report fontbakery-report reproducible

quality: validate ots harfbuzz fontforge sfnt-audit fontbakery reproducible

quality-faces:
	rm -f "$(QUALITY_FACES)"/*.ttf
	python src/extract_faces.py --collection "$(QUALITY_FONT)" --output-dir "$(QUALITY_FACES)"

ots:
	mkdir -p "$(QUALITY_DIR)/ots"
	ots-sanitize "$(QUALITY_FONT)" "$(QUALITY_DIR)/ots/Goku-sanitized.ttc"

# Report all findings while reserving a nonzero status for tool/runtime errors.
# The strict target below fails on FontBakery FAIL findings.
fontbakery-report: quality-faces
	mkdir -p "$(QUALITY_DIR)/fontbakery"
	fontbakery check-universal --skip-network --no-progress --no-colors --succinct --jobs 4 --error-code-on ERROR --json "$(QUALITY_DIR)/fontbakery/report.json" --ghmarkdown "$(QUALITY_DIR)/fontbakery/report.md" $(QUALITY_FACES)/*.ttf

fontbakery: quality-faces
	mkdir -p "$(QUALITY_DIR)/fontbakery"
	fontbakery check-universal --skip-network --no-progress --no-colors --succinct --jobs 4 --json "$(QUALITY_DIR)/fontbakery/report.json" --ghmarkdown "$(QUALITY_DIR)/fontbakery/report.md" $(QUALITY_FACES)/*.ttf

fontforge: quality-faces
	mkdir -p "$(QUALITY_DIR)/fontforge"
	for face in "$(QUALITY_FACES)"/*.ttf; do \
		stem=$$(basename "$$face" .ttf); \
		fontforge -quiet -script src/fontforge_validate.py "$$face" --report "$(QUALITY_DIR)/fontforge/$$stem.json" 2>"$(QUALITY_DIR)/fontforge/$$stem.stderr.log" || exit $$?; \
	done

harfbuzz:
	python src/shaping_audit.py --collection "$(QUALITY_FONT)" --report "$(QUALITY_DIR)/harfbuzz.json"

sfnt-audit:
	python src/sfnt_audit.py --collection "$(QUALITY_FONT)" --sources SOURCES.md --gohu-license vendor/gohufont/COPYING-LICENSE --report "$(QUALITY_DIR)/sfnt.json"

sfnt-audit-report:
	python src/sfnt_audit.py --collection "$(QUALITY_FONT)" --sources SOURCES.md --gohu-license vendor/gohufont/COPYING-LICENSE --report "$(QUALITY_DIR)/sfnt.json" --report-only

reproducible:
	python src/reproducibility_audit.py --base-builder src/build_goku_collection.py --weight-builder src/build_weight_collection.py --pixel-builder src/pixelate_collection.py --hint-builder src/hint_pixel_collection.py --regular-bdf "$(GOHU_REGULAR_BDF)" --bold-bdf "$(GOHU_BOLD_BDF)" --reference "$(GOKU_OUTPUT)" --columns "$(PIXEL_COLUMNS)" --rows "$(PIXEL_ROWS)" --icon-columns "$(ICON_PIXEL_COLUMNS)" --icon-rows "$(ICON_PIXEL_ROWS)" --icon-threshold "$(ICON_PIXEL_THRESHOLD)" --icon-fallback-threshold "$(ICON_PIXEL_FALLBACK_THRESHOLD)" --threshold "$(PIXEL_THRESHOLD)" --weight-contrast "$(PIXEL_WEIGHT_CONTRAST)" --budgets quality/budgets.json --report "$(QUALITY_DIR)/reproducibility.json"

release: validate ots harfbuzz sfnt-audit reproducible
	python src/prepare_release.py --font "$(GOKU_OUTPUT)" --output-dir "$(RELEASE_DIR)" --reproducibility-report "$(QUALITY_DIR)/reproducibility.json" --notices THIRD_PARTY_NOTICES.md --release-notes RELEASE_NOTES.md --gohu-license "vendor/gohufont/COPYING-LICENSE"

icon-inventory:
	python src/audit_icons.py --collection "$(AUDIT_FONT)" --gohu-bdf "$(GOHU_REGULAR_BDF)" --output "$(ICON_INVENTORY)"

icon-classes: icon-inventory
	python src/classify_icons.py --inventory "$(ICON_INVENTORY)" --output "$(ICON_CLASSES)"

icon-policy: icon-classes
	python src/derive_icon_policy.py --classes "$(ICON_CLASSES)" --output "$(ICON_POLICY)"

p1-regression:
	python src/compare_candidate.py --baseline "$(BASELINE)" --candidate "$(CANDIDATE)" --regular-bdf "$(GOHU_REGULAR_BDF)" --bold-bdf "$(GOHU_BOLD_BDF)"

icon-atlas:
	python src/render_icon_atlas.py --baseline "$(BASELINE)" --candidate "$(CANDIDATE)" --policy "$(ICON_POLICY)" --output-dir build/reports/icon-atlas

clean:
	rm -rf build dist
