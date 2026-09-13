"""RQ3 returns a bound and its blockers, never a rate."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from channels.errors import ProvenanceError, UnvalidatedDetectorError
from channels.rq3 import (
    REGISTERED_SENSITIVITY_ANALYSES,
    denominator_sensitivity,
    feasible_denominator,
    recall_corrected_bound,
    rq3_endpoint,
    rung1_obj_recalls,
)
from channels.schema import Channel, Provenance, Utterance
from channels.tree import TreeCoder
from channels.validate import CodeScore, ValidationRecord, write_validation


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


# --- Guards wired at the entry point, recalls read from records, deviations ---

SYNTHETIC_HASH = "sha256:synthetic-test-codebook"


def _synthetic_utt(uid: str, provenance: Provenance) -> Utterance:
    """An obviously synthetic utterance; its text is never inspected here."""
    return Utterance(
        uid=f"synthetic:{uid}",
        corpus="synthetic",
        channel=Channel.INTER_AGENT_MESSAGE,
        provenance=provenance,
        text="synthetic placeholder",
        actor="synthetic_agent",
    )


def _write_synthetic_record(
    directory: Path, name: str, recall: float, interval: tuple[float, float]
) -> None:
    """Persist a synthetic OBJ validation record; the numbers are test inputs only."""
    score = CodeScore("OBJ", 100, 100, int(recall * 100), recall, interval, 0.5, 0.5)
    write_validation(
        ValidationRecord(name, "1.0", SYNTHETIC_HASH, "synthetic", 100, {"OBJ": score}),
        directory,
    )


def test_entry_point_raises_for_an_unvalidated_detector(tmp_path: Path) -> None:
    """A count from a detector with no record never becomes a bound."""
    utts = [_synthetic_utt("1", Provenance.VERBATIM)]
    with pytest.raises(UnvalidatedDetectorError, match="no validation record"):
        rq3_endpoint(
            Counter({1: 7, 2: 3}), observed_objections=0, utterances=utts,
            detector=TreeCoder(), codebook=SYNTHETIC_HASH, validation_dir=tmp_path,
        )


def test_entry_point_raises_for_a_count_from_no_named_detector(tmp_path: Path) -> None:
    utts = [_synthetic_utt("1", Provenance.VERBATIM)]
    with pytest.raises(UnvalidatedDetectorError, match="without the detector"):
        rq3_endpoint(
            Counter({1: 7, 2: 3}), observed_objections=0, utterances=utts,
            codebook=SYNTHETIC_HASH, validation_dir=tmp_path,
        )


def test_entry_point_raises_for_non_primary_provenance(tmp_path: Path) -> None:
    """A paraphrase reaching the endpoint raises even when the detector is validated."""
    _write_synthetic_record(tmp_path, "tree_coder", 0.5, (0.4, 0.6))
    utts = [
        _synthetic_utt("1", Provenance.VERBATIM),
        _synthetic_utt("2", Provenance.PARAPHRASE),
    ]
    with pytest.raises(ProvenanceError, match="synthetic:2"):
        rq3_endpoint(
            Counter({1: 7, 2: 3}), observed_objections=0, utterances=utts,
            detector=TreeCoder(), codebook=SYNTHETIC_HASH, validation_dir=tmp_path,
        )


def test_entry_point_checks_provenance_even_without_a_count(tmp_path: Path) -> None:
    utts = [_synthetic_utt("1", Provenance.INVESTIGATOR_SUMMARY)]
    with pytest.raises(ProvenanceError):
        rq3_endpoint(Counter({1: 7, 2: 3}), utterances=utts, validation_dir=tmp_path)


def test_count_without_utterances_raises(tmp_path: Path) -> None:
    with pytest.raises(ProvenanceError, match="without the utterances"):
        rq3_endpoint(
            Counter({1: 7, 2: 3}), observed_objections=0, detector=TreeCoder(),
            codebook=SYNTHETIC_HASH, validation_dir=tmp_path,
        )


def test_validated_gated_count_gives_a_bound(tmp_path: Path) -> None:
    """With both guards satisfied the endpoint still returns a bound, never a rate."""
    _write_synthetic_record(tmp_path, "tree_coder", 0.5, (0.4, 0.6))
    _write_synthetic_record(tmp_path, "nli_detector", 0.25, (0.2, 0.3))
    result = rq3_endpoint(
        Counter({1: 7, 2: 3}), observed_objections=0,
        utterances=[_synthetic_utt("1", Provenance.VERBATIM)],
        detector=TreeCoder(), codebook=SYNTHETIC_HASH, validation_dir=tmp_path,
    )
    assert result.rate is None
    assert result.rate_status == "one_sided_bound_only"
    assert result.upper_bound_95 is not None


def test_recalls_are_read_from_the_records_not_restated(tmp_path: Path) -> None:
    _write_synthetic_record(tmp_path, "tree_coder", 0.5, (0.4, 0.6))
    _write_synthetic_record(tmp_path, "nli_detector", 0.25, (0.2, 0.3))
    recalls = rung1_obj_recalls(SYNTHETIC_HASH, tmp_path)
    assert recalls == (
        ("tree_coder", 0.5, (0.4, 0.6)),
        ("nli_detector", 0.25, (0.2, 0.3)),
    )
    result = rq3_endpoint(
        Counter({1: 7, 2: 3}), codebook=SYNTHETIC_HASH, validation_dir=tmp_path
    )
    assert "2.0x" in result.blockers[1]
    assert "non-overlapping" in result.blockers[1]


def test_missing_validation_record_raises_not_defaults(tmp_path: Path) -> None:
    with pytest.raises(UnvalidatedDetectorError):
        rung1_obj_recalls(SYNTHETIC_HASH, tmp_path)
    with pytest.raises(UnvalidatedDetectorError):
        rq3_endpoint(
            Counter({1: 7, 2: 3}), codebook=SYNTHETIC_HASH, validation_dir=tmp_path
        )


def test_substituted_sensitivity_analyses_are_declared_as_a_deviation() -> None:
    """The registered §8.2 analyses were not run; the result must say so."""
    result = rq3_endpoint(Counter({1: 70, 2: 30}))
    assert result.sensitivity_analyses_registered == REGISTERED_SENSITIVITY_ANALYSES
    assert any("dse" in a for a in result.sensitivity_analyses_registered)
    assert any("attribution" in a for a in result.sensitivity_analyses_registered)
    assert any("recall correction" in a for a in result.sensitivity_analyses_run)
    assert any("denominator" in a for a in result.sensitivity_analyses_run)
    joined = " ".join(result.deviations)
    assert "deviation" in joined
    assert "wiki" in joined and "not an actor" in joined
