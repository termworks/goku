#!/usr/bin/env python3
"""Derive Goku's conservative, class-aware icon transform policy."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


IMMUTABLE_ROLES = {"powerline", "progress", "gohu"}
MIN_GROUP_SIZE = 20
# At native 14 px this is a little over half a vertical source pixel. Smaller
# deviations are not stable enough to justify modifying an upstream icon.
MIN_NORMALIZED_SIZE_EXCESS = 0.04
MIN_ALLOWED_SCALE = 0.80


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--classes", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rounded(value: float) -> float:
    return round(value, 6)


def derive_action(icon: dict[str, Any], groups: dict[str, Any]) -> dict[str, Any]:
    base = {
        "codepoint": icon["codepoint"],
        "glyph": icon["glyph"],
        "source": icon["source"],
        "role": icon["role"],
        "group": icon["group"],
    }
    if icon["role"] in IMMUTABLE_ROLES:
        return {**base, "action": "preserve", "reason": "immutable semantic role"}
    if not icon["metrics"]:
        return {**base, "action": "preserve", "reason": "intentional blank glyph"}
    group = groups.get(icon["group"])
    if group is None or group["count"] < MIN_GROUP_SIZE:
        return {**base, "action": "preserve", "reason": "class too small for policy"}

    metrics = icon["metrics"]
    target_width = group["metrics"]["width_ratio"]["p95"]
    target_height = group["metrics"]["height_ratio"]["p95"]
    width_excess = metrics["width_ratio"] - target_width
    height_excess = metrics["height_ratio"] - target_height
    scale = min(
        1.0,
        target_width / metrics["width_ratio"],
        target_height / metrics["height_ratio"],
    )
    if scale < 1 and max(width_excess, height_excess) >= MIN_NORMALIZED_SIZE_EXCESS:
        assert scale >= MIN_ALLOWED_SCALE, (
            f"policy would over-shrink {icon['codepoint']}: {scale}"
        )
        return {
            **base,
            "action": "scale_down",
            "reason": "exceeds class p95 bounding size",
            "scale": rounded(scale),
            "current": {
                "width_ratio": rounded(metrics["width_ratio"]),
                "height_ratio": rounded(metrics["height_ratio"]),
            },
            "target": {
                "width_ratio": target_width,
                "height_ratio": target_height,
            },
        }
    if icon["outlier_metrics"]:
        return {
            **base,
            "action": "review_only",
            "reason": "statistical exception without a safe automatic transform",
            "outlier_metrics": icon["outlier_metrics"],
        }
    return {**base, "action": "preserve", "reason": "inside class policy"}


def main() -> None:
    args = parse_args()
    classes = json.loads(args.classes.read_text(encoding="utf-8"))
    actions = [
        derive_action(icon, classes["groups"])
        for icon in classes["icons"]
    ]
    action_counts = Counter(action["action"] for action in actions)
    source_transforms = Counter(
        action["source"] for action in actions if action["action"] == "scale_down"
    )
    scales = [
        action["scale"] for action in actions if action["action"] == "scale_down"
    ]
    report = {
        "schema": 1,
        "classes": str(args.classes),
        "classes_sha256": sha256(args.classes),
        "collection_sha256": classes["collection_sha256"],
        "principles": [
            "never scale an icon up",
            "never transform Powerline, progress indicators, or Gohu glyphs",
            "never translate from ink centroid because asymmetric symbols carry meaning",
            "preserve statistically unusual icons unless a class-relative size rule is safe",
            "apply only uniform scaling around the terminal cell center",
        ],
        "parameters": {
            "size_target": "source/aspect/circular class p95 bounding width and height",
            "minimum_group_size": MIN_GROUP_SIZE,
            "minimum_normalized_size_excess": MIN_NORMALIZED_SIZE_EXCESS,
            "minimum_allowed_scale": MIN_ALLOWED_SCALE,
            "immutable_roles": sorted(IMMUTABLE_ROLES),
        },
        "summary": {
            "icons": len(actions),
            "action_counts": dict(sorted(action_counts.items())),
            "transforms_by_source": dict(sorted(source_transforms.items())),
            "minimum_scale": min(scales) if scales else None,
            "median_scale": sorted(scales)[len(scales) // 2] if scales else None,
            "maximum_scale": max(scales) if scales else None,
        },
        "actions": actions,
    }
    assert report["summary"]["icons"] == classes["summary"]["icons"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output}")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
