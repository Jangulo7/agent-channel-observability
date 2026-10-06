"""Recall ceilings: what coverage of the reasoning channel permits a monitor to achieve.

The argument is arithmetic, not empirical. A detector that only looks when the model
deliberated cannot find what the model never deliberated about, so its recall is capped
by the emission rate regardless of how good its second stage is.

The units must agree. `coverage` and `stage2_recall` have to be measured over the same
unit of observation, because the product is a statement about that unit. Mixing a
per-turn coverage with a per-trajectory recall understates the ceiling: a trajectory is
caught if *any* readable turn flags, so the multiplier for a trajectory-level recall is
the share of trajectories with at least one readable turn, which exceeds the share of
readable turns whenever readable turns cluster. `assert_bound_respected` exists to make
that mistake raise rather than print.
"""

from collections.abc import Mapping

from channels.errors import InvalidRateError


def recall_ceiling(coverage: float, stage2_recall: float) -> float:
    """Upper bound on system recall for a detector gated on deliberation.

    A two-stage detector that runs its expensive check only when a cheap trigger
    fires has recall at most coverage * stage2_recall. Hua et al.
    (arXiv:2507.15886) optimise the monitor-calling probability p_m as a
    defender's budgeted choice; here coverage is imposed by the model's emission
    behaviour, so sup(p_m) = coverage and no budget restores the difference.

    `coverage` must be measured over the same unit as `stage2_recall` and as the
    recall this bounds. Under the abstention rule of `channels.monitor` (a channel
    with no content never catches) the relation is an *identity* on that shared
    unit, not an inequality: recall = coverage * stage2_recall exactly, because the
    uncovered share contributes zero catches. It is written as a bound because
    `stage2_recall` is itself usually an estimate from the covered subset.
    """
    _check_unit_interval(coverage, "coverage")
    _check_unit_interval(stage2_recall, "stage2_recall")
    return coverage * stage2_recall


def recall_ceiling_trajectory(p_any_readable: float, stage2_recall: float) -> float:
    """Trajectory-level recall ceiling, for a monitor scored per trajectory.

    `p_any_readable` is the share of positive trajectories with *at least one*
    readable relevant turn — not the share of readable turns. The per-turn share is
    the wrong multiplier here: one readable turn is enough to catch a trajectory, so
    a corpus whose readable turns concentrate in few trajectories has a much lower
    per-turn coverage than per-trajectory coverage, and the per-turn product then
    sits below the recall actually achievable.

    This is the same arithmetic as `recall_ceiling`; the separate name exists so the
    unit is visible at the call site and in the record.
    """
    _check_unit_interval(p_any_readable, "p_any_readable")
    return recall_ceiling(p_any_readable, stage2_recall)


def assert_bound_respected(
    observed_recall: float, coverage: float, stage2_recall: float, *, unit: str
) -> None:
    """Raise unless an observed recall is consistent with its stated ceiling.

    A guard clause, not a diagnostic. An observed recall above coverage *
    stage2_recall means the two factors were not measured over the unit the recall
    was measured over, and the usual cause is a per-turn coverage paired with a
    per-trajectory recall. Reporting such a ceiling beside the recall it fails to
    bound is the error this refuses to let through.

    `unit` names the unit of observation ("turn", "trajectory") and appears in the
    message so the fix is obvious from the traceback.
    """
    _check_unit_interval(observed_recall, "observed_recall")
    ceiling = recall_ceiling(coverage, stage2_recall)
    if observed_recall > ceiling:
        raise InvalidRateError(
            f"observed recall {observed_recall:.4f} exceeds the ceiling "
            f"{ceiling:.4f} = coverage {coverage:.4f} * stage2_recall "
            f"{stage2_recall:.4f}, computed over unit {unit!r}. A recall cannot "
            "exceed its own ceiling, so the factors were not measured over the "
            "unit the recall was measured over. A per-turn coverage does not "
            "bound a per-trajectory recall: use recall_ceiling_trajectory with "
            "the share of trajectories holding at least one readable turn."
        )


def recall_ceiling_at_step(
    profile: Mapping[int, float], step: int, stage2_recall: float
) -> float:
    """Recall ceiling at one step position, using the positional profile c(j).

    The decision-relevant quantity is coverage at the step where the harmful
    action occurs, not mean coverage. The direction of the profile is
    task-structure-dependent: AdaptR1 finds no-think early and explicit
    reasoning late in multi-hop QA ("retrieve-then-reason"). Long-horizon
    agentic trajectories may invert this, and that is what we measure.
    """
    if step not in profile:
        raise InvalidRateError(
            f"no coverage recorded at step {step}; "
            f"profile covers steps {sorted(profile)}"
        )
    return recall_ceiling(profile[step], stage2_recall)


def ceiling_profile(
    profile: Mapping[int, float], stage2_recall: float
) -> dict[int, float]:
    """Apply the ceiling at every step, returning c(j) * r2 as a profile."""
    return {
        step: recall_ceiling(coverage, stage2_recall)
        for step, coverage in profile.items()
    }


def worst_step(profile: Mapping[int, float]) -> tuple[int, float]:
    """The step position with the lowest coverage, and that coverage.

    Reported alongside the mean because an adversary chooses when to act, and the
    step where coverage is weakest is the step where acting is cheapest.
    """
    if not profile:
        raise InvalidRateError("cannot take the worst step of an empty profile")
    step = min(profile, key=lambda key: profile[key])
    return step, profile[step]


def _check_unit_interval(value: float, name: str) -> None:
    """Raise InvalidRateError unless value lies in [0, 1]."""
    if not 0.0 <= value <= 1.0:
        raise InvalidRateError(
            f"{name} must lie in [0, 1], got {value}. A recall ceiling built from a "
            "value outside that range is not a probability."
        )
