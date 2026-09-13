"""The primary estimator: per-step reasoning emission rate, with a stated denominator.

The denominator is the contribution here. A per-step emission rate is meaningless
without saying which turns were counted, and the prior art does not say. See
`emission_rate` below.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace

from channels._vendored_stats import wilson_interval
from channels.cluster import clustered_wilson
from channels.errors import MissingActorError
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
    # Turns per trajectory id. Carried so that pooling cells can count DISTINCT
    # trajectories and weight clustered intervals, which a bare n_clusters cannot:
    # two cells with 10 trajectories each may share all ten or none of them.
    cluster_sizes: Mapping[str, int] = field(default_factory=dict)


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
        sizes: dict[str, int] = defaultdict(int)
        for observation in group:
            counts[observation.state] += 1
            if observation.sample_id is not None:
                sizes[observation.sample_id] += 1
        cells.append(
            EmissionCell(
                model=model,
                task_class=task_class,
                step_index=step_index,
                reasoning_effort=effort,
                n_turns=len(group),
                counts=counts,
                n_clusters=len(sizes) or None,
                cluster_sizes=dict(sizes),
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
    by_step: dict[int, list[EmissionCell]] = defaultdict(list)
    for cell in cells:
        if cell.model == model and cell.task_class == task_class:
            by_step[cell.step_index].append(cell)
    return {
        step: cell_rate(group[0]) if len(group) == 1 else _merge(group)
        for step, group in sorted(by_step.items())
    }


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
    return (
        RateWithCI(
            rate=successes / n_turns,
            ci_low=interval.low,
            ci_high=interval.high,
            n=n_turns,
            method=interval.method,
            weighting="action-weighted",
            n_clusters=distinct_trajectories(selected),
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


def _merge(group: Sequence[EmissionCell]) -> RateWithCI:
    """Pool one step index's cells across reasoning_effort strata into one rate.

    Only used when the caller asked for a profile without fixing an effort level.
    Pooling across strata is recorded in `weighting` so the result cannot be mistaken
    for a within-stratum rate. Counts are summed directly rather than recovered from
    rounded rates, and n_clusters counts distinct trajectories, not the last stratum's.
    """
    n_turns = sum(cell.n_turns for cell in group)
    successes = sum(cell.counts[ReasoningState.RAW_PRESENT] for cell in group)
    interval = wilson_interval(successes, n_turns)
    return RateWithCI(
        rate=successes / n_turns,
        ci_low=interval.low,
        ci_high=interval.high,
        n=n_turns,
        method=interval.method,
        weighting="pooled-across-effort",
        n_clusters=distinct_trajectories(group),
        low_n=n_turns < MIN_CELL_N,
    )


def distinct_trajectories(cells: Iterable[EmissionCell]) -> int | None:
    """Return the number of distinct trajectories across cells, or None if unknowable.

    None when any cell lacks trajectory ids: a maximum or a sum of per-cell counts
    would be a guess (the same trajectory appears at every step it reached), and a
    guessed cluster count is worse than a stated unknown.
    """
    merged = merged_cluster_sizes(cells)
    return len(merged) if merged is not None else None


def merged_cluster_sizes(
    cells: Iterable[EmissionCell], qualify: bool = False
) -> dict[str, int] | None:
    """Return turns per trajectory id pooled over cells, or None if any cell lacks ids.

    `qualify=True` prefixes each id with its task class and effort, for pools that
    span task classes: Inspect sample ids restart per task, so id "1" of two tasks is
    two trajectories, and merging them would invent a dependence that is not there.
    """
    merged: dict[str, int] = {}
    for cell in cells:
        if not cell.cluster_sizes:
            return None
        prefix = f"{cell.task_class}|{cell.reasoning_effort}|" if qualify else ""
        for name, size in cell.cluster_sizes.items():
            merged[prefix + name] = merged.get(prefix + name, 0) + size
    return merged


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
    width, grouped = _bin_groups(list(cells), n_bins)
    profile: dict[int, RateWithCI] = {}
    for bin_index, members in grouped.items():
        n_turns = sum(cell.n_turns for cell in members)
        successes = sum(cell.counts[ReasoningState.RAW_PRESENT] for cell in members)
        interval = wilson_interval(successes, n_turns)
        profile[bin_index] = RateWithCI(
            rate=successes / n_turns,
            ci_low=interval.low,
            ci_high=interval.high,
            n=n_turns,
            method=interval.method,
            weighting=f"binned-{width}-steps-per-bin",
            n_clusters=distinct_trajectories(members),
            low_n=n_turns < MIN_CELL_N,
        )
    return profile


def _bin_groups(
    cells: Sequence[EmissionCell], n_bins: int
) -> tuple[int, dict[int, list[EmissionCell]]]:
    """Return the bin width and cells grouped by equal-width bin of step index."""
    if not cells:
        return 1, {}
    max_step = max(cell.step_index for cell in cells)
    width = max(1, (max_step + 1 + n_bins - 1) // n_bins)
    grouped: dict[int, list[EmissionCell]] = defaultdict(list)
    for cell in cells:
        grouped[min(cell.step_index // width, n_bins - 1)].append(cell)
    return width, dict(sorted(grouped.items()))


@dataclass(frozen=True)
class ArmProfile:
    """The positional profile of one arm: one model x task class x reasoning effort.

    The record and Figure 2 are both drawn from this one object, so the published
    numbers and the plotted ones cannot drift apart.
    """

    model: str
    task_class: str
    reasoning_effort: str | None
    unit: str                        # "step" (step_index keys) or "bin" (bin keys)
    bin_width: int | None            # steps per bin when unit == "bin", else None
    n_trajectories: int
    points: dict[int, RateWithCI]    # key is a step index or a bin index, per `unit`
    raw_present: RateWithCI          # action-weighted over all the arm's turns

    def powered(self) -> dict[int, RateWithCI]:
        """Return the points whose denominator is at least MIN_CELL_N."""
        return {key: rate for key, rate in self.points.items() if not rate.low_n}


def arm_profiles(
    cells: Iterable[EmissionCell], n_bins: int = 10
) -> list[ArmProfile]:
    """Return one profile per arm, per step where possible and per bin where not.

    Arms are never pooled: a profile averaged across a raw-emitting arm and a
    withholding one describes neither. With two or more trajectories each step index
    holds at most one turn per trajectory, so a per-step Wilson interval is honest and
    the true step keys are kept. With a single trajectory every step has one turn, so
    steps are binned — and the bins get no interval, because one trajectory is one
    cluster and no clustered interval exists.
    """
    grouped: dict[tuple[str, str, str | None], list[EmissionCell]] = defaultdict(list)
    for cell in cells:
        grouped[(cell.model, cell.task_class, cell.reasoning_effort)].append(cell)
    ordered = sorted(grouped.items(), key=lambda item: (item[0][:2], str(item[0][2])))
    return [_arm_profile(key, members, n_bins) for key, members in ordered]


def _arm_profile(
    key: tuple[str, str, str | None], members: list[EmissionCell], n_bins: int
) -> ArmProfile:
    """Return the profile of one arm's cells; see `arm_profiles` for the rule."""
    sizes = _require_cluster_sizes(members, key)
    if len(sizes) >= 2:
        unit, width = "step", None
        points = {cell.step_index: _step_rate(cell) for cell in members}
    else:
        unit, (width, bins) = "bin", _bin_groups(members, n_bins)
        points = {index: _pooled_rate(group) for index, group in bins.items()}
    return ArmProfile(
        model=key[0], task_class=key[1], reasoning_effort=key[2],
        unit=unit, bin_width=width, n_trajectories=len(sizes),
        points=dict(sorted(points.items())), raw_present=_pooled_rate(members),
    )


