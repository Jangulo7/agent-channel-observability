"""Cross-task, cross-model positional coverage: the table the write-up needs.

One model on one task cannot distinguish a task effect from a model effect. This
prints c(j) for every (task family, model) pair that has been run, so the two
can be told apart — and prints the replication verdict rather than leaving a
reader to eyeball it.

    uv run python scripts/report_positional.py
"""

from __future__ import annotations

from pathlib import Path

from channels.emission import (
    MIN_CELL_N,
    build_cells,
    positional_profile,
    trajectory_rate,
)
from channels.loaders.inspect_logs import InspectLogLoader
from channels.schema import TurnObservation

#: Task families, in the order they were run. The label is what the write-up uses.
FAMILIES = {
    "agentharm": Path("data/inspect-runs-agentic"),
    "intercode_ctf": Path("data/inspect-runs-ctf"),
    "agent_bench_os": Path("data/inspect-runs-osbench"),
}

#: A profile counts as DECLINING only if some adequately-powered late cell sits
#: below the first step's interval. Eyeballing a downward wiggle is how a
#: single-arm artefact becomes a claim.
FLAT_TOLERANCE = 0.05


def _by_arm(root: Path) -> dict[str, list[TurnObservation]]:
    """Observations grouped by arm, or empty if the corpus is absent."""
    loader = InspectLogLoader(root, label_by_directory=True)
    if not loader.available():
        return {}
    grouped: dict[str, list[TurnObservation]] = {}
    for obs in loader.observations():
        grouped.setdefault(obs.model, []).append(obs)
    return grouped


def _verdict(profile: dict[int, object]) -> str:
    """Classify a profile's shape from adequately-powered cells only."""
    powered = {s: r for s, r in profile.items() if r.n >= MIN_CELL_N}  # type: ignore[attr-defined]
    if not powered:
        return "under-powered"
    first = powered[min(powered)]
    rates = [r.rate for r in powered.values() if r.rate is not None]  # type: ignore[attr-defined]
    if not rates:
        return "no data"
    if max(rates) - min(rates) <= FLAT_TOLERANCE:
        return f"FLAT at {rates[0]:.2f}"
    lowest = min(rates)
    # A decline only counts if the weakest powered cell falls below the first
    # step's lower confidence bound; otherwise it is within noise.
    if first.ci_low is not None and lowest < first.ci_low:  # type: ignore[attr-defined]
        return f"DECLINES {first.rate:.2f} -> {lowest:.2f}"  # type: ignore[attr-defined]
    return f"varies {max(rates):.2f}-{lowest:.2f}, within noise"


def verdict_table_markdown() -> str:
    """The replication verdict table, as markdown for RESULTS_SUMMARY."""
    present = {k: _by_arm(v) for k, v in FAMILIES.items()}
    present = {k: v for k, v in present.items() if v}
    arms = sorted({a for grouped in present.values() for a in grouped})
    lines = [
        "| model | families run | verdict | shape |",
        "|---|---|---|---|",
    ]
    for arm in arms:
        shapes = []
        for grouped in present.values():
            obs = grouped.get(arm)
            if not obs:
                continue
            cells = build_cells(obs)
            shapes.append(
                _verdict(positional_profile(cells, arm, cells[0].task_class))
            )
        if not shapes:
            continue
        kinds = {s.split()[0] for s in shapes}
        verdict = (
            "**consistent**" if len(kinds) == 1 and len(shapes) > 1
            else "differs by task" if len(shapes) > 1
            else "one family only"
        )
        lines.append(
            f"| `{arm}` | {len(shapes)} | {verdict} | {' · '.join(shapes)} |"
        )
    return "\n".join(lines)


def main() -> int:
    """Print the cross-family table and each cell's shape verdict."""
    present = {k: _by_arm(v) for k, v in FAMILIES.items()}
    present = {k: v for k, v in present.items() if v}
    if not present:
        print("no agentic corpora available")
        return 2

    arms = sorted({a for grouped in present.values() for a in grouped})
    print(f"Positional coverage c(j), adequately-powered cells only "
          f"(n >= {MIN_CELL_N})\n")
    for family, grouped in present.items():
        print(f"### {family}")
        print(f"{'arm':22s} {'c':>7s} {'turns':>6s}  shape")
        for arm in arms:
            obs = grouped.get(arm)
            if not obs:
                print(f"{arm:22s} {'-':>7s} {'-':>6s}  not run")
                continue
            cells = build_cells(obs)
            rate, _ = trajectory_rate(cells, arm, cells[0].task_class)
            profile = positional_profile(cells, arm, cells[0].task_class)
            print(f"{arm:22s} {rate.rate:7.3f} {rate.n:6d}  {_verdict(profile)}")
        print()

    print("Replication check — does an arm's shape hold across task families?\n")
    for arm in arms:
        shapes = []
        for family, grouped in present.items():
            obs = grouped.get(arm)
            if not obs:
                continue
            cells = build_cells(obs)
            profile = positional_profile(cells, arm, cells[0].task_class)
            shapes.append(f"{family}={_verdict(profile)}")
        if len(shapes) >= 2:
            kinds = {s.split("=")[1].split()[0] for s in shapes}
            mark = "CONSISTENT" if len(kinds) == 1 else "DIFFERS BY TASK"
            print(f"  {arm:22s} {mark}")
            for s in shapes:
                print(f"      {s}")
    return 0


def _update_results_block() -> None:
    """Write the verdict table into RESULTS_SUMMARY's generated block."""
    import re

    summary = Path("RESULTS_SUMMARY.md")
    text = summary.read_text(encoding="utf-8")
    marker = "positional-verdicts"
    pattern = re.compile(
        rf"(<!-- BEGIN:{marker} -->\n).*?(\n<!-- END:{marker} -->)", re.DOTALL
    )
    if not pattern.search(text):
        print("no positional-verdicts markers in RESULTS_SUMMARY.md")
        return
    summary.write_text(
        pattern.sub(lambda m: m.group(1) + verdict_table_markdown() + m.group(2), text),
        encoding="utf-8",
    )
    print("updated RESULTS_SUMMARY positional-verdicts block")


if __name__ == "__main__":
    import sys as _sys

    if "--update-results" in _sys.argv:
        _update_results_block()
        raise SystemExit(0)
    raise SystemExit(main())
