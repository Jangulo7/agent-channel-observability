"""The primary estimator: per-step reasoning emission rate, with a stated denominator.

The denominator is the contribution here. A per-step emission rate is meaningless
without saying which turns were counted, and the prior art does not say. See
`emission_rate` below.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from channels._vendored_stats import wilson_interval
from channels.schema import RateWithCI, ReasoningState, TurnObservation

# Below 30 turns a Wilson interval on a mid-range proportion is roughly +/-0.18 wide,
# which is the point past which a cell stops informing anything it is asked.
MIN_CELL_N = 30

# The four states partition every turn, so these two sets partition the denominator.
INSPECTABLE: frozenset[ReasoningState] = frozenset({ReasoningState.RAW_PRESENT})
UNINSPECTABLE: frozenset[ReasoningState] = frozenset(
    {ReasoningState.SUMMARY_ONLY, ReasoningState.REDACTED, ReasoningState.ABSENT}
)

DENOMINATOR_STATEMENT = "assistant turns that occurred at this step index"


@dataclass(frozen=True)
class EmissionCell:
    """Emission counts for one (model, task class, step index, effort) cell."""

    model: str
    task_class: str
    step_index: int
    reasoning_effort: str | None
    n_turns: int                         # assistant turns that actually occurred
    counts: dict[ReasoningState, int]    # sums to n_turns
    n_clusters: int | None = None        # distinct trajectories contributing


def emission_rate(cell: EmissionCell) -> float:
    """Share of turns in this cell whose raw reasoning is readable.

    Denominator is assistant turns that OCCURRED at this step index. Turns that
    did not occur — because the trajectory ended earlier — are absent from the
    cell entirely, not counted as ABSENT. This matters: counting non-existent
    turns as absent would make long-horizon trajectories look unmonitorable by
    construction.

    AdaptR1 (arXiv:2605.31062) reports per-step no-think ratios but does not
    define its denominator, and its reported averages do not reconcile with
    either an unweighted or an action-weighted mean over steps. We therefore
    define ours explicitly and do not compare rates numerically with theirs.
    """
    return cell.counts[ReasoningState.RAW_PRESENT] / cell.n_turns


def build_cells(observations: Iterable[TurnObservation]) -> list[EmissionCell]:
    """Group turn observations into emission cells and count their states.

    A cell exists only if at least one turn landed in it, which is how the
    denominator rule in `emission_rate` is enforced structurally rather than by
    convention: there is nowhere to record a turn that never happened.
    """
    grouped: dict[
        tuple[str, str, int, str | None], list[TurnObservation]
    ] = defaultdict(list)
    for observation in observations:
        key = (
            observation.model,
            observation.task_class,
            observation.step_index,
            observation.reasoning_effort,
        )
        grouped[key].append(observation)

    cells: list[EmissionCell] = []
    for (model, task_class, step_index, effort), group in sorted(grouped.items()):
        counts = dict.fromkeys(ReasoningState, 0)
        clusters: set[str] = set()
        for observation in group:
            counts[observation.state] += 1
            if observation.sample_id is not None:
                clusters.add(observation.sample_id)
        cells.append(
            EmissionCell(
                model=model,
                task_class=task_class,
                step_index=step_index,
                reasoning_effort=effort,
                n_turns=len(group),
                counts=counts,
                n_clusters=len(clusters) or None,
            )
        )
    return cells


def cell_rate(cell: EmissionCell) -> RateWithCI:
    """Emission rate for one cell, with its Wilson interval and its low-n flag."""
    successes = cell.counts[ReasoningState.RAW_PRESENT]
    interval = wilson_interval(successes, cell.n_turns)
    return RateWithCI(
        rate=emission_rate(cell),
        ci_low=interval.low,
        ci_high=interval.high,
        n=cell.n_turns,
        method=interval.method,
        weighting="within-cell",
        n_clusters=cell.n_clusters,
        low_n=cell.n_turns < MIN_CELL_N,
    )


def positional_profile(
    cells: Iterable[EmissionCell], model: str, task_class: str
) -> dict[int, RateWithCI]:
    """Return c(j): the emission rate at each step index, never collapsed to a mean.

    The decision-relevant quantity is coverage at the step where a harmful action
    occurs, so the profile is the object of interest and the mean is a summary of it.
    Callers that want the mean get it from `trajectory_rate`, which returns the
    profile alongside so the two cannot be separated by accident.
    """
    profile: dict[int, RateWithCI] = {}
    for cell in cells:
        if cell.model != model or cell.task_class != task_class:
            continue
        if cell.step_index in profile:
            profile[cell.step_index] = _merge(profile[cell.step_index], cell)
        else:
            profile[cell.step_index] = cell_rate(cell)
    return dict(sorted(profile.items()))


def trajectory_rate(
    cells: Iterable[EmissionCell], model: str, task_class: str
) -> tuple[RateWithCI, dict[int, RateWithCI]]:
    """Action-weighted emission across step indices, returned *with* its profile.

    Secondary to the profile. The weighting is action-weighted — every turn counts
    once, so long trajectories contribute more — and that is recorded in the returned
    `weighting` field rather than left to the reader to guess.
    """
    selected = [c for c in cells if c.model == model and c.task_class == task_class]
    profile = positional_profile(selected, model, task_class)
    successes = sum(c.counts[ReasoningState.RAW_PRESENT] for c in selected)
    n_turns = sum(c.n_turns for c in selected)
    if n_turns == 0:
        return (
            RateWithCI(None, None, None, 0, "none", "action-weighted",
                       status="no_denominator"),
            profile,
        )
    interval = wilson_interval(successes, n_turns)
    clusters = {c.n_clusters for c in selected if c.n_clusters is not None}
    return (
        RateWithCI(
            rate=successes / n_turns,
            ci_low=interval.low,
            ci_high=interval.high,
            n=n_turns,
            method=interval.method,
            weighting="action-weighted",
            n_clusters=max(clusters) if clusters else None,
            low_n=n_turns < MIN_CELL_N,
        ),
        profile,
    )


def uninspectable_share(cells: Iterable[EmissionCell]) -> RateWithCI:
    """Share of turns that are SUMMARY_ONLY, REDACTED or ABSENT.

    This is the number the `uninspectable_ceiling` gate reads. Uninspectable turns
    stay in the denominator and fail the gate; they are never dropped, because a
    measurement you could not make is a result about the measurement apparatus.
    """
    selected = list(cells)
    n_turns = sum(c.n_turns for c in selected)
    if n_turns == 0:
        return RateWithCI(None, None, None, 0, "none", status="no_denominator")
    successes = sum(
        sum(c.counts[state] for state in UNINSPECTABLE) for c in selected
    )
    interval = wilson_interval(successes, n_turns)
    return RateWithCI(
        rate=successes / n_turns,
        ci_low=interval.low,
        ci_high=interval.high,
        n=n_turns,
        method=interval.method,
        weighting="action-weighted",
        low_n=n_turns < MIN_CELL_N,
    )


def state_shares(cell: EmissionCell) -> Mapping[ReasoningState, float]:
    """The cell's four-state distribution as shares summing to one."""
    return {state: cell.counts[state] / cell.n_turns for state in ReasoningState}


