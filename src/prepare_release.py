#!/usr/bin/env python3
"""Assemble deterministic GitHub release assets for Goku."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from fontTools.ttLib import TTCollection

from design import SOURCE_DATE_EPOCH, VERSION


EXPECTED_STYLES = [
    str(weight) + (" Italic" if italic else "")
    for weight in range(100, 1000, 100)
    for italic in (False, True)
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--reproducibility-report", required=True, type=Path)
    parser.add_argument("--notices", required=True, type=Path)
    parser.add_argument("--release-notes", required=True, type=Path)
    parser.add_argument("--gohu-license", required=True, type=Path)
    return parser.parse_args()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def atomic_copy(source: Path, destination: Path) -> None:
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
        temporary = Path(stream.name)
        with source.open("rb") as source_stream:
            shutil.copyfileobj(source_stream, stream)
    os.chmod(temporary, 0o644)
    os.replace(temporary, destination)


def atomic_text(destination: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=destination.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    os.chmod(temporary, 0o644)
    os.replace(temporary, destination)


def name(font, name_id: int) -> str:
    value = font["name"].getDebugName(name_id)
    if not value:
        raise ValueError(f"missing name ID {name_id}")
    return value


def inspect_faces(path: Path, family: str, postscript_stem: str) -> list[dict]:
    collection = TTCollection(path, lazy=True)
    try:
        if len(collection.fonts) != 18:
            raise ValueError(f"release contains {len(collection.fonts)} faces, expected 18")
        faces = []
        for index, (font, expected_style) in enumerate(
            zip(collection.fonts, EXPECTED_STYLES)
        ):
            style = name(font, 17)
            if style != expected_style:
                raise ValueError(
                    f"face {index} is {style!r}, expected {expected_style!r}"
                )
            weight = int(style.split()[0])
            italic = style.endswith(" Italic")
            expected_postscript = (
                f"{postscript_stem}-{weight}{'Italic' if italic else ''}"
            )
            if name(font, 16) != family:
                raise ValueError(f"unexpected family name for {style}")
            if name(font, 6) != expected_postscript:
                raise ValueError(f"unexpected PostScript name for {style}")
            if name(font, 5) != f"Version {VERSION}; Goku":
                raise ValueError(f"unexpected version metadata for {style}")
            if font["OS/2"].usWeightClass != weight:
                raise ValueError(f"unexpected weight class for {style}")
            faces.append(
                {
                    "index": index,
                    "style": style,
                    "postscript_name": expected_postscript,
                    "weight": weight,
                    "italic": italic,
                }
            )
        return faces
    finally:
        collection.close()


def main() -> None:
    args = parse_args()
    reproducibility = json.loads(
        args.reproducibility_report.read_text(encoding="utf-8")
    )
    candidate = reproducibility["candidate"]
    if reproducibility["failures"]:
        raise ValueError("reproducibility report contains failures")
    if not candidate["byte_identical"] or not candidate["matches_release"]:
        raise ValueError("release was not reproduced byte-for-byte")

    faces = inspect_faces(args.font, "Goku", "Goku")
    font_sha256 = digest(args.font)
    if candidate["sha256"] != font_sha256:
        raise ValueError("reproducibility SHA-256 does not match release font")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for obsolete in ("Goku-Pixel.ttc", "Goku-Pixel.ttc.sha256"):
        (args.output_dir / obsolete).unlink(missing_ok=True)
    release_font = args.output_dir / "Goku.ttc"
    atomic_copy(args.font, release_font)
    atomic_copy(args.notices, args.output_dir / "THIRD_PARTY_NOTICES.md")
    atomic_copy(args.release_notes, args.output_dir / "RELEASE_NOTES.md")
    atomic_copy(args.gohu_license, args.output_dir / "GohuFont-WTFPL.txt")
    atomic_text(
        args.output_dir / "Goku.ttc.sha256",
        f"{font_sha256}  Goku.ttc\n",
    )
    atomic_text(
        args.output_dir / "SHA256SUMS",
        f"{font_sha256}  Goku.ttc\n",
    )

    manifest = {
        "format": 3,
        "release": f"Goku {VERSION}",
        "source_date_epoch": SOURCE_DATE_EPOCH,
        "font": {
            "file": "Goku.ttc",
            "outline_model": "universal-pixel-grid",
            "bytes": release_font.stat().st_size,
            "sha256": font_sha256,
            "faces": faces,
        },
        "validation": {
            "base_and_weight_audits": "passed",
            "harfbuzz": "passed",
            "opentype_sanitizer": "passed",
            "sfnt_integrity": "passed",
            "clean_build_byte_identical": True,
        },
    }
    atomic_text(
        args.output_dir / "release.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )
    print(f"Prepared Goku {VERSION} release assets in {args.output_dir}")
    print(f"  Goku.ttc: {release_font.stat().st_size:,} bytes")
    print(f"  SHA-256: {font_sha256}")
    print(f"  faces: {len(faces)} pixel-grid faces")


if __name__ == "__main__":
    main()
