#!/usr/bin/env python3
"""
Report capability and price drift between the committed export and a
regeneration against an upstream snapshot. Report-only: it never writes to
filtered_models.json.

Categories (per model, per field):

* stale-true    — committed ``supports_*`` is true, regeneration is not.
                  The dangerous one: the dashboard forwards true flags to
                  LiteLLM, and a flag the vendor does not honour becomes a 400.
* missing-true  — regeneration is true, committed is not. The feature is
                  silently disabled downstream.
* changed-false — any other ``supports_*`` change (false <-> absent).
* price-changed — a price field present in the committed export changed or
                  disappeared. These affect billing.
* price-added   — a price field the committed export does not have yet.
* other-changed — any other difference, in raw_data or in the export's own
                  top-level fields (type, friendly_name, context limits...).
                  The dashboard reads those too — `type` decides modelType —
                  so a regeneration-consistency check must see them.

"Price" means any field that changes what a request is billed: every *cost*
field, tiered_pricing, off_peak_pricing (time-of-day rates),
provider_specific_entry (per-geo / per-speed multipliers) and the
*_multiplier fields. Several of these carry no "cost" in their name, which
is how a DeepSeek off-peak schedule and an Anthropic fast-mode multiplier
once slipped through a sync unreported.

Plus models added to / removed from the key set.

Limit: this compares the export with a regeneration, so a value that is
wrong in BOTH — upstream and committed alike — shows no drift. It is a
change detector, not a vendor audit.

Usage:
    python drift_report.py                      # vs live upstream (what a sync would bring)
    python drift_report.py --pinned             # vs the pinned snapshot (should be empty)
    python drift_report.py --regenerated x.json # compare an already-generated export
    python drift_report.py --pinned --fail-on stale-true
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Mapping

CATEGORIES = ("stale-true", "missing-true", "changed-false", "price-changed", "price-added", "other-changed")
MODEL_CATEGORIES = ("model-added", "model-removed")
_MISSING = object()


def is_capability_field(field: str) -> bool:
    return field.startswith("supports_")


_BILLING_FIELDS_WITHOUT_COST = frozenset({"tiered_pricing", "off_peak_pricing", "provider_specific_entry"})


def is_price_field(field: str) -> bool:
    return "cost" in field or field.endswith("_multiplier") or "_multiplier_" in field or field in _BILLING_FIELDS_WITHOUT_COST


def _classify_capability(old: Any, new: Any) -> str:
    if old is True:
        return "stale-true"
    if new is True:
        return "missing-true"
    return "changed-false"


def classify(
    committed: Mapping[str, Mapping[str, Any]],
    regenerated: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[tuple]]:
    """Classify every field-level difference.

    Both arguments map model_key -> export record (with ``raw_data``). Returns
    ``{category: [(model_key, field, committed_value, regenerated_value), ...]}``
    for field categories and ``{category: [(model_key,), ...]}`` for the model
    categories. Values absent on one side are reported as None.
    """
    report: dict[str, list[tuple]] = {c: [] for c in CATEGORIES + MODEL_CATEGORIES}

    for key in sorted(set(regenerated) - set(committed)):
        report["model-added"].append((key,))
    for key in sorted(set(committed) - set(regenerated)):
        report["model-removed"].append((key,))

    for key in sorted(set(committed) & set(regenerated)):
        old_raw = committed[key].get("raw_data", {})
        new_raw = regenerated[key].get("raw_data", {})
        for field in sorted(set(old_raw) | set(new_raw)):
            old = old_raw.get(field, _MISSING)
            new = new_raw.get(field, _MISSING)
            if old == new:
                continue
            shown = (None if old is _MISSING else old, None if new is _MISSING else new)
            if is_capability_field(field):
                report[_classify_capability(old, new)].append((key, field, *shown))
            elif is_price_field(field):
                category = "price-added" if old is _MISSING else "price-changed"
                report[category].append((key, field, *shown))
            else:
                report["other-changed"].append((key, field, *shown))
        # The export's own top-level fields are derived from raw_data, but a
        # hand edit can change them independently; report them as "top:<f>".
        old_top = {f: v for f, v in committed[key].items() if f != "raw_data"}
        new_top = {f: v for f, v in regenerated[key].items() if f != "raw_data"}
        for field in sorted(set(old_top) | set(new_top)):
            old, new = old_top.get(field), new_top.get(field)
            if old != new:
                report["other-changed"].append((key, f"top:{field}", old, new))
    return report


def render(report: Mapping[str, list[tuple]], title: str) -> str:
    lines = [f"# {title}", ""]
    total = sum(len(v) for v in report.values())
    if total == 0:
        lines.append("No drift.")
        return "\n".join(lines) + "\n"
    lines.append("| Category | Count |")
    lines.append("|---|---|")
    for category, rows in report.items():
        lines.append(f"| {category} | {len(rows)} |")
    for category, rows in report.items():
        if not rows:
            continue
        lines += ["", f"## {category} ({len(rows)})", ""]
        for row in rows:
            if len(row) == 1:
                lines.append(f"- `{row[0]}`")
            else:
                key, field, old, new = row
                lines.append(f"- `{key}` `{field}`: `{json.dumps(old)}` → `{json.dumps(new)}`")
    return "\n".join(lines) + "\n"


def failing(report: Mapping[str, list[tuple]], fail_on: list[str]) -> list[str]:
    """Categories named in ``fail_on`` (or all, for "any") that are non-empty."""
    wanted = set(report) if "any" in fail_on else set(fail_on)
    return [c for c in report if c in wanted and report[c]]


def main(argv: list[str] | None = None) -> int:
    from filter_models import load_upstream
    from model_sync_rules import ModelSyncRules

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--upstream", help="Upstream model dict as a URL or file path (default: live upstream)")
    source.add_argument("--pinned", action="store_true", help="Regenerate against the pinned snapshot")
    source.add_argument("--regenerated", help="Compare an already-generated export file instead of regenerating")
    parser.add_argument("--committed", default="filtered_models.json", help="Committed export to compare against")
    parser.add_argument(
        "--fail-on",
        action="append",
        default=[],
        choices=CATEGORIES + MODEL_CATEGORIES + ("any",),
        help="Exit 1 if this category is non-empty (repeatable; 'any' = all). Default: always exit 0",
    )
    parser.add_argument("--output", help="Also write the Markdown report to this file")
    args = parser.parse_args(argv)

    with open(args.committed, encoding="utf-8") as f:
        committed = json.load(f)["models"]

    if args.regenerated:
        with open(args.regenerated, encoding="utf-8") as f:
            regenerated = json.load(f)["models"]
        title = f"Drift: {args.committed} vs {args.regenerated}"
    else:
        upstream_source = (
            ModelSyncRules.UPSTREAM_SNAPSHOT_URL if args.pinned else args.upstream or ModelSyncRules.DATA_SOURCE_URL
        )
        regenerated = ModelSyncRules.filter_all_models(load_upstream(upstream_source))
        title = f"Drift: {args.committed} vs regeneration at {upstream_source}"

    report = classify(committed, regenerated)
    text = render(report, title)
    print(text)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)

    bad = failing(report, args.fail_on)
    if bad:
        print(f"FAIL: non-empty categories {bad}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
