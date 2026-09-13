"""The gatekeeper raises, and undefined recall is never reported as zero."""

from __future__ import annotations

from pathlib import Path

import pytest

from channels.detect import DetectorResult
from channels.errors import UnvalidatedDetectorError
from channels.schema import Channel, Provenance, Utterance
from channels.tree import CodedLabel, TreeCoder
from channels.validate import (
    load_validations,
    require_validation,
    shuffled_control,
    validate,
    validate_from_result,
    write_validation,
)


def _utt(uid: str, text: str, gold: str | None) -> Utterance:
    """A synthetic control utterance carrying its gold code."""
    return Utterance(
        uid=uid,
        corpus="synthetic_control",
        channel=Channel.INTER_AGENT_MESSAGE,
        provenance=Provenance.VERBATIM,
        text=text,
        actor="agent_a",
        corpus_meta={"gold_code": gold},
    )


def test_unvalidated_detector_raises(tmp_path: Path) -> None:
    """The architectural rule: no rate without a recorded, validated recall."""
    with pytest.raises(UnvalidatedDetectorError, match="no validation record"):
        require_validation(TreeCoder(), "sha256:whatever", directory=tmp_path)


def test_validation_is_keyed_on_the_codebook_hash(tmp_path: Path) -> None:
    """A record earned against one codebook does not validate another."""
    control = [_utt("s:1", "you should not do that", "OBJ")]
    record = validate(TreeCoder(), control, "sha256:aaa", "synthetic", ["OBJ"])
    write_validation(record, tmp_path)
    assert require_validation(TreeCoder(), "sha256:aaa", tmp_path).codebook_hash == (
        "sha256:aaa"
    )
    with pytest.raises(UnvalidatedDetectorError):
        require_validation(TreeCoder(), "sha256:bbb", tmp_path)


def test_recall_is_undefined_not_zero_when_the_control_has_no_support() -> None:
    """A code absent from the control has no recall. Zero would be an invention."""
    control = [_utt("s:1", "please confirm the hash", "SHARE")]
    record = validate(TreeCoder(), control, "sha256:aaa", "synthetic", ["ESC"])
    score = record.scores["ESC"]
    assert score.support == 0
    assert score.recall is None
    assert score.recall_ci95 is None
    assert score.status == "no_support_in_control"


def test_measured_recall_carries_an_interval() -> None:
    control = [
        _utt("s:1", "you should not do that", "OBJ"),
        _utt("s:2", "that is unacceptable conduct", "OBJ"),
        _utt("s:3", "zzqqxx", "OBJ"),
    ]
    record = validate(TreeCoder(), control, "sha256:aaa", "synthetic", ["OBJ"])
    score = record.scores["OBJ"]
    assert score.support == 3
    assert score.true_positives == 2
    assert score.recall == pytest.approx(2 / 3)
    assert score.recall_ci95 is not None
    low, high = score.recall_ci95
    assert low < score.recall < high


def test_validation_round_trips_through_disk(tmp_path: Path) -> None:
    control = [_utt("s:1", "you should not do that", "OBJ")]
    record = validate(TreeCoder(), control, "sha256:aaa", "synthetic", ["OBJ"])
    write_validation(record, tmp_path)
    loaded = require_validation(TreeCoder(), "sha256:aaa", tmp_path)
    assert loaded.scores["OBJ"].recall == record.scores["OBJ"].recall
    assert loaded.scores["OBJ"].recall_ci95 == record.scores["OBJ"].recall_ci95


def test_shuffled_control_preserves_length_and_vocabulary() -> None:
    words = "you should not do that at all"
    shuffled = shuffled_control([_utt("s:1", words, None)], seed=11)
    assert len(shuffled) == 1
    assert shuffled[0].text is not None
    assert sorted(shuffled[0].text.split()) == sorted(words.split())


def _binary_result(labels: dict[str, str]) -> DetectorResult:
    """A synthetic result from a detector that can only emit OBJ or UNCL."""
    return DetectorResult(
        detector_name="synthetic_binary",
        detector_version="0.0",
        labels=tuple(
            CodedLabel(uid, code, None, ("SYN",)) for uid, code in labels.items()
        ),
        label_space=("OBJ", "UNCL"),
    )


def test_code_outside_label_space_has_null_metrics_not_zero(tmp_path: Path) -> None:
    """A detector that cannot emit REF has no REF recall; 0.0 would be invented."""
    control = [_utt("s:1", "x", "REF"), _utt("s:2", "y", "OBJ")]
    result = _binary_result({"s:1": "UNCL", "s:2": "OBJ"})
    record = validate_from_result(result, control, "sha256:aaa", "syn", ["OBJ", "REF"])
    ref = record.scores["REF"]
    assert ref.status == "outside_detector_label_space"
    assert ref.support == 1
    assert ref.recall is None
    assert ref.recall_ci95 is None
    assert ref.precision is None
    assert ref.f1 is None
    assert record.scores["OBJ"].recall == 1.0
    write_validation(record, tmp_path)
    loaded = load_validations(tmp_path)[("synthetic_binary", "0.0", "sha256:aaa")]
    assert loaded.scores["REF"].recall is None
    assert loaded.scores["REF"].recall_ci95 is None


def test_validate_applies_the_same_label_space_rule() -> None:
    """TreeCoder cannot emit REVERT; a supported REVERT gold label gets nulls."""
    control = [_utt("s:1", "you should not do that", "REVERT")]
    record = validate(TreeCoder(), control, "sha256:aaa", "synthetic", ["REVERT"])
    score = record.scores["REVERT"]
    assert score.status == "outside_detector_label_space"
    assert score.recall is None
    assert score.recall_ci95 is None


def test_no_support_status_is_kept_when_both_statuses_apply() -> None:
    control = [_utt("s:1", "please confirm the hash", "SHARE")]
    record = validate(TreeCoder(), control, "sha256:aaa", "synthetic", ["REVERT"])
    assert record.scores["REVERT"].status == "no_support_in_control"
    assert record.scores["REVERT"].recall is None
