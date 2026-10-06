"""Full-denominator recall bounds for the monitor arms, from the committed record.

The monitor record keeps per-step aggregates, not per-trajectory verdicts: the run that
produced it aggregated them and did not store them, so the exact monotone
full-denominator curve cannot be recomputed without re-scoring. It can still be
bracketed. This prints, per arm and channel, the survivor-conditioned recall the record
already holds beside the interval that must contain the full-denominator value, using
`channels.monitor.cumulative_recall_full_bounds`.

No model call, no network. Reads one committed record and writes only counts.

    .venv/bin/python scripts/report_monitor_bounds.py
    .venv/bin/python scripts/report_monitor_bounds.py --write

`--write` adds a `recall_full_bounds` block per arm and channel to the record. It is
append-only: the script refuses to run if any pre-existing value would change.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from channels.monitor import RecallBound, cumulative_recall_full_bounds

RECORD = Path("results/monitor_experiment_qwen3/monitor_record.json")
CHANNELS = ("reasoning", "action")


def _arm_bounds(arm: dict[str, Any], channel: str) -> list[RecallBound]:
    """Bounds for one arm and channel, from that arm's committed aggregates."""
    survivor = arm["recall_by_step"][channel]
    flags_by_step = arm["flag_rate_by_step"][channel]
    lengths = arm["positive_trajectory_lengths"]
    _assert_denominators_agree(lengths, survivor)
    return cumulative_recall_full_bounds(
        lengths,
        [point["n_caught_by_here"] for point in survivor],
        [flags_by_step[str(point["step_index"])]["flag"] for point in survivor],
    )


def _assert_denominators_agree(
    lengths: list[int], survivor: list[dict[str, Any]]
) -> None:
    """Raise unless the record's survivor denominator matches the trajectory lengths.

    The bounds derive `reaching(j)` from the lengths; the record states it separately
    as `n_positive_reaching`. If the two disagree the record is internally
    inconsistent, which would invalidate both the published curve and these bounds,
    so it must stop the run rather than be reconciled silently.
    """
    for point in survivor:
        step = point["step_index"]
        derived = sum(1 for length in lengths if step < length)
        if derived != point["n_positive_reaching"]:
            raise SystemExit(
                f"step {step}: record says {point['n_positive_reaching']} "
                f"trajectories reach it, trajectory lengths imply {derived}"
            )


def _as_json(bounds: list[RecallBound]) -> list[dict[str, Any]]:
    """Serialise bounds as plain counts and rates, in record order."""
    return [
        {
            "step_index": bound.step_index,
            "n_positive": bound.n_positive,
            "caught_low": bound.caught_low,
            "caught_high": bound.caught_high,
            "recall_low": bound.recall_low,
            "recall_high": bound.recall_high,
        }
        for bound in bounds
    ]


def _report(arm_name: str, channel: str, bounds: list[RecallBound]) -> None:
    """Print one arm-and-channel block, ending with the ever-caught interval."""
    print(f"  {arm_name} / {channel}")
    for bound in bounds:
        print(
            f"    step {bound.step_index}: "
            f"caught {bound.caught_low}-{bound.caught_high} of {bound.n_positive}  "
            f"recall [{bound.recall_low:.3f}, {bound.recall_high:.3f}]"
        )
    final = bounds[-1]
    print(
        f"    ever caught: [{final.caught_low}/{final.n_positive}, "
        f"{final.caught_high}/{final.n_positive}] = "
        f"[{final.recall_low:.3f}, {final.recall_high:.3f}]"
    )


def main() -> int:
    """Print the bounds; with --write, append them to the record."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="append a recall_full_bounds block to the record (append-only)",
    )
    args = parser.parse_args()

    if not RECORD.exists():
        print(f"no record at {RECORD}")
        return 1

    payload = json.loads(RECORD.read_text())
    before = copy.deepcopy(payload)
    arms = payload["monitor_experiment"]["arms"]

    print(f"full-denominator recall bounds, from {RECORD}")
    print(
        "(the exact curve needs per-trajectory verdicts, "
        "which this run did not keep)"
    )
    for arm_name, arm in arms.items():
        for channel in CHANNELS:
            bounds = _arm_bounds(arm, channel)
            _report(arm_name, channel, bounds)
            arm.setdefault("recall_full_bounds", {})[channel] = _as_json(bounds)

    if not args.write:
        return 0

    _assert_append_only(before, payload)
    RECORD.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    print(f"wrote {RECORD}")
    return 0


def _assert_append_only(before: Any, after: Any, path: str = "") -> None:
    """Raise unless `after` only adds keys to `before`.

    The project's rule is that a record is the source of truth: a script may add a
    derived block to one, never revise a measured value. This enforces it rather than
    trusting the caller, so a future edit to this script cannot silently rewrite a
    published number.
    """
    if isinstance(before, dict):
        if not isinstance(after, dict):
            raise SystemExit(f"{path or '<root>'}: a mapping became {type(after)}")
        for key, value in before.items():
            if key not in after:
                raise SystemExit(f"{path}/{key}: pre-existing key was removed")
            _assert_append_only(value, after[key], f"{path}/{key}")
    elif isinstance(before, list):
        if not isinstance(after, list) or len(after) != len(before):
            raise SystemExit(f"{path}: a list changed length or type")
        for index, value in enumerate(before):
            _assert_append_only(value, after[index], f"{path}[{index}]")
    elif before != after:
        raise SystemExit(f"{path}: {before!r} would become {after!r}")


if __name__ == "__main__":
    raise SystemExit(main())
