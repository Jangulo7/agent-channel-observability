"""Retrofit `schema_version` onto the records that schema 4.2 newly covers.

Before schema 4.2 only `results/observability_record_reasoning.json` carried a
`schema_version` and was the only record the committed JSON Schema described. The
monitor arms, the header and route contrasts and the long-horizon depth arm - every
record behind the paper's headline findings - were unvalidated. 4.2 extends the schema
to all four shapes; this script adds the version field to the records that lack it so
they validate, and renames `preregistration_commit` to `prespecification_commit`, which
is what the endpoints actually are: git-committed before any label existed, but with no
independent registration.

The script is additive and idempotent. It changes no measured value: every write is
checked against the pre-image first, and the run aborts if any pre-existing value other
than the one renamed key would change. Run it twice and the second run is a no-op.

    .venv/bin/python scripts/migrate_record_schema_version.py --check
    .venv/bin/python scripts/migrate_record_schema_version.py
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from channels.record import SCHEMA_COVERED_RECORDS, SCHEMA_VERSION

RESULTS = Path("results")
SCHEMA_FILE = RESULTS / "record_schema.json"
OLD_PROVENANCE_KEY = "preregistration_commit"
NEW_PROVENANCE_KEY = "prespecification_commit"


def _records() -> list[Path]:
    """The records the schema covers, in the order `SCHEMA_COVERED_RECORDS` lists.

    An explicit list, not a glob over results/: the annotation label files and the
    detector validation records live there too, have their own shapes and their own
    tests, and are not measurement records. A glob would migrate them by accident.
    """
    return [RESULTS / name for name in SCHEMA_COVERED_RECORDS]


def _migrate(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return a migrated copy of one record, plus a list of what changed."""
    migrated = copy.deepcopy(payload)
    changes: list[str] = []

    # The observability record already carries its version inside its single
    # top-level block; the other three shapes have nowhere to put it but the top
    # level. Bump a nested version where one exists, add a top-level one where none
    # does, and never both - the schema branches forbid a stray extra key.
    nested = [
        block
        for block in migrated.values()
        if isinstance(block, dict) and "schema_version" in block
    ]
    for block in nested:
        if block["schema_version"] != SCHEMA_VERSION:
            was = block["schema_version"]
            block["schema_version"] = SCHEMA_VERSION
            changes.append(f"bumped schema_version {was} -> {SCHEMA_VERSION}")
    if not nested and "schema_version" not in migrated:
        migrated = {"schema_version": SCHEMA_VERSION, **migrated}
        changes.append(f"added schema_version {SCHEMA_VERSION}")
    elif not nested and migrated["schema_version"] != SCHEMA_VERSION:
        was = migrated["schema_version"]
        migrated["schema_version"] = SCHEMA_VERSION
        changes.append(f"bumped schema_version {was} -> {SCHEMA_VERSION}")

    for key, block in migrated.items():
        if isinstance(block, dict) and OLD_PROVENANCE_KEY in block:
            # Rebuild in place rather than pop-and-append, so the key keeps its
            # position and the record's diff stays readable.
            migrated[key] = {
                (NEW_PROVENANCE_KEY if name == OLD_PROVENANCE_KEY else name): value
                for name, value in block.items()
            }
            changes.append(f"renamed {OLD_PROVENANCE_KEY} -> {NEW_PROVENANCE_KEY}")

    return migrated, changes


def _assert_values_preserved(before: Any, after: Any, path: str = "") -> None:
    """Raise unless `after` preserves every measured value in `before`.

    The project's rule is that a record is the source of truth: a migration may add a
    metadata key or rename a provenance key, never revise a measurement. Anything
    else must stop the run, because a silently rewritten number in a published record
    is the failure this whole project is about.
    """
    if isinstance(before, dict):
        if not isinstance(after, dict):
            raise SystemExit(f"{path or '<root>'}: a mapping became {type(after)}")
        for key, value in before.items():
            if key == OLD_PROVENANCE_KEY:
                if after.get(NEW_PROVENANCE_KEY) != value:
                    raise SystemExit(f"{path}/{key}: value lost in the rename")
                continue
            if key == "schema_version":
                continue  # the one field this migration is allowed to set
            if key not in after:
                raise SystemExit(f"{path}/{key}: pre-existing key was removed")
            _assert_values_preserved(value, after[key], f"{path}/{key}")
    elif isinstance(before, list):
        if not isinstance(after, list) or len(after) != len(before):
            raise SystemExit(f"{path}: a list changed length or type")
        for index, value in enumerate(before):
            _assert_values_preserved(value, after[index], f"{path}[{index}]")
    elif before != after:
        raise SystemExit(f"{path}: {before!r} would become {after!r}")


def main() -> int:
    """Migrate every record that needs it; with --check, report without writing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report what would change and exit non-zero if anything would",
    )
    args = parser.parse_args()

    stale = 0
    for path in _records():
        payload = json.loads(path.read_text())
        migrated, changes = _migrate(payload)
        if not changes:
            print(f"ok       {path}")
            continue
        _assert_values_preserved(payload, migrated)
        stale += 1
        print(f"migrate  {path}: {'; '.join(changes)}")
        if not args.check:
            path.write_text(json.dumps(migrated, indent=2) + "\n")

    if args.check and stale:
        print(f"{stale} record(s) are stale; run without --check to migrate")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
