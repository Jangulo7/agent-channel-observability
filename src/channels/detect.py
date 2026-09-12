"""The `Detector` protocol, and a second instrument with a different inductive bias.

`TreeCoder` fires on lexical cues transcribed from the codebook. `NliDetector`
fires on entailment geometry learned from a different corpus entirely. They agree
only where the signal is strong enough to survive both inductive biases.

Its purpose is NOT a better rate. It is to establish how much of the reported rate
is detector-dependent — the seed of extension B in spec §15, and the empirical
route to Jha's signal/error decomposition that `TreeCoder` addresses only by
design. **Report the two detectors' recalls side by side; never average them.**
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from channels.errors import ChannelsError
from channels.schema import Channel, Utterance
from channels.tree import CodedLabel

#: A small NLI cross-encoder. Pinned by name; the checkpoint is cached locally and
#: CI never downloads it. Any sentence-pair NLI model with a contradiction label
#: would serve; this one is chosen for size, not for score.
DEFAULT_CHECKPOINT = "cross-encoder/nli-deberta-v3-small"

#: Contradiction probability above which a pair is called an objection. Chosen a
#: priori as "more likely contradiction than not", NOT tuned against recall.
# NEEDS REVIEW: illustrative threshold. Sweeping it would make this a fitted
# instrument, which is what TreeCoder's docstring forbids for the same reason.
CONTRADICTION_THRESHOLD = 0.5


class OfflineCheckpointError(ChannelsError):
    """Raised when the NLI checkpoint is not in the local cache.

    Never falls back to downloading. CI runs without network, and a detector that
    silently reaches the internet mid-analysis is not reproducible.
    """


class DoNotTrainError(ChannelsError):
    """Raised when an utterance carrying `do_not_train` reaches a model detector."""


@runtime_checkable
class Detector(Protocol):
    """Anything that turns utterances into coded labels."""

    name: str
    version: str
    requires_validation: bool
    #: The codes this detector is capable of emitting. A code outside it scores
    #: zero for structural reasons, which is not the same as being measured at
    #: zero, and `validate_from_result` reports the difference.
    label_space: tuple[str, ...]

    def detect(self, utts: Iterable[Utterance]) -> DetectorResult: ...


@dataclass(frozen=True)
class DetectorResult:
    """What one detector produced, with the detector's identity attached.

    The identity travels with the labels so two detectors' outputs can never be
    silently merged into one rate.
    """

    detector_name: str
    detector_version: str
    labels: tuple[CodedLabel, ...]
    skipped: tuple[str, ...] = field(default_factory=tuple)
    label_space: tuple[str, ...] = field(default_factory=tuple)


def check_do_not_train(utts: Sequence[Utterance]) -> None:
    """Raise if any utterance is marked do-not-train.

    Spec §13.2. The Mythos transcript carries an explicit request; honouring it is
    not optional and the check is here rather than in a caller so it cannot be
    forgotten at a call site.
    """
    offenders = [u.uid for u in utts if u.corpus_meta.get("do_not_train")]
    if offenders:
        raise DoNotTrainError(
            f"{len(offenders)} utterance(s) carry do_not_train and must not be sent "
            f"to a model detector: {offenders[:10]}"
        )


def checkpoint_is_cached(checkpoint: str = DEFAULT_CHECKPOINT) -> bool:
    """Whether the checkpoint is already in the local HuggingFace cache."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        return False
    try:
        snapshot_download(checkpoint, local_files_only=True)
    except Exception:
        return False
    return True


