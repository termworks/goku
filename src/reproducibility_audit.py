#!/usr/bin/env python3
"""Build the numeric Goku release twice and enforce reproducibility budgets."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-builder", required=True, type=Path)
    parser.add_argument("--weight-builder", required=True, type=Path)
    parser.add_argument("--regular-bdf", required=True, type=Path)
    parser.add_argument("--bold-bdf", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--budgets", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def build(args: argparse.Namespace, output: Path, log: Path) -> float:
    started = time.perf_counter()
    base = output.with_name("Goku-Base.ttc")
    with log.open("w", encoding="utf-8") as stream:
        subprocess.run(
            (
                sys.executable,
                str(args.base_builder),
                "--regular-bdf",
                str(args.regular_bdf),
                "--bold-bdf",
                str(args.bold_bdf),
                "--output",
                str(base),
            ),
            check=True,
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
        subprocess.run(
            (
                sys.executable,
                str(args.weight_builder),
                "--source",
                str(base),
                "--regular-bdf",
                str(args.regular_bdf),
                "--bold-bdf",
                str(args.bold_bdf),
                "--output",
                str(output),
                "--family",
                "Goku",
            ),
            check=True,
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
    return time.perf_counter() - started


def main() -> None:
    args = parse_args()
    budgets = json.loads(args.budgets.read_text(encoding="utf-8"))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    first_log = args.report.parent / "clean-build-1.log"
    second_log = args.report.parent / "clean-build-2.log"
    with tempfile.TemporaryDirectory(prefix="goku-repro-") as directory:
        temporary = Path(directory)
        first = temporary / "first" / "Goku.ttc"
        second = temporary / "second" / "Goku.ttc"
        first.parent.mkdir()
        second.parent.mkdir()
        first_seconds = build(args, first, first_log)
        second_seconds = build(args, second, second_log)
        first_bytes = first.read_bytes()
        second_bytes = second.read_bytes()
        first_hash = digest(first)
        second_hash = digest(second)
        size = len(first_bytes)

    failures: list[str] = []
    if first_bytes != second_bytes:
        failures.append("independent builds are not byte-identical")
    reference_bytes = args.reference.read_bytes()
    if first_bytes != reference_bytes:
        failures.append("clean build does not match the release artifact")
    if size > budgets["max_release_bytes"]:
        failures.append(
            f"release is {size} bytes; budget is {budgets['max_release_bytes']}"
        )
    for label, seconds in (("first", first_seconds), ("second", second_seconds)):
        if seconds > budgets["max_clean_build_seconds"]:
            failures.append(
                f"{label} build took {seconds:.3f}s; budget is "
                f"{budgets['max_clean_build_seconds']:.3f}s"
            )

    reference_size = len(reference_bytes)
    reference_hash = digest(args.reference)
    report = {
        "builders": {
            "base": str(args.base_builder),
            "weights": str(args.weight_builder),
        },
        "reference": {
            "path": str(args.reference),
            "bytes": reference_size,
            "sha256": reference_hash,
        },
        "candidate": {
            "bytes": size,
            "sha256": first_hash,
            "second_sha256": second_hash,
            "byte_identical": first_bytes == second_bytes,
            "matches_release": first_bytes == reference_bytes,
            "size_change_bytes": size - reference_size,
            "first_build_seconds": round(first_seconds, 3),
            "second_build_seconds": round(second_seconds, 3),
            "build_logs": [str(first_log), str(second_log)],
        },
        "budgets": budgets,
        "failures": failures,
    }
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("Clean-build reproducibility audit")
    print(f"  SHA-256: {first_hash}")
    print(f"  byte-identical: {first_bytes == second_bytes}")
    print(
        f"  size: {size:,} bytes ({size - reference_size:+,} vs "
        f"{args.reference.name})"
    )
    print(f"  build times: {first_seconds:.3f}s / {second_seconds:.3f}s")
    print(
        f"  budgets: {budgets['max_release_bytes']:,} bytes; "
        f"{budgets['max_clean_build_seconds']:.1f}s/build"
    )
    if failures:
        for failure in failures:
            print(f"  FAIL: {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
