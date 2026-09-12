"""Recall ceilings: what coverage of the reasoning channel permits a monitor to achieve.

The argument is arithmetic, not empirical. A detector that only looks when the model
deliberated cannot find what the model never deliberated about, so its recall is capped
by the emission rate regardless of how good its second stage is.
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
    """
    _check_unit_interval(coverage, "coverage")
    _check_unit_interval(stage2_recall, "stage2_recall")
    return coverage * stage2_recall


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
