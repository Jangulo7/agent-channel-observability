"""The positional verdict names rises, refuses one-cell shapes, and mixed tasks.

All profiles here are synthetic rates chosen to sit on either side of the rule.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from channels._vendored_stats import wilson_interval
from channels.emission import EmissionCell
from channels.schema import RateWithCI, ReasoningState

_spec = importlib.util.spec_from_file_location(
    "report_positional", Path(__file__).parents[1] / "scripts" / "report_positional.py"
)
assert _spec and _spec.loader
report_positional = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(report_positional)


def _rate(successes: int, n: int) -> RateWithCI:
    """A synthetic cell rate with its Wilson interval."""
    interval = wilson_interval(successes, n)
    return RateWithCI(successes / n, interval.low, interval.high, n, interval.method)


def test_rising_profile_is_reported_as_rising() -> None:
    """0.20 -> 0.90 at n=50 each is far outside step 0's interval, not noise."""
    verdict = report_positional._verdict({0: _rate(10, 50), 1: _rate(45, 50)})
    assert verdict.startswith("RISES 0.20 -> 0.90")


def test_declining_profile_is_still_reported_as_declining() -> None:
    verdict = report_positional._verdict({0: _rate(45, 50), 1: _rate(10, 50)})
    assert verdict.startswith("DECLINES 0.90 -> 0.20")


def test_small_move_inside_the_interval_is_within_noise() -> None:
    verdict = report_positional._verdict({0: _rate(40, 50), 1: _rate(36, 50)})
    assert "within noise" in verdict


def test_single_powered_cell_is_not_flat() -> None:
    """One powered step has no shape; FLAT would report an unobserved trajectory."""
    profile = {0: _rate(40, 50), 1: _rate(1, 5), 2: _rate(2, 5)}
    verdict = report_positional._verdict(profile)
    assert verdict.startswith("insufficient powered steps")
    assert "FLAT" not in verdict


def test_no_powered_cell_is_insufficient() -> None:
    verdict = report_positional._verdict({0: _rate(1, 5)})
    assert verdict.startswith("insufficient powered steps")


def test_flat_profile_is_flat() -> None:
    verdict = report_positional._verdict({0: _rate(50, 50), 1: _rate(49, 50)})
    assert verdict.startswith("FLAT")


def test_profile_leaving_the_interval_both_ways_is_not_one_direction() -> None:
    profile = {0: _rate(25, 50), 1: _rate(2, 50), 2: _rate(48, 50)}
    assert report_positional._verdict(profile).startswith("NON-MONOTONE")


def _cell(task_class: str) -> EmissionCell:
    """A synthetic emission cell for the synthetic arm."""
    counts = dict.fromkeys(ReasoningState, 0)
    counts[ReasoningState.RAW_PRESENT] = 1
    return EmissionCell("synthetic_arm", task_class, 0, None, 1, counts)


def test_arm_with_one_task_class_returns_it() -> None:
    cells = [_cell("synthetic_task"), _cell("synthetic_task")]
    assert report_positional._task_class(cells, "synthetic_arm") == "synthetic_task"


def test_arm_with_several_task_classes_raises() -> None:
    """Profiling cells[0]'s class would silently drop the others."""
    cells = [_cell("synthetic_task_a"), _cell("synthetic_task_b")]
    with pytest.raises(report_positional.MixedTaskClassError, match="synthetic_task_b"):
        report_positional._task_class(cells, "synthetic_arm")
