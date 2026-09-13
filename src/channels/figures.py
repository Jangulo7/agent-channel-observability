"""The two named figures. Matplotlib only, no seaborn.

Captions are generated with the figure and are readable standalone, because a figure
that needs the surrounding paragraph to state its n is one that will be
screenshotted without it.

Colour choices are not taste. The four reasoning states are an *ordered* scale from
"fully readable" to "nothing", so Figure 1 uses a single-hue ordinal ramp rather than
four categorical hues; the ramp below passes the lightness-monotonicity, adjacent-step
and light-end-contrast checks. Figure 2's three series are genuine categories and use
the first three categorical slots, which pass all-pairs CVD separation.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import matplotlib

# Agg so the figures render identically in CI, where there is no display.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from channels.emission import (
    MIN_CELL_N,
    ArmProfile,
    EmissionCell,
    pooled_raw_present,
)
from channels.priors import (
    ADAPTR1_STEP_PROFILE,
    ADAPTTHINK_TASK_SPREAD,
)
from channels.schema import RateWithCI, ReasoningState

# Ordinal blue ramp, darkest = most information readable. Validated: monotone
# lightness, every adjacent gap >= 0.06, light end 2.06:1 against the surface.
STATE_COLOURS: dict[ReasoningState, str] = {
    ReasoningState.RAW_PRESENT: "#0d366b",
    ReasoningState.SUMMARY_ONLY: "#1c5cab",
    # REDACTED and ABSENT are the pair a reader must never confuse - "withheld"
    # versus "never produced" is the distinction the four-state scheme exists
    # for - so they are separated by hue as well as lightness rather than being
    # two steps of one blue ramp.
    ReasoningState.REDACTED: "#b4522b",
    ReasoningState.ABSENT: "#c9c6c0",
}

# Categorical slots 1-3. Validated all-pairs: worst CVD dE 9.2, normal-vision 24.0.
SERIES_MEASURED = "#2a78d6"
SERIES_CEILING = "#eb6834"
SERIES_INDUCED = "#1baf7a"
# Low-n positions are drawn hollow and grey: present, so nothing is hidden, but
# visibly not carrying the same weight as a position with a usable denominator.
LOW_N_MARKER = "#9a988f"

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"

# The two darkest ramp steps need light text on them; the two lightest need dark.
_DARK_SEGMENTS = frozenset(
    {ReasoningState.RAW_PRESENT, ReasoningState.SUMMARY_ONLY, ReasoningState.REDACTED}
)

STATE_LABELS: dict[ReasoningState, str] = {
    ReasoningState.RAW_PRESENT: "raw present",
    ReasoningState.SUMMARY_ONLY: "summary only",
    ReasoningState.REDACTED: "redacted",
    ReasoningState.ABSENT: "absent",
}


def figure_one(
    cells: Sequence[EmissionCell], out_path: Path, by_task: bool = True
) -> tuple[Path, str]:
    """Stacked four-state distribution by model (and task class), with clustered bars.

    Low-n cells are excluded from the plot and named in the caption, per the
    small-cell rule. Returns the path written and the caption text.

    `by_task=False` collapses task classes into one bar per model. Use it only
    when the within-model spread across task classes has been checked and is
    small: collapsing an axis that carries variation hides the variation, which
    is the reporting-unit failure this package exists to name.
    `task_class_spread` computes that check.
    """
    grouped = (
        _group_by_model_task(cells) if by_task else _group_by_model(cells)
    )
    grouped = _ordered_for_story(grouped)
    plotted = {
        key: group for key, group in grouped.items() if _n_of(group) >= MIN_CELL_N
    }
    excluded = sorted(set(grouped) - set(plotted))

    figure, axes = plt.subplots(figsize=(max(5.0, 1.9 * len(plotted) + 2.6), 4.6))
    figure.patch.set_facecolor(SURFACE)
    axes.set_facecolor(SURFACE)

    labels = [_bar_label(key) for key in plotted]
    bottoms = [0.0] * len(plotted)
    for state in ReasoningState:
        heights = [_share_of(group, state) for group in plotted.values()]
        axes.bar(
            labels,
            heights,
            bottom=bottoms,
            color=STATE_COLOURS[state],
            label=STATE_LABELS[state],
            width=0.58,
            # A 2px surface gap between stacked segments keeps the boundary legible.
            edgecolor=SURFACE,
            linewidth=2.0,
        )
        bottoms = [b + h for b, h in zip(bottoms, heights, strict=True)]

    _label_segments(axes, list(plotted.values()))
    _overlay_raw_present_intervals(axes, list(plotted.values()))
    _style_axes(axes, ylabel="share of assistant turns")
    axes.set_ylim(0.0, 1.0)
    # Without this a single bar expands to the full axis and reads as a block of
    # colour rather than as a bar.
    axes.set_xlim(-0.75, len(plotted) - 0.25)
    axes.legend(
        frameon=False, fontsize=8, labelcolor=TEXT_SECONDARY,
        loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=4,
    )
    axes.set_title(
        "Reasoning channel states per assistant turn",
        color=TEXT_PRIMARY, fontsize=11, loc="left", pad=10,
    )
    figure.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out_path, dpi=200, facecolor=SURFACE)
    plt.close(figure)
    return out_path, _caption_one(plotted, excluded)


def figure_two(
    arm: ArmProfile,
    out_path: Path,
    stage2_recall: float = 1.0,
    panel_title: str = "Measured",
) -> tuple[Path, str]:
    """Return the path and caption of one arm's c(j) and ceiling, beside prior art.

    Takes the same `ArmProfile` the record is written from, so the plotted and the
    published numbers are one object. Multi-trajectory arms are drawn per step, with
    low-n steps hollow and grey; a single-trajectory arm is drawn per bin.

    Two panels sharing one y-axis rather than one panel with two x-meanings: our
    position 2 and AdaptR1's step 2 are not the same thing. A second y-scale is never
    used, because it would let the curves be slid against each other.
    """
    figure, (left, right) = _two_panels()
    _plot_measured(left, arm)
    steps = sorted(arm.points)
    measured = [arm.points[step].rate or 0.0 for step in steps]
    _plot_ceiling(left, steps, measured, stage2_recall)
    _style_axes(left, ylabel="probability", xlabel=_position_label(arm))
    left.set_ylim(0.0, 1.05)
    left.xaxis.set_major_locator(MaxNLocator(integer=True))
    # Legends sit below the axes: inside, they covered the low-n points they label.
    left.legend(frameon=False, fontsize=8, labelcolor=TEXT_SECONDARY, ncol=2,
                loc="upper center", bbox_to_anchor=(0.5, -0.16))
    left.set_title(panel_title, color=TEXT_PRIMARY, fontsize=9, loc="left", pad=8)

    _plot_adaptr1_reference(right)
    figure.suptitle(
        "Positional coverage and the recall ceiling it imposes",
        color=TEXT_PRIMARY, fontsize=11.5, x=0.008, ha="left", y=0.985,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.94))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(out_path, dpi=200, facecolor=SURFACE)
    plt.close(figure)
    return out_path, _caption_two(arm, stage2_recall)


def _two_panels() -> tuple[Any, tuple[Any, Any]]:
    """Return a figure with a wide measured panel and a narrow prior-art panel."""
    figure, (left, right) = plt.subplots(
        1, 2, figsize=(10.4, 5.0), sharey=True,
        gridspec_kw={"width_ratios": [2.0, 1.0]},
    )
    figure.patch.set_facecolor(SURFACE)
    for axes in (left, right):
        axes.set_facecolor(SURFACE)
    return figure, (left, right)


def _position_label(arm: ArmProfile) -> str:
    """The x-axis label, which says whether positions are steps or bins."""
    if arm.unit == "bin":
        return f"trajectory position (equal-width bins of {arm.bin_width} steps)"
    return "step index (0-based assistant turn)"


def _plot_measured(axes: Any, arm: ArmProfile) -> None:
    """Draw c(j): filled where powered, hollow grey where low-n, with any intervals."""
    steps = sorted(arm.points)
    rates = [arm.points[step].rate or 0.0 for step in steps]
    axes.plot(steps, rates, color=SERIES_MEASURED, linewidth=1.2, alpha=0.5)
    for low_n, label in ((False, f"measured c(j), n ≥ {MIN_CELL_N}"),
                         (True, f"low-n position, n < {MIN_CELL_N}")):
        chosen = [step for step in steps if arm.points[step].low_n is low_n]
        if not chosen:
            continue
        axes.plot(
            chosen, [arm.points[step].rate or 0.0 for step in chosen],
            linestyle="none", marker="o", markersize=5, label=label,
            markerfacecolor="none" if low_n else SERIES_MEASURED,
            markeredgecolor=LOW_N_MARKER if low_n else SERIES_MEASURED,
        )
    _plot_interval_bars(axes, arm.points)


def _plot_ceiling(
    axes: Any, steps: Sequence[int], measured: Sequence[float], stage2_recall: float
) -> None:
    """Draw c(j)*r2, or say why it is not drawn when it coincides with c(j).

    At r2 = 1 the ceiling *is* the coverage. Drawing a second identical line would
    imply two findings where there is one, so the identity is annotated instead.
    """
    if stage2_recall >= 1.0:
        axes.annotate(
            "r₂ = 1, so the ceiling c(j)·r₂ coincides exactly with c(j):\n"
            "no second stage, however good, recovers the gap above this line.",
            xy=(0.02, 0.90), xycoords="axes fraction",
            color=TEXT_SECONDARY, fontsize=8, va="top",
        )
        return
    axes.plot(
        list(steps), [value * stage2_recall for value in measured],
        color=SERIES_CEILING, linewidth=2.0, linestyle="--", marker="s", markersize=5,
        label=f"recall ceiling c(j)·r₂, r₂={stage2_recall:g}",
    )


def adaptr1_thinking_share() -> dict[int, float]:
    """Return AdaptR1's published per-step no-think ratio transformed to 1 - ratio.

    The published value is a NO-think share; c(j) is a share of turns WITH readable
    reasoning. Plotted untransformed beside c(j), a high point would read as high
    coverage when it means the opposite. The transform lives here, not in priors.py,
    because priors.py holds transcribed values only.
    """
    return {step: 1.0 - ratio for step, ratio in ADAPTR1_STEP_PROFILE.items()}


def _plot_adaptr1_reference(axes: Any) -> None:
    """Plot AdaptR1's induced step profile as a thinking share, labelled as induced."""
    share = adaptr1_thinking_share()
    steps = sorted(share)
    axes.plot(
        steps, [share[step] for step in steps], color=SERIES_INDUCED, linewidth=1.8,
        linestyle=":", marker="^", markersize=6,
        label="AdaptR1: 1 - published no-think ratio\n"
              "(induced by RL objective, not observed)",
    )
    axes.set_xticks(steps)
    axes.legend(frameon=False, fontsize=8, labelcolor=TEXT_SECONDARY,
                loc="upper center", bbox_to_anchor=(0.5, -0.16))
    _style_axes(axes, ylabel="", xlabel="step index (AdaptR1)")
    axes.set_title(
        "Prior art: INDUCED, not observed",
        color=TEXT_PRIMARY, fontsize=10, loc="left", pad=8,
    )


