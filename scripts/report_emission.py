"""Print the emission tables for a log directory, in Markdown.

Used to keep RESULTS_SUMMARY.md and BUILD_LOG.md honest: every figure in those
documents is pasted from this script's output rather than typed by hand, so a
number cannot drift from the corpus it claims to describe.

    uv run python scripts/report_emission.py --logs data/inspect-runs-reasoning
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from channels._vendored_stats import wilson_upper_bound
from channels.emission import (
    MIN_CELL_N,
    build_cells,
    cell_rate,
    state_shares,
    uninspectable_share,
)
from channels.loaders.inspect_logs import InspectLogLoader
from channels.schema import ReasoningState, TurnObservation

STATE_ORDER = (
    ReasoningState.RAW_PRESENT,
    ReasoningState.SUMMARY_ONLY,
    ReasoningState.REDACTED,
    ReasoningState.ABSENT,
)


def _arm_of(path_parts: tuple[str, ...]) -> str:
    """The arm directory name, which is how the runner labels a configuration."""
    return path_parts[-2] if len(path_parts) >= 2 else "unknown"


def _by_arm(loader: InspectLogLoader) -> dict[str, list[TurnObservation]]:
    """Group observations by arm directory, not by model.

    Three gpt-5-nano arms share one model id and differ only by reasoning_effort;
    grouping on the model would silently pool them and destroy the one axis this
    run exists to measure.
    """
    grouped: dict[str, list[TurnObservation]] = defaultdict(list)
    for path in loader.log_paths():
        arm = _arm_of(path.parts)
        for observation in loader._observations_for_log(path):
            grouped[arm].append(observation)
    return grouped


def _print_arm_table(grouped: dict[str, list[TurnObservation]]) -> None:
    """One row per arm: the four state shares over all its task classes."""
    print("| arm | n turns | raw_present | 95% CI | summary_only | redacted | absent |")
    print("|---|---|---|---|---|---|---|")
    for arm in sorted(grouped):
        cells = build_cells(grouped[arm])
        n_turns = sum(cell.n_turns for cell in cells)
        counts = {state: sum(c.counts[state] for c in cells) for state in STATE_ORDER}
        raw = counts[ReasoningState.RAW_PRESENT]
        merged = build_cells(grouped[arm])
        pooled = cell_rate(
            type(merged[0])(
                model=arm, task_class="all", step_index=-1, reasoning_effort=None,
                n_turns=n_turns, counts=counts,
            )
        )
        interval = (
            f"[{pooled.ci_low:.4f}, {pooled.ci_high:.4f}]"
            if pooled.ci_low is not None
            else "n/a"
        )
        shares = {s: counts[s] / n_turns for s in STATE_ORDER}
        print(
            f"| `{arm}` | {n_turns:,} | **{raw / n_turns:.4f}** | {interval} | "
            f"{shares[ReasoningState.SUMMARY_ONLY]:.4f} | "
            f"{shares[ReasoningState.REDACTED]:.4f} | "
            f"{shares[ReasoningState.ABSENT]:.4f} |"
        )


def _print_cell_table(grouped: dict[str, list[TurnObservation]]) -> None:
    """The appendix table: arm x task class x step index."""
    print("\n| arm | task class | step | n | raw_present | 95% CI | low n |")
    print("|---|---|---|---|---|---|---|")
    for arm in sorted(grouped):
        for cell in build_cells(grouped[arm]):
            rate = cell_rate(cell)
            interval = (
                f"[{rate.ci_low:.4f}, {rate.ci_high:.4f}]"
                if rate.ci_low is not None
                else "n/a"
            )
            shares = state_shares(cell)
            print(
                f"| `{arm}` | {cell.task_class} | {cell.step_index} | {cell.n_turns} "
                f"| {shares[ReasoningState.RAW_PRESENT]:.4f} | {interval} "
                f"| {'YES' if rate.low_n else 'no'} |"
            )


def main() -> int:
    """Print every table needed to update the two reports."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--logs", type=Path, default=Path("data/inspect-runs-reasoning")
    )
    args = parser.parse_args()

    loader = InspectLogLoader(args.logs)
    if not loader.available():
        print(f"no complete logs under {args.logs}")
        return 2

    incomplete = loader.incomplete_logs()
    grouped = _by_arm(loader)
    total = sum(len(v) for v in grouped.values())

    print(f"### Emission by arm — {args.logs}\n")
    print(
        f"{len(loader.log_paths())} complete log(s), {len(incomplete)} incomplete "
        f"and EXCLUDED, {len(grouped)} arm(s), {total:,} assistant turns. "
        f"MIN_CELL_N={MIN_CELL_N}.\n"
    )
    _print_arm_table(grouped)

    all_cells = build_cells([o for obs in grouped.values() for o in obs])
    share = uninspectable_share(all_cells)
    raw_total = sum(
        c.counts[ReasoningState.RAW_PRESENT] for c in all_cells
    )
    print(f"\nPooled uninspectable share: {share.rate:.4f} (n={share.n:,})")
    if raw_total == 0:
        print(
            f"Zero raw_present observed; 95% one-sided upper bound "
            f"{wilson_upper_bound(0, share.n):.5f}"
        )
    _print_cell_table(grouped)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
