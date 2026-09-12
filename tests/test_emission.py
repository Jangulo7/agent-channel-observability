"""The primary estimator, and the denominator rule it exists to make explicit."""

from channels.emission import (
    MIN_CELL_N,
    build_cells,
    cell_rate,
    emission_rate,
    positional_profile,
    trajectory_rate,
    uninspectable_share,
)
from channels.schema import ReasoningState

from .fixtures.synthetic import turns

RAW = ReasoningState.RAW_PRESENT
ABSENT = ReasoningState.ABSENT
SUMMARY = ReasoningState.SUMMARY_ONLY


def test_emission_denominator_excludes_turns_that_never_happened() -> None:
    """The AdaptR1 lesson, encoded.

    One trajectory of length 3 and one of length 1. At step 2 exactly one turn
    occurred, so the denominator there is 1 — not 2 with the short trajectory counted
    as ABSENT. Counting non-existent turns would drive emission toward zero purely as
    a function of trajectory length.
    """
    observations = [
        *turns([RAW, RAW, RAW], sample_id="SYNTHETIC_LONG"),
        *turns([RAW], sample_id="SYNTHETIC_SHORT"),
    ]
    cells = {c.step_index: c for c in build_cells(observations)}
    assert cells[0].n_turns == 2
    assert cells[2].n_turns == 1
    assert cells[2].counts[ABSENT] == 0
    assert emission_rate(cells[2]) == 1.0


def test_cell_counts_sum_to_n_turns() -> None:
    cells = build_cells(turns([RAW, SUMMARY, ABSENT]))
    for cell in cells:
        assert sum(cell.counts.values()) == cell.n_turns


def test_positional_profile_not_collapsed() -> None:
    """positional_profile returns per-step values, and the mean helper returns both."""
    observations = [
        *turns([RAW, ABSENT], sample_id="SYNTHETIC_A"),
        *turns([RAW, ABSENT], sample_id="SYNTHETIC_B"),
    ]
    cells = build_cells(observations)
    profile = positional_profile(cells, "SYNTHETIC-MODEL-A", "synthetic_task")
    assert sorted(profile) == [0, 1]
    assert profile[0].rate == 1.0
    assert profile[1].rate == 0.0

    mean, returned_profile = trajectory_rate(
        cells, "SYNTHETIC-MODEL-A", "synthetic_task"
    )
    assert mean.rate == 0.5
    assert mean.weighting == "action-weighted"
    # The mean cannot be obtained without the profile coming with it.
    assert returned_profile == profile


def test_low_n_cells_flagged() -> None:
    small = build_cells(turns([RAW] * 1))[0]
    assert cell_rate(small).low_n is True

    many = [
        *(
            observation
            for index in range(MIN_CELL_N)
            for observation in turns([RAW], sample_id=f"SYNTHETIC_{index}")
        )
    ]
    big = build_cells(many)[0]
    assert big.n_turns == MIN_CELL_N
    assert cell_rate(big).low_n is False


def test_uninspectable_share_counts_all_three_states() -> None:
    cells = build_cells(turns([RAW, SUMMARY, ReasoningState.REDACTED, ABSENT]))
    share = uninspectable_share(cells)
    assert share.rate == 0.75
    assert share.n == 4


def test_uninspectable_share_reports_no_denominator_when_empty() -> None:
    """An empty corpus yields a status, never a rate of 0.0."""
    share = uninspectable_share([])
    assert share.rate is None
    assert share.status == "no_denominator"


def test_cells_are_split_by_reasoning_effort() -> None:
    """Effort strata must not pool, since pooling them hides the designed comparison."""
    observations = [
        *turns([RAW], effort="high", sample_id="SYNTHETIC_H"),
        *turns([ABSENT], effort="low", sample_id="SYNTHETIC_L"),
    ]
    cells = build_cells(observations)
    assert len(cells) == 2
    assert {c.reasoning_effort for c in cells} == {"high", "low"}