def _plot_interval_bars(axes: Any, profile: Mapping[int, RateWithCI]) -> None:
    """Draw each position's interval, only where one exists and in its point's style.

    Bars rather than a shaded band, because a band interpolates across positions
    that have no interval (a single trajectory) and across low-n gaps.
    """
    for step, rate in profile.items():
        if rate.rate is None or rate.ci_low is None or rate.ci_high is None:
            continue
        axes.errorbar(
            step, rate.rate,
            yerr=[[rate.rate - rate.ci_low], [rate.ci_high - rate.rate]],
            fmt="none", elinewidth=1.0, capsize=2,
            ecolor=LOW_N_MARKER if rate.low_n else SERIES_MEASURED,
        )


def _label_segments(axes: Any, groups: Sequence[Sequence[EmissionCell]]) -> None:
    """Direct-label each visible segment, so identity is never carried by colour alone.

    Segments below 6% of the bar are left unlabelled: the text would not fit and a
    collision is worse than a legend lookup.
    """
    for position, group in enumerate(groups):
        bottom = 0.0
        for state in ReasoningState:
            share = _share_of(group, state)
            if share >= 0.06:
                axes.text(
                    position, bottom + share / 2, f"{share:.3f}",
                    ha="center", va="center", fontsize=9,
                    color=SURFACE if state in _DARK_SEGMENTS else TEXT_PRIMARY,
                )
            bottom += share


