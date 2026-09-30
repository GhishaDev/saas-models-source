#!/usr/bin/env python3
"""
Enforce the capability-overlay policy on the synth tables.

Policy (see README "Capability flags"):

* A synth entry for a key that is ABSENT upstream (pre-staged) may carry any
  ``supports_*`` flag — the synth entry is the only source of truth.
* A synth entry for a key that is PRESENT upstream must not carry a
  ``supports_*`` flag unless it deliberately overrides upstream. Every
  deliberate override is listed in ``ModelSyncRules.CAPABILITY_OVERRIDES``
  with the vendor source that justifies it.

Violations:

* ``redundant``         — the synth value equals upstream. It changes nothing
                          today and pins stale state the moment upstream moves.
                          Applies even to allowlisted pairs: an override that
                          upstream has caught up with must be retired.
* ``unlisted-override`` — the synth value differs from upstream (including
                          upstream not defining the flag) and the pair is not
                          in CAPABILITY_OVERRIDES.
* ``orphan-override``   — a CAPABILITY_OVERRIDES entry that no synth entry for
                          an upstream-present key actually sets. Dead
                          allowlist entries hide what is really overridden.

Exit status is 1 when any violation is found, 0 otherwise.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Any, Mapping

CAPABILITY_PREFIX = "supports_"
_MISSING = object()


@dataclass(frozen=True)
class Violation:
    kind: str
    table: str
    key: str
    flag: str
    synth_value: Any = None
    upstream_value: Any = None

    def describe(self) -> str:
        if self.kind == "orphan-override":
            return f"{self.kind}: ({self.key!r}, {self.flag!r}) is allowlisted but no synth entry sets it"
        upstream = "<absent>" if self.upstream_value is _MISSING else repr(self.upstream_value)
        return (
            f"{self.kind}: {self.table}[{self.key!r}][{self.flag!r}] = "
            f"{self.synth_value!r} (upstream: {upstream})"
        )


def synth_tables(rules: type) -> dict[str, Mapping[str, Mapping[str, Any]]]:
    """Every ``*_SYNTH_DATA`` table defined on the rules class, by name."""
    return {
        name: getattr(rules, name)
        for name in sorted(dir(rules))
        if name.endswith("_SYNTH_DATA")
    }


def find_violations(
    tables: Mapping[str, Mapping[str, Mapping[str, Any]]],
    upstream: Mapping[str, Mapping[str, Any]],
    overrides: Mapping[tuple[str, str], str],
) -> list[Violation]:
    """Return every capability-policy violation. Pure: no I/O, no globals."""
    violations: list[Violation] = []
    used: set[tuple[str, str]] = set()

    for table_name, table in tables.items():
        for key, entry in table.items():
            if key not in upstream:
                continue  # pre-staged: the synth entry is authoritative
            upstream_entry = upstream[key]
            for flag, synth_value in entry.items():
                if not flag.startswith(CAPABILITY_PREFIX):
                    continue
                upstream_value = upstream_entry.get(flag, _MISSING)
                pair = (key, flag)
                if pair in overrides:
                    used.add(pair)  # reported once below, never also as an orphan
                if upstream_value is not _MISSING and upstream_value == synth_value:
                    violations.append(
                        Violation("redundant", table_name, key, flag, synth_value, upstream_value)
                    )
                elif pair not in overrides:
                    violations.append(
                        Violation("unlisted-override", table_name, key, flag, synth_value, upstream_value)
                    )

    for key, flag in sorted(set(overrides) - used):
        violations.append(Violation("orphan-override", "CAPABILITY_OVERRIDES", key, flag))

    return violations


def main(argv: list[str] | None = None) -> int:
    from filter_models import load_upstream
    from model_sync_rules import ModelSyncRules

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--upstream",
        default=ModelSyncRules.UPSTREAM_SNAPSHOT_URL,
        help="Upstream model dict as a URL or file path (default: the pinned snapshot)",
    )
    args = parser.parse_args(argv)

    upstream = load_upstream(args.upstream)
    violations = find_violations(
        synth_tables(ModelSyncRules), upstream, ModelSyncRules.CAPABILITY_OVERRIDES
    )
    if not violations:
        print(f"capability policy: OK ({len(ModelSyncRules.CAPABILITY_OVERRIDES)} allowlisted overrides)")
        return 0
    print(f"capability policy: {len(violations)} violation(s)")
    for v in violations:
        print("  " + v.describe())
    return 1


if __name__ == "__main__":
    sys.exit(main())