def _merge(existing: RateWithCI, cell: EmissionCell) -> RateWithCI:
    """Pool a cell into an existing step-index rate, across reasoning_effort strata.

    Only used when the caller asked for a profile without fixing an effort level.
    Pooling across strata is recorded in `weighting` so the result cannot be mistaken
    for a within-stratum rate.
    """
    n_turns = existing.n + cell.n_turns
    successes = round((existing.rate or 0.0) * existing.n) + cell.counts[
        ReasoningState.RAW_PRESENT
    ]
    interval = wilson_interval(successes, n_turns)
    return RateWithCI(
        rate=successes / n_turns,
        ci_low=interval.low,
        ci_high=interval.high,
        n=n_turns,
        method=interval.method,
        weighting="pooled-across-effort",
        n_clusters=cell.n_clusters,
        low_n=n_turns < MIN_CELL_N,
    )


def binned_profile(
    cells: Iterable[EmissionCell], n_bins: int = 10
) -> dict[int, RateWithCI]:
    """Emission by *bin* of step index, for corpora too thin for a per-step profile.

    A per-step profile needs many trajectories: with one trajectory every step index
    has n_turns = 1 and every cell is low_n, so `positional_profile` returns 2000 cells
    that individually say nothing. Binning trades positional resolution for a usable
    denominator.

    The bins are equal-width over the observed step range, not equal-count, so bin k
    always means the same region of the trajectory across models.

    The returned intervals assume turns within a bin are independent. **They are not**
    when the bin is filled by a single trajectory. `n_clusters` on each returned rate
    carries the number of distinct trajectories, and `cluster.py` refuses to compute a
    clustered interval from one cluster rather than pretending it can.
    """
    selected = list(cells)
    if not selected:
        return {}
    max_step = max(cell.step_index for cell in selected)
    width = max(1, (max_step + 1 + n_bins - 1) // n_bins)

    grouped: dict[int, list[EmissionCell]] = defaultdict(list)
    for cell in selected:
        grouped[min(cell.step_index // width, n_bins - 1)].append(cell)

    profile: dict[int, RateWithCI] = {}
    for bin_index, members in sorted(grouped.items()):
        n_turns = sum(cell.n_turns for cell in members)
        successes = sum(cell.counts[ReasoningState.RAW_PRESENT] for cell in members)
        clusters = {c.n_clusters for c in members if c.n_clusters is not None}
        interval = wilson_interval(successes, n_turns)
        profile[bin_index] = RateWithCI(
            rate=successes / n_turns,
            ci_low=interval.low,
            ci_high=interval.high,
            n=n_turns,
            method=interval.method,
            weighting=f"binned-{width}-steps-per-bin",
            n_clusters=max(clusters) if clusters else None,
            low_n=n_turns < MIN_CELL_N,
        )
    return profile