def _overlay_raw_present_intervals(
    axes: Any, groups: Sequence[Sequence[EmissionCell]]
) -> None:
    """Draw a trajectory-clustered interval on each bar's raw_present share."""
    for position, group in enumerate(groups):
        rate = pooled_raw_present(group)
        if rate.rate is None or rate.ci_low is None or rate.ci_high is None:
            continue
        axes.errorbar(
            position, rate.rate,
            yerr=[[rate.rate - rate.ci_low], [rate.ci_high - rate.rate]],
            fmt="none", ecolor=TEXT_PRIMARY, elinewidth=1.4, capsize=4, zorder=5,
        )


def _style_axes(axes: Any, ylabel: str, xlabel: str = "") -> None:
    """Recessive grid and axes; the data should be the darkest thing on the page."""
    axes.spines["top"].set_visible(False)
    axes.spines["right"].set_visible(False)
    axes.spines["left"].set_color("#d8d7d2")
    axes.spines["bottom"].set_color("#d8d7d2")
    axes.tick_params(colors=TEXT_SECONDARY, labelsize=8.5)
    axes.grid(axis="y", color="#e8e7e3", linewidth=0.8)
    axes.set_axisbelow(True)
    axes.set_ylabel(ylabel, color=TEXT_SECONDARY, fontsize=9)
    if xlabel:
        axes.set_xlabel(xlabel, color=TEXT_SECONDARY, fontsize=9)


