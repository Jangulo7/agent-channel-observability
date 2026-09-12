"""The second instrument: offline-only, do-not-train honoured, never averaged."""

from __future__ import annotations

import pytest

from channels.detect import (
    DetectorResult,
    DoNotTrainError,
    NliDetector,
    OfflineCheckpointError,
    check_do_not_train,
    checkpoint_is_cached,
)
from channels.schema import Channel, Provenance, Utterance
from channels.tree import CodedLabel, TreeCoder

requires_checkpoint = pytest.mark.skipif(
    not checkpoint_is_cached(),
    reason="NLI checkpoint is not in the local cache; CI runs with no network",
)


def _utt(uid: str, text: str, seq: int, do_not_train: bool = False) -> Utterance:
    """A synthetic threaded utterance."""
    return Utterance(
        uid=uid,
        corpus="synthetic_fixture",
        channel=Channel.INTER_AGENT_MESSAGE,
        provenance=Provenance.VERBATIM,
        text=text,
        actor="agent_a",
        thread_id="synthetic_thread",
        seq=seq,
        corpus_meta={"do_not_train": True} if do_not_train else {},
    )


def test_offline_refusal_is_the_tested_path() -> None:
    """A checkpoint that is not cached must raise, never download mid-analysis."""
    detector = NliDetector(checkpoint="not-a-real-org/not-a-real-checkpoint")
    with pytest.raises(OfflineCheckpointError, match="never downloads"):
        detector.detect([_utt("s:1", "placeholder", 0), _utt("s:2", "placeholder", 1)])


def test_do_not_train_utterances_are_refused() -> None:
    """Spec §13.2. Checked before the model is even loaded."""
    utterances = [_utt("s:1", "placeholder", 0, do_not_train=True)]
    with pytest.raises(DoNotTrainError, match="do_not_train"):
        check_do_not_train(utterances)
    # And through the detector, whose checkpoint is never reached.
    with pytest.raises(DoNotTrainError):
        NliDetector(checkpoint="not-a-real-org/not-a-real-checkpoint").detect(utterances)


def test_first_utterance_in_a_thread_is_skipped_not_labelled_negative() -> None:
    """Nothing to contradict is an abstention, not a silent negative."""
    detector = NliDetector(checkpoint="not-a-real-org/not-a-real-checkpoint")
    from channels.detect import _thread_pairs

    pairs, skipped = _thread_pairs(
        [_utt("s:1", "a", 0), _utt("s:2", "b", 1), _utt("s:3", "c", 2)]
    )
    assert len(pairs) == 2
    assert skipped == ["s:1"]
    assert detector.label_space == ("OBJ", "UNCL")


def test_two_detectors_reported_separately() -> None:
    """A rate from two detectors is two records with their own recalls, never one.

    The identity travels on the result, so there is no shape in which the two
    label sets can be concatenated and averaged without discarding it.
    """
    tree = TreeCoder()
    results = [
        DetectorResult(
            detector_name=tree.name,
            detector_version=tree.version,
            labels=(
                CodedLabel("s:1", "OBJ", "normative", ("P", "C", "G0", "G1", "G4")),
            ),
            label_space=tree.label_space,
        ),
        DetectorResult(
            detector_name="nli_detector",
            detector_version="1.0",
            labels=(CodedLabel("s:1", "UNCL", None, ("NLI", "contradiction=0.100")),),
            label_space=("OBJ", "UNCL"),
        ),
    ]
    assert len({r.detector_name for r in results}) == 2
    # The two disagree on the same utterance, which is the finding, not a bug.
    assert results[0].labels[0].uid == results[1].labels[0].uid
    assert results[0].labels[0].code != results[1].labels[0].code


@requires_checkpoint
def test_nli_detector_runs_from_the_local_cache() -> None:
    """Integration-lite: only runs where the checkpoint was already fetched."""
    result = NliDetector().detect(
        [
            _utt("s:1", "We should merge this change now.", 0),
            _utt("s:2", "No, we should not merge this change.", 1),
        ]
    )
    assert result.detector_name == "nli_detector"
    assert len(result.labels) == 1
    assert result.labels[0].code == "OBJ"
    assert result.skipped == ("s:1",)
