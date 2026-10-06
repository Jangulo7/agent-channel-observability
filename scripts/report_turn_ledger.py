"""The turn ledger: one row per arm the paper actually uses, and their total.

The paper previously opened with "Across 23,541 assistant turns", a figure that counts
the six corpora the artifact measures - including two the paper explicitly scopes out -
and excludes the follow-up and SWE-bench arms the paper's own findings rest on. It is a
true statement about the artifact and a misleading one about the findings, so the repo
metadata keeps it and the paper uses this ledger instead.

Every count is read from a committed record. Nothing here is typed by hand.

    .venv/bin/python scripts/report_turn_ledger.py
    .venv/bin/python scripts/report_turn_ledger.py --latex
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

RESULTS = Path("results")
SWEEP = RESULTS / "observability_record_reasoning.json"
FOLLOWUP = RESULTS / "turn_boundary_followup.json"
LONGHORIZON = RESULTS / "swebench_longhorizon" / "longhorizon.json"
MONITOR = RESULTS / "monitor_experiment_qwen3" / "monitor_record.json"


@dataclass(frozen=True)
class Row:
    """One arm of the paper, with the record the count came from."""

    arm: str
    task_family: str
    configuration: str
    turns: int
    record: str


def _sweep_rows() -> list[Row]:
    """The nine-arm reasoning sweep behind Figure 1."""
    record = json.loads(SWEEP.read_text())["observability_record"]
    per_arm: dict[str, int] = {}
    for cell in record["emission"]["cells"]:
        per_arm[cell["model"]] = per_arm.get(cell["model"], 0) + cell["n_turns"]
    return [
        Row(arm, "sycophancy / xstest / strong_reject", "reasoning sweep", turns,
            "observability_record_reasoning.json")
        for arm, turns in sorted(per_arm.items())
    ]


def _followup_rows() -> list[Row]:
    """The header and route contrast arms, by family then arm."""
    record = json.loads(FOLLOWUP.read_text())
    rows: list[Row] = []
    for family, arms in sorted(record.items()):
        if not isinstance(arms, dict) or family == "schema_version":
            continue
        for arm, block in sorted(arms.items()):
            turns = sum(bucket["n"] for bucket in block["buckets"].values())
            providers = "/".join(sorted(block.get("providers", {}))) or "unrecorded"
            rows.append(
                Row(arm, family.replace("_followup", ""), providers, turns,
                    "turn_boundary_followup.json")
            )
    return rows


def _longhorizon_rows() -> list[Row]:
    """The SWE-bench depth arms."""
    arms = json.loads(LONGHORIZON.read_text())["swebench_longhorizon"]["arms"]
    rows: list[Row] = []
    for arm, block in sorted(arms.items()):
        turns = sum(step["n"] for step in block["by_step"].values())
        providers = "/".join(sorted(block.get("providers", {}))) or "unrecorded"
        rows.append(Row(arm, "swe_bench_verified", providers, turns,
                        "swebench_longhorizon/longhorizon.json"))
    return rows


def _monitor_turns() -> dict[str, int]:
    """Reasoning-channel turns scored per monitor arm, over positive trajectories only.

    Counted separately from the ledger total: these are turns of the positive
    trajectories only, the negatives were never scored (see the paper's limitations),
    so they are not a corpus the way the rows above are.
    """
    arms = json.loads(MONITOR.read_text())["monitor_experiment"]["arms"]
    return {
        arm: sum(
            sum(counts.values())
            for counts in block["flag_rate_by_step"]["reasoning"].values()
        )
        for arm, block in sorted(arms.items())
    }


def main() -> int:
    """Print the ledger as plain text, or as a LaTeX table with --latex."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latex", action="store_true", help="emit a LaTeX tabular")
    args = parser.parse_args()

    groups = [
        ("reasoning sweep (Figure 1)", _sweep_rows()),
        ("header and route contrasts", _followup_rows()),
        ("SWE-bench long horizon", _longhorizon_rows()),
    ]
    total = sum(row.turns for group in groups for row in group[1])

    if args.latex:
        print(r"\begin{tabular}{lllr}")
        print(r"  \toprule")
        print(r"  arm & task family & configuration & turns \\")
        for title, rows in groups:
            print(r"  \midrule")
            print(rf"  \multicolumn{{4}}{{l}}{{\emph{{{title}}}}} \\")
            for row in rows:
                arm = row.arm.replace("_", r"\_")
                family = row.task_family.replace("_", r"\_")
                config = row.configuration.replace("_", r"\_")
                print(rf"  \code{{{arm}}} & {family} & {config} & {row.turns:,} \\")
        print(r"  \midrule")
        print(rf"  \textbf{{total}} & & & \textbf{{{total:,}}} \\")
        print(r"  \bottomrule")
        print(r"\end{tabular}")
        return 0

    for title, rows in groups:
        subtotal = sum(row.turns for row in rows)
        print(f"\n{title} ({subtotal:,} turns)")
        for row in rows:
            print(
                f"  {row.arm:34} {row.task_family:36} "
                f"{row.configuration:22} {row.turns:>7,}"
            )
    print(f"\nLEDGER TOTAL: {total:,} assistant turns")
    print("\nmonitor arms, reasoning turns over positive trajectories only")
    print("(negatives were never scored, so these are not a corpus row):")
    for arm, turns in _monitor_turns().items():
        print(f"  {arm:34} {turns:>7,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