def _group_by_model_task(
    cells: Sequence[EmissionCell],
) -> dict[tuple[str, ...], list[EmissionCell]]:
    """Group cells into the figure's bars: one bar per model x task class."""
    grouped: dict[tuple[str, str], list[EmissionCell]] = {}
    for cell in cells:
        grouped.setdefault((cell.model, cell.task_class), []).append(cell)
    return dict(sorted(grouped.items()))


def _n_of(group: Sequence[EmissionCell]) -> int:
    return sum(cell.n_turns for cell in group)


def _share_of(group: Sequence[EmissionCell], state: ReasoningState) -> float:
    """Pooled share of one state across a group of cells."""
    total = _n_of(group)
    if total == 0:
        return 0.0
    return sum(cell.counts[state] for cell in group) / total


def _ordered_for_story(
    grouped: dict[tuple[str, ...], list[EmissionCell]],
) -> dict[tuple[str, ...], list[EmissionCell]]:
    """Order bars by readability, then by withholding, not alphabetically.

    Alphabetical order scatters the finding: `deepseek-v3.2` (absent) landed
    beside `deepseek-v3.2-reasoning-on` (raw) purely because of their names,
    while the three arms that share a state sat apart. Sorting by raw_present
    descending, then by redacted descending, puts the readable arms on the left,
    the withheld arms together on the right, and the arms that produced nothing
    at the far end - so the two different ways of scoring zero are adjacent and
    comparable rather than interleaved.
    """
    def key(item: tuple[tuple[str, ...], list[EmissionCell]]) -> tuple[float, float]:
        rate = pooled_raw_present(item[1])
        raw = rate.rate if rate.rate is not None else 0.0
        redacted = _share_of(item[1], ReasoningState.REDACTED)
        return (-raw, -redacted)

    return dict(sorted(grouped.items(), key=key))