class NliDetector:
    """Scores contradiction between paired claims drawn from the same thread.

    Rung 1 only: validated on WikiTactics as a second instrument with a different
    inductive bias. It is deliberately NOT run on collusion_wiki, whose protocol
    strings are nothing like the human prose this checkpoint was trained on.
    """

    name = "nli_detector"
    version = "1.0"
    requires_validation = True
    #: This detector is binary: a pair either reads as a contradiction or it does
    #: not. It cannot express REF, ESC, WARN, NORM, SELF_LICENSE or SHARE, so its
    #: recall on those is undefined by construction, never a measured zero.
    label_space = ("OBJ", "UNCL")

    def __init__(
        self,
        checkpoint: str = DEFAULT_CHECKPOINT,
        threshold: float = CONTRADICTION_THRESHOLD,
        cache_dir: Path | None = None,
    ) -> None:
        self.checkpoint = checkpoint
        self.threshold = threshold
        self.cache_dir = cache_dir
        self._pipeline: Any | None = None

    def _load(self) -> Any:
        """Load the checkpoint from the local cache, or raise. Never downloads."""
        if self._pipeline is not None:
            return self._pipeline
        if not checkpoint_is_cached(self.checkpoint):
            raise OfflineCheckpointError(
                f"NLI checkpoint {self.checkpoint!r} is not in the local cache and "
                "this detector never downloads. Fetch it once with "
                f"`huggingface-cli download {self.checkpoint}`, then re-run."
            )
        from transformers import pipeline

        self._pipeline = pipeline(
            "text-classification",
            model=self.checkpoint,
            top_k=None,
            local_files_only=True,
        )
        return self._pipeline

    def detect(self, utts: Iterable[Utterance]) -> DetectorResult:
        """Label each utterance OBJ or UNCL by contradiction against its predecessor.

        An utterance with no predecessor in its thread has nothing to contradict
        and is skipped rather than labelled, so it never enters a denominator as
        a silent negative.
        """
        utterances = list(utts)
        check_do_not_train(utterances)
        classifier = self._load()

        pairs, skipped = _thread_pairs(utterances)
        labels: list[CodedLabel] = []
        for previous, current in pairs:
            score = self._contradiction_score(classifier, previous.text, current.text)
            code = "OBJ" if score >= self.threshold else "UNCL"
            labels.append(
                CodedLabel(
                    uid=current.uid,
                    code=code,
                    type="normative" if code == "OBJ" else None,
                    gate_path=("NLI", f"contradiction={score:.3f}"),
                )
            )
        return DetectorResult(
            detector_name=self.name,
            detector_version=self.version,
            labels=tuple(labels),
            skipped=tuple(skipped),
            label_space=self.label_space,
        )

    def _contradiction_score(
        self, classifier: Any, premise: str | None, hypothesis: str | None
    ) -> float:
        """Return P(contradiction) for one premise/hypothesis pair."""
        if not premise or not hypothesis:
            return 0.0
        scored = classifier({"text": premise, "text_pair": hypothesis})
        rows = scored[0] if isinstance(scored[0], list) else scored
        for row in rows:
            if str(row["label"]).lower().startswith("contradiction"):
                return float(row["score"])
        return 0.0


def _thread_pairs(
    utterances: Sequence[Utterance],
) -> tuple[list[tuple[Utterance, Utterance]], list[str]]:
    """Pair each utterance with its predecessor in the same thread.

    Returns the pairs and the uids that had no predecessor, so the skipped set is
    reported rather than absorbed.
    """
    by_thread: dict[str, list[Utterance]] = {}
    skipped: list[str] = []
    for utt in utterances:
        if utt.thread_id is None:
            skipped.append(utt.uid)
            continue
        by_thread.setdefault(utt.thread_id, []).append(utt)

    pairs: list[tuple[Utterance, Utterance]] = []
    for thread in by_thread.values():
        ordered = sorted(thread, key=lambda u: (u.seq if u.seq is not None else 0))
        if ordered:
            skipped.append(ordered[0].uid)
        pairs.extend(itertools.pairwise(ordered))
    return pairs, skipped


class RevertDetector:
    """Scores REVERT from structure, never from text.

    A revert is an act, not an utterance: the evidence is that a revision
    restored a body another agent had replaced. The loader computes that by
    checksum matching and records it on `corpus_meta["is_revert"]`; this detector
    only reads it. Keeping it a detector rather than a loader field means it goes
    through `require_validation` like any other instrument.

    **Its recall is not measurable on any control this project holds.** No corpus
    here carries human revert labels, so `validate` will report `REVERT` support
    of zero and status `no_support_in_control`. That is the honest state: the
    detector is deterministic given the definition, but the definition's own
    coverage — checksum matching finds ~94% of reverts and misses every partial
    revert — is inherited from the literature, not measured here.
    """

    name = "revert_detector"
    version = "1.0"
    requires_validation = True
    #: Structural only. It cannot express any verbal code, and a verbal detector
    #: cannot express this one, so the two are never compared or averaged.
    label_space = ("REVERT", "UNCL")

    def detect(self, utts: Iterable[Utterance]) -> DetectorResult:
        """Label artefact edits REVERT or UNCL; skip everything else.

        Messages are skipped rather than labelled UNCL: a change summary is not a
        failed revert, it is a different channel, and putting it in the
        denominator would understate the revert rate.
        """
        labels: list[CodedLabel] = []
        skipped: list[str] = []
        for utt in utts:
            if utt.channel is not Channel.ARTEFACT_EDIT:
                skipped.append(utt.uid)
                continue
            is_revert = bool(utt.corpus_meta.get("is_revert"))
            labels.append(
                CodedLabel(
                    uid=utt.uid,
                    code="REVERT" if is_revert else "UNCL",
                    type="normative" if is_revert else None,
                    gate_path=("STRUCTURAL", "body_sha256_restored_cross_actor"),
                )
            )
        return DetectorResult(
            detector_name=self.name,
            detector_version=self.version,
            labels=tuple(labels),
            skipped=tuple(skipped),
            label_space=self.label_space,
        )
