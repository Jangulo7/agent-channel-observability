"""Regenerate the generated blocks of RESULTS_SUMMARY.md from the live corpora.

Six more sweep arms are still landing, and a table retyped by hand once per arm
is a table that will eventually disagree with the record beside it. Everything
between a BEGIN/END marker pair is replaced from measurement; everything outside
is prose and is never touched.

    uv run python scripts/update_results.py
"""

from __future__ import annotations

import re
from pathlib import Path

from channels.emission import MIN_CELL_N, build_cells, cell_rate, state_shares
from channels.loaders.inspect_logs import InspectLogLoader
from channels.schema import ReasoningState, TurnObservation

SUMMARY = Path(".research-plan/RESULTS_SUMMARY_full.md")  # full internal summary
REASONING_LOGS = Path("data/inspect-runs-reasoning")

#: Arms the sweep intends to produce, in run order. Naming them lets the report
#: say which are PENDING rather than quietly describing a partial sweep as whole.
PLANNED_ARMS = (
    "gpt-oss-120b",
    "qwen3-32b",
    "glm-4.7-flash",
    "claude-haiku-4.5",
    "deepseek-v3.2",
    "deepseek-v3.2-reasoning-on",
    "gpt-5-nano-low",
    "gpt-5-nano-medium",
    "gpt-5-nano-high",
)
TASKS_PER_ARM = 4


def _observations_by_arm(loader: InspectLogLoader) -> dict[str, list[TurnObservation]]:
    """Group turn observations by arm directory."""
    grouped: dict[str, list[TurnObservation]] = {}
    for path in loader.log_paths():
        arm = path.parent.name
        grouped.setdefault(arm, []).extend(loader._observations_for_log(path))
    return grouped


def _logs_per_arm(loader: InspectLogLoader) -> dict[str, int]:
    """Count complete logs per arm, to tell a finished arm from a partial one."""
    counts: dict[str, int] = {}
    for path in loader.log_paths():
        counts[path.parent.name] = counts.get(path.parent.name, 0) + 1
    return counts


def _arm_rows(loader: InspectLogLoader) -> str:
    """The per-arm emission table, complete arms only."""
    grouped = _observations_by_arm(loader)
    counts = _logs_per_arm(loader)
    lines = [
        "| arm | n turns | raw_present | 95% CI | summary_only | redacted | absent |",
        "|---|---|---|---|---|---|---|",
    ]
    for arm in PLANNED_ARMS:
        if counts.get(arm, 0) < TASKS_PER_ARM:
            continue
        cells = build_cells(grouped[arm])
        n_turns = sum(c.n_turns for c in cells)
        totals = {s: sum(c.counts[s] for c in cells) for s in ReasoningState}
        merged = type(cells[0])(
            model=arm, task_class="all", step_index=-1, reasoning_effort=None,
            n_turns=n_turns, counts=totals,
        )
        rate = cell_rate(merged)
        shares = state_shares(merged)
        lines.append(
            f"| `{arm}` | {n_turns:,} | **{rate.rate:.4f}** | "
            f"[{rate.ci_low:.4f}, {rate.ci_high:.4f}] | "
            f"{shares[ReasoningState.SUMMARY_ONLY]:.4f} | "
            f"{shares[ReasoningState.REDACTED]:.4f} | "
            f"{shares[ReasoningState.ABSENT]:.4f} |"
        )
    return "\n".join(lines)


def _status_line(loader: InspectLogLoader) -> str:
    """A sentence naming what is measured and what is still pending."""
    counts = _logs_per_arm(loader)
    complete = [a for a in PLANNED_ARMS if counts.get(a, 0) >= TASKS_PER_ARM]
    partial = [
        a for a in PLANNED_ARMS if 0 < counts.get(a, 0) < TASKS_PER_ARM
    ]
    pending = [a for a in PLANNED_ARMS if counts.get(a, 0) == 0]
    grouped = _observations_by_arm(loader)
    turns = sum(
        len(grouped[a]) for a in complete
    )
    parts = [
        f"**{len(complete)} of {len(PLANNED_ARMS)} arms complete**, "
        f"{turns:,} assistant turns measured. `MIN_CELL_N={MIN_CELL_N}`; no cell "
        f"is low-n. {loader.errored_samples()} sample(s) errored; "
        f"{len(loader.incomplete_logs())} incomplete log(s) excluded and counted."
    ]
    if partial:
        named = ", ".join(f"`{a}`" for a in partial)
        parts.append(f"Partially run, excluded from the table: {named}.")
    if pending:
        parts.append(f"Not yet run: {', '.join(f'`{a}`' for a in pending)}.")
    return " ".join(parts)


def _replace_block(text: str, marker: str, content: str) -> str:
    """Swap the body between a BEGIN/END marker pair, leaving prose untouched."""
    pattern = re.compile(
        rf"(<!-- BEGIN:{marker} -->\n).*?(\n<!-- END:{marker} -->)", re.DOTALL
    )
    if not pattern.search(text):
        raise ValueError(f"marker pair {marker!r} not found in {SUMMARY}")
    return pattern.sub(lambda m: m.group(1) + content + m.group(2), text)


def main() -> int:
    """Refresh every generated block and report what changed."""
    loader = InspectLogLoader(REASONING_LOGS, label_by_directory=True)
    if not loader.available():
        print(f"no complete logs under {REASONING_LOGS}; nothing to update")
        return 2
    text = SUMMARY.read_text(encoding="utf-8")
    text = _replace_block(text, "reasoning-status", _status_line(loader))
    text = _replace_block(text, "reasoning-arms", _arm_rows(loader))
    SUMMARY.write_text(text, encoding="utf-8")
    print(_status_line(loader))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