def _bar_label(key: tuple[str, ...]) -> str:
    """Axis label for one bar: model alone, or model over task class."""
    if len(key) == 2:
        return f"{_display_model(key[0])}\n{key[1]}"
    return _display_model(key[0])


def _group_by_model(
    cells: Sequence[EmissionCell],
) -> dict[tuple[str, ...], list[EmissionCell]]:
    """Group cells into one bar per model, pooling task classes."""
    grouped: dict[tuple[str, ...], list[EmissionCell]] = {}
    for cell in cells:
        grouped.setdefault((cell.model,), []).append(cell)
    return grouped


def task_class_spread(cells: Sequence[EmissionCell]) -> dict[str, float]:
    """Max-minus-min raw_present across task classes, per model.

    The number that decides whether `figure_one(by_task=False)` is honest. A
    model whose spread is ~0 loses nothing by having its task classes pooled;
    one whose spread is large must keep them separate.
    """
    by_model_task: dict[str, dict[str, list[EmissionCell]]] = {}
    for cell in cells:
        by_model_task.setdefault(cell.model, {}).setdefault(
            cell.task_class, []
        ).append(cell)
    spread: dict[str, float] = {}
    for model, tasks in by_model_task.items():
        rates = []
        for group in tasks.values():
            rate = pooled_raw_present(group)
            if rate.rate is not None:
                rates.append(rate.rate)
        spread[model] = max(rates) - min(rates) if rates else 0.0
    return spread


def _display_model(model: str) -> str:
    """Shorten a provider-qualified model id for an axis tick.

    The record keeps the full id; only the tick is shortened, because colliding
    tick labels make a committed figure unreadable and an unreadable figure
    cannot be checked by a reader.
    """
    return model.split("/")[-1]


def _caption_one(
    plotted: Mapping[tuple[str, ...], Sequence[EmissionCell]],
    excluded: Sequence[tuple[str, ...]],
) -> str:
    """Standalone-readable caption for Figure 1, stating every n."""
    parts = []
    for key, group in plotted.items():
        model = key[0]
        task = key[1] if len(key) == 2 else "all task classes"
        shares = {
            state: _share_of(group, state) for state in ReasoningState
        }
        parts.append(
            f"{model} on {task}: n={_n_of(group)} assistant turns, "
            f"raw_present {shares[ReasoningState.RAW_PRESENT]:.3f} "
            f"({_interval_phrase(pooled_raw_present(group))}), "
            f"summary_only {shares[ReasoningState.SUMMARY_ONLY]:.3f}, "
            f"redacted {shares[ReasoningState.REDACTED]:.3f}, "
            f"absent {shares[ReasoningState.ABSENT]:.3f}"
        )
    caption = (
        "Figure 1. Share of assistant turns in each reasoning-channel state. "
        "The denominator is assistant turns that OCCURRED; turns that never happened "
        "because a trajectory ended earlier are not counted as absent. "
        + "; ".join(parts)
        + ". Error bars are Wilson 95% intervals on the raw_present share, clustered "
        "by trajectory: turns of one trajectory are not independent, so n is "
        "deflated by the design effect (icc = 1) before the interval is computed. "
        "A bar drawn from a single trajectory has no interval."
    )
    if excluded:
        caption += (
            f" Excluded from the plot for n < {MIN_CELL_N}: "
            + ", ".join("/".join(str(part) for part in key) for key in excluded)
            + " (these appear in the appendix table)."
        )
    return caption


def _interval_phrase(rate: RateWithCI) -> str:
    """The caption's interval clause: clustered bounds, or why there are none."""
    if rate.ci_low is None or rate.ci_high is None:
        return f"no interval: {rate.n_clusters} trajectory, status {rate.status}"
    return (
        f"95% CI {rate.ci_low:.3f}-{rate.ci_high:.3f}, clustered by trajectory, "
        f"{rate.n_clusters} trajectories"
    )


