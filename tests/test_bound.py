"""Recall ceilings, including the inputs that must be refused."""

import pytest

from channels.bound import (
    ceiling_profile,
    recall_ceiling,
    recall_ceiling_at_step,
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
