#!/usr/bin/env python3
"""Audit Goku table integrity, cmap consistency, reachability and licensing."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTCollection
from fontTools.ttLib.sfnt import calcChecksum


EXPECTED_STYLES = {
    str(weight) + (" Italic" if italic else "")
    for weight in range(100, 1000, 100)
    for italic in (False, True)
}
CONVENTIONAL_UNENCODED = {".notdef", ".null", "nonmarkingreturn"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", required=True, type=Path)
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--gohu-license", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--report-only", action="store_true")
    return parser.parse_args()


def names(font, name_id: int) -> set[str]:
    return {
        record.toUnicode()
        for record in font["name"].names
        if record.nameID == name_id
    }


def style(font) -> str:
    matches = names(font, 17) & EXPECTED_STYLES
    assert len(matches) == 1, matches
    return matches.pop()


def table_checksum_failures(font) -> list[dict]:
    failures: list[dict] = []
    for tag, entry in sorted(font.reader.tables.items()):
        data = font.reader[tag]
        # The head table's directory checksum is calculated with its
        # checkSumAdjustment field zeroed (OpenType `head` requirement).
        if tag == "head":
            data = data[:8] + b"\0\0\0\0" + data[12:]
        actual = calcChecksum(data)
        if actual != entry.checkSum:
            failures.append(
                {
                    "table": tag,
                    "recorded": f"0x{entry.checkSum:08X}",
                    "actual": f"0x{actual:08X}",
                }
            )
    return failures


def cmap_audit(font) -> dict:
    unicode_tables = [table for table in font["cmap"].tables if table.isUnicode()]
    signatures = [
        (table.platformID, table.platEncID, table.language, table.format)
        for table in unicode_tables
    ]
    duplicate_records = [
        signature for signature, count in Counter(signatures).items() if count > 1
    ]
    mappings: dict[int, set[str]] = defaultdict(set)
    for table in unicode_tables:
        for codepoint, glyph_name in table.cmap.items():
            mappings[codepoint].add(glyph_name)
    conflicts = {
        f"U+{codepoint:04X}": sorted(glyph_names)
        for codepoint, glyph_names in mappings.items()
        if len(glyph_names) > 1
    }
    best = font.getBestCmap()
    aliases = Counter(best.values())
    return {
        "unicode_subtables": [list(signature) for signature in signatures],
        "duplicate_subtable_records": [list(item) for item in duplicate_records],
        "conflicting_codepoints": conflicts,
        "best_cmap_mappings": len(best),
        "aliased_glyphs": sum(count > 1 for count in aliases.values()),
    }


def reachability_audit(font) -> dict:
    glyph_order = font.getGlyphOrder()
    requested = set(font.getBestCmap().values()) | (
        CONVENTIONAL_UNENCODED & set(glyph_order)
    )
    subsetter = Subsetter(Options())
    subsetter.populate(glyphs=requested)
    # FontTools' closure follows GSUB outputs and composite components without
    # writing a subset. The dev shell pins this implementation via flake.lock.
    subsetter._closure_glyphs(font)
    reachable = set(subsetter.glyphs_retained)
    unreachable = sorted(set(glyph_order) - reachable)
    return {
        "total_glyphs": len(glyph_order),
        "cmap_seed_glyphs": len(set(font.getBestCmap().values())),
        "conventional_unencoded": sorted(CONVENTIONAL_UNENCODED & set(glyph_order)),
        "closure_glyphs": len(reachable),
        "unreachable": unreachable,
    }


def main() -> None:
    args = parse_args()
    sources = args.sources.read_text(encoding="utf-8")
    gohu_license = args.gohu_license.read_text(encoding="utf-8", errors="replace")
    assert "GohuFont" in sources and "Nerd Fonts" in sources
    assert "cc36b8c9fed7141763e55dcee0a97abffcf08224" in sources
    assert "WTFPL" in sources and "DO WHAT THE FUCK YOU WANT" in gohu_license.upper()

    collection = TTCollection(args.collection, lazy=True)
    assert len(collection.fonts) == 18
    face_reports: list[dict] = []
    failures: list[str] = []
    reference_cmap = None
    reference_order = None

    for index, font in enumerate(collection.fonts):
        face_style = style(font)
        checksums = table_checksum_failures(font)
        cmap = cmap_audit(font)
        reachability = reachability_audit(font)
        copyright_records = names(font, 0)
        license_records = names(font, 13)

        if checksums:
            failures.append(f"{face_style}: invalid table checksums: {checksums}")
        if cmap["duplicate_subtable_records"]:
            failures.append(
                f"{face_style}: duplicate cmap records: "
                f"{cmap['duplicate_subtable_records']}"
            )
        if cmap["conflicting_codepoints"]:
            failures.append(
                f"{face_style}: conflicting cmap mappings: "
                f"{cmap['conflicting_codepoints']}"
            )
        if reachability["unreachable"]:
            failures.append(
                f"{face_style}: unreachable glyphs: {reachability['unreachable']}"
            )
        if not copyright_records or not license_records:
            failures.append(f"{face_style}: missing embedded rights/license names")
        combined_rights = " ".join(copyright_records | license_records)
        if "Gohu" not in combined_rights or "Nerd Fonts" not in combined_rights:
            failures.append(f"{face_style}: incomplete embedded attribution")
        if "WTFPL" not in combined_rights:
            failures.append(f"{face_style}: missing embedded Gohu license")
        if font["OS/2"].fsType != 0:
            failures.append(
                f"{face_style}: OS/2 fsType is 0x{font['OS/2'].fsType:X}, "
                "expected 0x0 for installable embedding"
            )

        best_cmap = font.getBestCmap()
        glyph_order = font.getGlyphOrder()
        if reference_cmap is None:
            reference_cmap = best_cmap
            reference_order = glyph_order
        else:
            if best_cmap != reference_cmap:
                failures.append(f"{face_style}: cmap differs from face 100")
            if glyph_order != reference_order:
                failures.append(f"{face_style}: glyph order differs from face 100")

        face_reports.append(
            {
                "face_index": index,
                "style": face_style,
                "tables": len(font.reader.tables),
                "checksum_failures": checksums,
                "cmap": cmap,
                "reachability": reachability,
                "embedding_fstype": font["OS/2"].fsType,
                "copyright": sorted(copyright_records),
                "license": sorted(license_records),
            }
        )

    collection.close()
    if {face["style"] for face in face_reports} != EXPECTED_STYLES:
        failures.append("collection does not contain exactly numeric styles 100-900 with italics")
    report = {
        "collection": str(args.collection),
        "source_manifest": str(args.sources),
        "gohu_license": str(args.gohu_license),
        "faces": face_reports,
        "failures": failures,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print("sfnt integrity audit complete")
    for face in face_reports:
        print(
            f"  face {face['face_index']} {face['style']}: "
            f"{face['tables']} table checksums; "
            f"{face['cmap']['best_cmap_mappings']} cmap mappings; "
            f"{face['reachability']['closure_glyphs']} reachable glyphs"
        )
    print("  source provenance and embedded license metadata present")
    if failures:
        print(f"  release-gating findings: {len(failures)}")
        for failure in failures:
            print(f"    {failure}")
        if not args.report_only:
            raise SystemExit(1)
    else:
        print("  release-gating findings: none")


if __name__ == "__main__":
    main()
