"""Recall ceilings, including the inputs that must be refused."""

import pytest

from channels.bound import (
    assert_bound_respected,
    ceiling_profile,
    recall_ceiling,
    recall_ceiling_at_step,
    recall_ceiling_trajectory,
    worst_step,
)
from channels.errors import InvalidRateError


def test_recall_ceiling_bounds() -> None:
    """Zero coverage caps recall at zero however good the second stage is."""
    assert recall_ceiling(0.0, 1.0) == 0.0
    assert recall_ceiling(1.0, 1.0) == 1.0
    assert recall_ceiling(0.5, 0.8) == pytest.approx(0.4)


@pytest.mark.parametrize(
    ("coverage", "stage2"),
    [(-0.1, 1.0), (1.1, 1.0), (0.5, -0.01), (0.5, 1.01)],
)
def test_out_of_range_inputs_raise(coverage: float, stage2: float) -> None:
    with pytest.raises(InvalidRateError):
        recall_ceiling(coverage, stage2)


def test_recall_ceiling_at_step_uses_that_step() -> None:
    profile = {0: 0.4, 1: 0.1}
    assert recall_ceiling_at_step(profile, 1, 1.0) == pytest.approx(0.1)


def test_missing_step_raises_rather_than_defaulting() -> None:
    """A step with no recorded coverage is missing data, not coverage of zero."""
    with pytest.raises(InvalidRateError) as excinfo:
        recall_ceiling_at_step({0: 0.4}, 7, 1.0)
    assert "step 7" in str(excinfo.value)


def test_ceiling_profile_applies_at_every_step() -> None:
    assert ceiling_profile({0: 0.4, 1: 0.2}, 0.5) == {0: pytest.approx(0.2),
                                                     1: pytest.approx(0.1)}


def test_worst_step_reports_the_weakest_position() -> None:
    assert worst_step({0: 0.4, 1: 0.1, 2: 0.3}) == (1, 0.1)


def test_worst_step_of_empty_profile_raises() -> None:
    with pytest.raises(InvalidRateError):
        worst_step({})


# --- Unit agreement between the two factors and the recall they bound. ---------------
#
# The constants below are the measured qwen3-32b monitor arms
# (results/monitor_experiment_qwen3/monitor_record.json), not illustrations:
#   dark arm, reasoning channel: 11 of 155 turns carried content (144 abstentions),
#   and at least 4 of the 38 positive trajectories were caught (4 of the 24
#   trajectories still running at step 3 had been flagged by then).
#   visible arm, step 0: 39 of 42 caught, so stage-2 recall is 39/42.
DARK_TURN_COVERAGE = 11 / 155
DARK_TRAJECTORY_COVERAGE = 11 / 38  # upper: at most 11 trajectories hold those turns
DARK_OBSERVED_RECALL = 4 / 38
STAGE2_RECALL = 39 / 42


def test_recall_ceiling_trajectory_matches_the_product() -> None:
    """The trajectory ceiling is the same arithmetic, named for its unit."""
    assert recall_ceiling_trajectory(0.289, STAGE2_RECALL) == pytest.approx(
        0.2684, abs=1e-4
    )
    assert recall_ceiling_trajectory(0.0, 1.0) == 0.0


def test_recall_ceiling_never_exceeds_either_factor() -> None:
    """A product of two probabilities cannot exceed the smaller of them."""
    for coverage in (0.0, 0.07, 0.29, 0.5, 0.93, 1.0):
        for stage2 in (0.0, 0.17, 0.5, 0.93, 1.0):
            assert recall_ceiling(coverage, stage2) <= min(coverage, stage2) + 1e-12


def test_turn_level_coverage_cannot_bound_trajectory_recall() -> None:
    """The measured dark arm violates the bound when coverage is counted per turn.

    This is the defect the review found in the manuscript's Equation (1): a per-turn
    coverage of 11/155 against a per-trajectory recall of 39/42 gives a ceiling of
    0.066, i.e. 2.5 of 38 trajectories, while at least 4 of 38 were caught. The guard
    must refuse it, and must accept the same recall against a trajectory-level
    coverage.
    """
    with pytest.raises(InvalidRateError) as excinfo:
        assert_bound_respected(
            DARK_OBSERVED_RECALL,
            DARK_TURN_COVERAGE,
            STAGE2_RECALL,
            unit="turn",
        )
    message = str(excinfo.value)
    assert "exceeds the ceiling" in message
    assert "per-turn coverage does not bound a per-trajectory recall" in message

    # Same observed recall, coverage measured over the unit the recall is measured
    # over: consistent, so no raise.
    assert_bound_respected(
        DARK_OBSERVED_RECALL,
        DARK_TRAJECTORY_COVERAGE,
        STAGE2_RECALL,
        unit="trajectory",
    )


def test_assert_bound_respected_accepts_equality() -> None:
    """Under the abstention rule the relation is an identity, so equality must pass."""
    assert_bound_respected(0.4, 0.5, 0.8, unit="turn")


def test_assert_bound_respected_rejects_an_impossible_recall() -> None:
    with pytest.raises(InvalidRateError):
        assert_bound_respected(1.5, 1.0, 1.0, unit="turn")
