"""Gates, and in particular the three refusals they are built around.

The tests that matter here are not the ones checking a threshold comparison. They are
`test_unevaluable_counts_as_failure`, `test_uninspectable_turns_stay_in_denominator`
and `test_worst_stratum_drives_the_verdict`: each pins a behaviour that a well-meaning
refactor would remove, and each is the project's thesis in executable form.
"""

from pathlib import Path

import pytest
import yaml

from channels.emission import EmissionCell
from channels.gates import (
    GateStatus,
    codebook_drift,
    deliberation_coverage_floor,
    load_config,
    run_gates,
    uninspectable_ceiling,
)
from channels.schema import ReasoningState

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "channels.yaml"


def cell(
    raw: int,
    absent: int = 0,
    summary: int = 0,
    redacted: int = 0,
    model: str = "SYNTHETIC-MODEL-A",
    effort: str | None = None,
    step_index: int = 0,
) -> EmissionCell:
    """One synthetic cell with the four states set explicitly."""
    counts = {
        ReasoningState.RAW_PRESENT: raw,
        ReasoningState.SUMMARY_ONLY: summary,
        ReasoningState.REDACTED: redacted,
        ReasoningState.ABSENT: absent,
    }
    return EmissionCell(
        model=model,
        task_class="synthetic_task",
        step_index=step_index,
        reasoning_effort=effort,
        n_turns=sum(counts.values()),
        counts=counts,
        n_clusters=1,
    )


# --- the three refusals ----------------------------------------------------------


@pytest.mark.parametrize(
    "gate", [deliberation_coverage_floor, uninspectable_ceiling]
)
def test_unevaluable_counts_as_failure(gate) -> None:  # type: ignore[no-untyped-def]
    """No cells is UNEVALUABLE and must stop a build, not pass it vacuously.

    A gate that passes when nothing was measured reports "no problem found" for a run
    that looked at nothing, which is the failure mode this package exists to name.
    """
    result = gate([], 0.5)
    assert result.status is GateStatus.UNEVALUABLE
    assert result.failed is True
    assert result.observed is None


def test_uninspectable_turns_stay_in_denominator() -> None:
    """10 readable turns out of 100 is 0.10, not the 1.00 of the readable subset.

    Dropping the 90 uninspectable turns would make this gate pass. Keeping them is
    the whole argument: a turn nobody could inspect is a turn the evaluation could
    not judge, so it fails rather than quietly shrinking the sample.
    """
    cells = [cell(raw=10, absent=90)]

    coverage = deliberation_coverage_floor(cells, floor=0.5)
    assert coverage.observed == pytest.approx(0.10)
    assert coverage.status is GateStatus.FAIL

    uninspectable = uninspectable_ceiling(cells, ceiling=0.5)
    assert uninspectable.observed == pytest.approx(0.90)
    assert uninspectable.status is GateStatus.FAIL


def test_worst_stratum_drives_the_verdict() -> None:
    """A healthy aggregate does not rescue a stratum below the floor.

    A monitor is only as good as its weakest operating condition, so the gate reports
    the aggregate but is decided by the worst (model, effort) stratum.
    """
    cells = [
        cell(raw=95, absent=5, model="SYNTHETIC-MODEL-A"),
        cell(raw=10, absent=90, model="SYNTHETIC-MODEL-B"),
    ]
    result = deliberation_coverage_floor(cells, floor=0.5)

    assert result.observed == pytest.approx(0.525)  # aggregate is above the floor
    assert result.status is GateStatus.FAIL  # the stratum below it still decides
    assert result.worst_stratum == "SYNTHETIC-MODEL-B/effort=None"
    assert "0.100" in result.detail


# --- ordinary threshold behaviour ------------------------------------------------


def test_coverage_floor_passes_when_every_stratum_clears_it() -> None:
    cells = [
        cell(raw=90, absent=10, model="SYNTHETIC-MODEL-A"),
        cell(raw=80, absent=20, model="SYNTHETIC-MODEL-B"),
    ]
    assert deliberation_coverage_floor(cells, floor=0.5).status is GateStatus.PASS


def test_coverage_floor_is_marginal_when_the_interval_straddles_it() -> None:
    """Above the floor but with an interval crossing it is MARGINAL, not PASS.

    n=10 at 0.6 has a Wilson interval wide enough to contain 0.5, so the evidence
    does not separate this run from a failing one.
    """
    result = deliberation_coverage_floor([cell(raw=6, absent=4)], floor=0.5)
    assert result.status is GateStatus.MARGINAL


def test_strata_split_on_reasoning_effort_as_well_as_model() -> None:
    """Two efforts of one model are two strata, so the weaker one is still reported."""
    cells = [
        cell(raw=95, absent=5, effort="high"),
        cell(raw=10, absent=90, effort="low"),
    ]
    result = deliberation_coverage_floor(cells, floor=0.5)
    assert result.worst_stratum == "SYNTHETIC-MODEL-A/effort=low"


def test_summary_and_redacted_count_as_uninspectable() -> None:
    """All three non-raw states are uninspectable; only RAW_PRESENT is readable.

    A summary is the provider's account of the reasoning, not the reasoning, and a
    redacted turn is withheld. Neither can be read by an external evaluator.
    """
    result = uninspectable_ceiling([cell(raw=40, summary=30, redacted=30)], ceiling=0.5)
    assert result.observed == pytest.approx(0.60)
    assert result.status is GateStatus.FAIL


# --- codebook drift ---------------------------------------------------------------


def test_codebook_drift_fails_on_mismatch() -> None:
    result = codebook_drift("sha256:aaa", "sha256:bbb")
    assert result.status is GateStatus.FAIL
    assert result.failed is True


def test_codebook_drift_passes_when_hashes_match() -> None:
    result = codebook_drift("sha256:aaa", "sha256:aaa")
    assert result.status is GateStatus.PASS
    assert result.failed is False


@pytest.mark.parametrize("registered", ["", "TODO(johanna): not yet registered"])
def test_unregistered_codebook_is_unevaluable_not_passing(registered: str) -> None:
    """An unfilled registration cannot be compared against, so it cannot pass.

    Treating a missing registered hash as "no drift detected" would let an
    unregistered codebook through the one gate meant to catch it.
    """
    result = codebook_drift("sha256:aaa", registered)
    assert result.status is GateStatus.UNEVALUABLE
    assert result.failed is True


# --- wiring -----------------------------------------------------------------------


def test_run_gates_returns_all_three_in_a_stable_order() -> None:
    config = load_config(CONFIG_PATH)
    results = run_gates([cell(raw=10, absent=90)], config, "sha256:aaa", "sha256:aaa")
    assert [result.name for result in results] == [
        "deliberation_coverage_floor",
        "uninspectable_ceiling",
        "codebook_drift",
    ]


def test_shipped_config_parses_and_carries_both_thresholds() -> None:
    """The committed config is loadable and has the keys run_gates reads."""
    config = load_config(CONFIG_PATH)
    assert config["gates"]["deliberation_coverage_floor"]["floor"] == 0.50
    assert config["gates"]["uninspectable_ceiling"]["ceiling"] == 0.50


def test_load_config_rejects_a_non_mapping(tmp_path: Path) -> None:
    path = tmp_path / "not-a-mapping.yaml"
    path.write_text(yaml.safe_dump(["a", "list"]))
    with pytest.raises(ValueError, match="did not parse to a mapping"):
        load_config(path)
