"""RQ3 returns a bound and its blockers, never a rate."""

from __future__ import annotations

from collections import Counter

import pytest

from channels.rq3 import (
    denominator_sensitivity,
    feasible_denominator,
    recall_corrected_bound,
    rq3_endpoint,
)


def test_single_actor_pages_leave_the_denominator() -> None:
    """A page one agent edited is no denominator, not a small one."""
    total, single, multi = feasible_denominator(Counter({1: 70, 2: 20, 3: 10}))
    assert (total, single, multi) == (100, 70, 30)


def test_endpoint_refuses_a_rate_without_a_validated_detector() -> None:
    result = rq3_endpoint(Counter({1: 70, 2: 30}))
    assert result.rate is None
    assert result.rate_status == "no_validated_detector_for_this_corpus"
    assert result.upper_bound_95 is None
    assert len(result.blockers) == 3


def test_zero_observed_gives_a_bound_not_a_bare_zero() -> None:
    """'Zero observed' states nothing; 'below X with 95% confidence' does."""
    result = rq3_endpoint(Counter({1: 70, 2: 30}), observed_objections=0)
    assert result.rate is None
    assert result.rate_status == "one_sided_bound_only"
    assert result.upper_bound_95 is not None
    assert 0.0 < result.upper_bound_95 < 1.0


def test_recall_correction_shows_the_detector_dependence() -> None:
    """The same observed rate implies very different truths under the two recalls."""
    at_tree = recall_corrected_bound(0.01, 0.072)
    at_nli = recall_corrected_bound(0.01, 0.218)
    assert at_tree > at_nli
    assert at_tree / at_nli == pytest.approx(0.218 / 0.072, rel=1e-6)


def test_recall_correction_rejects_impossible_recall() -> None:
    with pytest.raises(ValueError, match="must be in"):
        recall_corrected_bound(0.01, 0.0)


def test_denominator_choice_changes_the_rate_materially() -> None:
    """The reporting-unit choice the prior art leaves unstated, quantified."""
    over_all, over_feasible = denominator_sensitivity(
        10, all_pages=4024, feasible_pages=1200
    )
    assert over_feasible > over_all
    assert over_feasible / over_all == pytest.approx(4024 / 1200)