def _caption_two(arm: ArmProfile, stage2_recall: float) -> str:
    """Standalone caption for Figure 2, stating n, the unit and the induced prior."""
    effort = "" if arm.reasoning_effort is None else f", effort {arm.reasoning_effort}"
    total = sum(rate.n for rate in arm.points.values())
    trajectories = "trajectory" if arm.n_trajectories == 1 else "trajectories"
    caption = (
        f"Figure 2. {arm.model} on {arm.task_class}{effort}: measured positional "
        "coverage c(j), the share of assistant turns with readable raw reasoning, and "
        "the recall ceiling it imposes on a monitor gated on deliberation "
        f"(r₂ = {stage2_recall:g}). n = {total} assistant turns over "
        f"{arm.n_trajectories} {trajectories}, {_unit_phrase(arm)} "
        f"{_lowest_phrase(arm, stage2_recall)} {_low_n_phrase(arm)}"
        "The green dotted series is a TRANSFORMATION of a published value: 1 minus "
        "AdaptR1's per-step no-think ratio (arXiv:2605.31062, Table 4, MuSiQue, "
        "lambda=0.9), so that its polarity matches c(j); induced by RL objective, "
        "not observed. It is INDUCED because the reward pays for first-step no-think "
        "and the lambda term moves the whole profile across its range. It is plotted "
        "in its "
        "own panel, on its own step axis: their step 2 and our position 2 are not "
        "the same quantity. AdaptThink's task spread (arXiv:2505.13417: gsm8k "
        f"{ADAPTTHINK_TASK_SPREAD['gsm8k'].value:.3f}, math500 "
        f"{ADAPTTHINK_TASK_SPREAD['math500'].value:.3f}, aime "
        f"{ADAPTTHINK_TASK_SPREAD['aime'].value:.3f}) is not plotted here because it "
        "varies by task, not by step position, and is likewise induced."
    )
    if arm.n_trajectories == 1:
        caption += (
            " WARNING: all turns come from a single trajectory (n_clusters = 1), so "
            "no interval is drawn: within-trajectory independence is false and the "
            "bins are descriptive, not inferential."
        )
    return caption


def _unit_phrase(arm: ArmProfile) -> str:
    """How positions are indexed and what the error bars are."""
    if arm.unit == "bin":
        return (
            f"plotted in {len(arm.points)} equal-width bins of {arm.bin_width} steps "
            "each (bins, not steps: one trajectory gives one turn per step)."
        )
    return (
        f"plotted per step index across {len(arm.points)} steps. Error bars are "
        "Wilson 95% intervals per step, where each step holds at most one turn per "
        "trajectory."
    )


def _lowest_phrase(arm: ArmProfile, stage2_recall: float) -> str:
    """The worst position, chosen among powered positions only, and saying so."""
    powered = arm.powered()
    if not powered:
        return (
            f"No position has n ≥ {MIN_CELL_N}, so no lowest position is reported."
        )
    step = min(powered, key=lambda key: (powered[key].rate or 0.0, key))
    lowest = powered[step].rate or 0.0
    return (
        f"Among powered positions (n ≥ {MIN_CELL_N}), coverage is lowest at position "
        f"{step} ({lowest:.3f}, n = {powered[step].n}), so a monitor gated on "
        f"deliberation cannot exceed {lowest * stage2_recall:.3f} recall against an "
        "action taken there."
    )


def _low_n_phrase(arm: ArmProfile) -> str:
    """Name every low-n position, which the plot draws hollow and grey."""
    low = [(key, rate.n) for key, rate in arm.points.items() if rate.low_n]
    if not low:
        return ""
    named = ", ".join(f"{key} (n = {n})" for key, n in low)
    return (
        f"Low-n positions (n < {MIN_CELL_N}), drawn as hollow grey markers and "
        f"excluded from the lowest-position claim: {named}. "
    )