def pooled_raw_present(cells: Sequence[EmissionCell]) -> RateWithCI:
    """Return the raw_present share over cells, with a trajectory-clustered interval.

    Pooled over steps, turns of one trajectory are not independent, so a naive Wilson
    interval would claim precision the data lack. A single-trajectory pool gets no
    interval at all (status `single_cluster_no_interval`).
    """
    if not cells:
        return RateWithCI(None, None, None, 0, "none", status="no_denominator")
    return _pooled_rate(cells, qualify=True)


def _pooled_rate(cells: Sequence[EmissionCell], qualify: bool = False) -> RateWithCI:
    """Return the clustered raw_present rate over cells, flagged low-n where thin."""
    sizes = merged_cluster_sizes(cells, qualify=qualify)
    if sizes is None:
        raise MissingActorError(
            f"{len(cells)} cell(s) of {cells[0].model}/{cells[0].task_class} carry no "
            "trajectory ids, so a clustered interval cannot be computed; expected "
            "every observation to carry a sample_id"
        )
    successes = sum(cell.counts[ReasoningState.RAW_PRESENT] for cell in cells)
    labels = [name for name, size in sorted(sizes.items()) for _ in range(size)]
    n_turns = sum(cell.n_turns for cell in cells)
    rate = clustered_wilson(successes, n_turns, labels)
    return replace(rate, weighting="action-weighted", low_n=n_turns < MIN_CELL_N)


def _step_rate(cell: EmissionCell) -> RateWithCI:
    """Return one step's rate: plain Wilson when each trajectory gave one turn."""
    if all(size == 1 for size in cell.cluster_sizes.values()):
        return cell_rate(cell)
    # Duplicate trajectory ids at one step mean ids are not unique per trajectory;
    # cluster on them rather than pretend the turns are independent.
    return _pooled_rate([cell])


def _require_cluster_sizes(
    members: Sequence[EmissionCell], key: tuple[str, str, str | None]
) -> dict[str, int]:
    """Return the arm's turns per trajectory, raising when ids are missing."""
    sizes = merged_cluster_sizes(members)
    if not sizes:
        raise MissingActorError(
            f"arm {key} has cells without trajectory ids; the unit of a profile "
            "(step or bin) depends on the trajectory count, which is unknowable here"
        )
    return sizes
