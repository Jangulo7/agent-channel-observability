"""The vendored statistics behave as the published interval maths says they should."""

import pytest

from channels._vendored_stats import (
    bootstrap_ci,
    wilson_interval,
    wilson_upper_bound,
)
from channels.errors import InvalidRateError


def test_wilson_interval_stays_inside_unit_range() -> None:
    """The reason Wilson is used at all: safety rates sit near 0 and 1."""
    interval = wilson_interval(0, 30)
    assert interval.low == 0.0
    assert 0.0 < interval.high < 1.0


def test_wilson_upper_bound_approximates_rule_of_three() -> None:
    """With zero events in n trials the 95% one-sided bound is near 3/n."""
    assert wilson_upper_bound(0, 100) == pytest.approx(3.0 / 100, abs=0.01)


def test_wilson_upper_bound_rejects_empty_denominator() -> None:
    with pytest.raises(InvalidRateError):
        wilson_upper_bound(0, 0)


def test_bootstrap_is_seeded_and_reproducible() -> None:
    values = [0.0, 1.0] * 25
    assert bootstrap_ci(values, seed=7) == bootstrap_ci(values, seed=7)


def test_wilson_interval_always_contains_its_point_estimate() -> None:
    """Regression: at successes=0 float error put the lower limit above the estimate.

    At n=500 the unclamped Wilson lower limit evaluates to 4.3e-19, not 0.0, which
    makes an error bar of negative length and states an interval that excludes the
    rate it describes. Found when the three-benchmark Inspect corpus produced
    exact-zero emission cells.
    """
    for n in (1, 30, 313, 450, 500, 3789, 10_000):
        for successes in (0, n):
            interval = wilson_interval(successes, n)
            point = successes / n
            assert interval.low <= point <= interval.high, (
                f"n={n}, successes={successes}: interval "
                f"({interval.low}, {interval.high}) excludes {point}"
            )
