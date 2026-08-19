#!/usr/bin/env python3
"""Classify Goku icons and identify class-relative optical outliers."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROLE_BY_SOURCE = {
    "Powerline": "powerline",
    "Progress Indicators": "progress",
    "Weather Icons": "weather",
    "Seti-UI + Custom": "logo",
    "Devicons": "logo",
    "Font Logos": "logo",
    "GohuFont": "gohu",
}
CIRCULAR_NAME = re.compile(r"(?:^|[-_. ])(?:circle|circular|round)(?:$|[-_. ])", re.I)
MIN_GROUP_FOR_OUTLIERS = 20
MODIFIED_Z_LIMIT = 3.5
# Robust statistics alone overreact when a class has a zero-ish median absolute
# deviation (many Nerd icons are mathematically centered). Require a difference
# large enough to be visually meaningful at compact terminal sizes as well.
PRACTICAL_DELTA = {
    "width_ratio": 0.12,
    "height_ratio": 0.12,
    "bbox_area_ratio": 0.12,
    "ink_area_ratio": 0.08,
    "x_bbox_offset": 0.10,
    "y_bbox_offset": 0.10,
    "x_centroid_offset": 0.10,
    "y_centroid_offset": 0.10,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
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


def percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return rounded(ordered[lower])
    weight = position - lower
    return rounded(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def classify_aspect(width: int, height: int) -> str:
    if not width or not height:
        return "blank"
    ratio = width / height
    if ratio >= 1.25:
        return "wide"
    if ratio <= 0.8:
        return "tall"
    return "square"


def source_role(source: str) -> str:
    return ROLE_BY_SOURCE.get(source, "general")


def declared_circular(glyph_name: str) -> bool:
    return bool(CIRCULAR_NAME.search(glyph_name))


def metric_values(icon: dict[str, Any], cell: dict[str, int]) -> dict[str, float]:
    outline = icon["outline"]
    if outline["empty"]:
        return {}
    center_x = cell["advance"] / 2
    center_y = (cell["ascent"] + cell["descent"]) / 2
    centroid = outline["ink_centroid"]
    bbox_center = outline["bbox_center"]
    return {
        "width_ratio": outline["width"] / cell["advance"],
        "height_ratio": outline["height"] / (cell["ascent"] - cell["descent"]),
        "bbox_area_ratio": (
            outline["width"]
            * outline["height"]
            / (cell["advance"] * (cell["ascent"] - cell["descent"]))
        ),
        "ink_area_ratio": outline["area_ratio"],
        "x_bbox_offset": (bbox_center[0] - center_x) / cell["advance"],
        "y_bbox_offset": (
            (bbox_center[1] - center_y) / (cell["ascent"] - cell["descent"])
        ),
        "x_centroid_offset": (centroid[0] - center_x) / cell["advance"],
        "y_centroid_offset": (
            (centroid[1] - center_y) / (cell["ascent"] - cell["descent"])
        ),
    }


def median_absolute_deviation(values: list[float], median: float) -> float:
    result = percentile((abs(value - median) for value in values), 0.5)
    assert result is not None
    return result


def group_statistics(
    members: list[dict[str, Any]],
) -> dict[str, Any]:
    statistics: dict[str, Any] = {"count": len(members), "metrics": {}}
    if not members:
        return statistics
    for metric in next(iter(members))["metrics"]:
        values = [member["metrics"][metric] for member in members]
        median = percentile(values, 0.5)
        assert median is not None
        statistics["metrics"][metric] = {
            "minimum": rounded(min(values)),
            "p05": percentile(values, 0.05),
            "p25": percentile(values, 0.25),
            "median": median,
            "p75": percentile(values, 0.75),
            "p95": percentile(values, 0.95),
            "maximum": rounded(max(values)),
            "mad": rounded(median_absolute_deviation(values, median)),
        }
    return statistics


def outlier_metrics(icon: dict[str, Any], group: dict[str, Any]) -> list[str]:
    if group["count"] < MIN_GROUP_FOR_OUTLIERS:
        return []
    outliers: list[str] = []
    for metric, value in icon["metrics"].items():
        stats = group["metrics"][metric]
        mad = stats["mad"]
        if math.isclose(mad, 0.0, abs_tol=1e-9):
            continue
        modified_z = 0.67448975 * (value - stats["median"]) / mad
        if (
            abs(modified_z) > MODIFIED_Z_LIMIT
            and abs(value - stats["median"]) >= PRACTICAL_DELTA[metric]
        ):
            outliers.append(metric)
    return outliers


def main() -> None:
    args = parse_args()
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    cell = inventory["cell"]
    classified: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for icon in inventory["icons"]:
        outline = icon["outline"]
        aspect = classify_aspect(
            0 if outline["empty"] else outline["width"],
            0 if outline["empty"] else outline["height"],
        )
        role = source_role(icon["source"])
        circular = declared_circular(icon["glyph"])
        edge_observed = False if outline["empty"] else outline["touches_cell_edge"]
        edge_intent = role in {"powerline", "progress"}
        group_name = "|".join(
            (icon["source"], aspect, "circular" if circular else "other")
        )
        entry = {
            "codepoint": icon["codepoint"],
            "glyph": icon["glyph"],
            "source": icon["source"],
            "role": role,
            "aspect": aspect,
            "declared_circular": circular,
            "edge_observed": edge_observed,
            "edge_intent": edge_intent,
            "group": group_name,
            "metrics": metric_values(icon, cell),
            "outlier_metrics": [],
        }
        classified.append(entry)
        if entry["metrics"] and not edge_intent:
            grouped[group_name].append(entry)

    groups = {
        name: group_statistics(members)
        for name, members in sorted(grouped.items())
    }
    for icon in classified:
        if icon["group"] in groups and icon["metrics"]:
            icon["outlier_metrics"] = outlier_metrics(icon, groups[icon["group"]])

    outliers = [icon for icon in classified if icon["outlier_metrics"]]
    role_counts = Counter(icon["role"] for icon in classified)
    aspect_counts = Counter(icon["aspect"] for icon in classified)
    source_outliers = Counter(icon["source"] for icon in outliers)
    metric_outliers = Counter(
        metric for icon in outliers for metric in icon["outlier_metrics"]
    )
    report = {
        "schema": 1,
        "inventory": str(args.inventory),
        "inventory_sha256": sha256(args.inventory),
        "collection_sha256": inventory["collection_sha256"],
        "method": {
            "aspect": "wide >= 1.25, tall <= 0.8, otherwise square",
            "circular": "semantic glyph-name token: circle, circular, or round",
            "role": "upstream source-set role",
            "outlier": (
                "absolute modified z-score > 3.5 plus a metric-specific visual "
                "delta floor within source/aspect/circular groups of at least "
                "20 nonempty, non-edge-intent glyphs"
            ),
            "outlier_visual_delta_floors": PRACTICAL_DELTA,
        },
        "summary": {
            "icons": len(classified),
            "role_counts": dict(sorted(role_counts.items())),
            "aspect_counts": dict(sorted(aspect_counts.items())),
            "declared_circular": sum(icon["declared_circular"] for icon in classified),
            "observed_edge_touching": sum(icon["edge_observed"] for icon in classified),
            "intentional_edge_touching": sum(icon["edge_intent"] for icon in classified),
            "outlier_icons": len(outliers),
            "outlier_metrics": dict(sorted(metric_outliers.items())),
            "outliers_by_source": dict(sorted(source_outliers.items())),
            "groups": len(groups),
        },
        "groups": groups,
        "icons": classified,
    }
    assert report["summary"]["icons"] == inventory["summary"]["pua_mappings"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output}")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
