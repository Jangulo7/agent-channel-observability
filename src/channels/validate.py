"""The gatekeeper: no detector reports a rate without a recorded, validated recall.

This is one of the two architectural rules in spec §0. `require_validation` raises,
and it is meant to. A rate from an uncalibrated instrument is not a weak measurement,
it is an unknown one, and a paper whose thesis is that unvalidated measurements
should not be trusted cannot ship one.
"""

from __future__ import annotations

import json
import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from channels._vendored_stats import wilson_interval
from channels.errors import UnvalidatedDetectorError
from channels.schema import Utterance

VALIDATION_DIR = Path(__file__).resolve().parents[2] / "results" / "validation"


@dataclass(frozen=True)
class CodeScore:
    """Recall, precision and F1 for one code, with the counts behind them."""

    code: str
    support: int
    predicted: int
    true_positives: int
    recall: float | None
    recall_ci95: tuple[float, float] | None
    precision: float | None
    f1: float | None
    status: str = "measured"


@dataclass(frozen=True)
class ValidationRecord:
    """What a detector scored against a labelled control, and against which codebook."""

    detector_name: str
    detector_version: str
    codebook_hash: str
    control_corpus: str
    n_utterances: int
    scores: dict[str, CodeScore]
    n_skipped: int = 0
    generated_utc: str = field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    @property
    def key(self) -> tuple[str, str, str]:
        """The identity a validation record is looked up by."""
        return (self.detector_name, self.detector_version, self.codebook_hash)


def _score_one_code(
    code: str, gold: Sequence[str | None], predicted: Sequence[str]
) -> CodeScore:
    """Score one code. Support of zero means undefined recall, never zero recall."""
    support = sum(1 for g in gold if g == code)
    n_predicted = sum(1 for p in predicted if p == code)
    true_positives = sum(1 for g, p in zip(gold, predicted, strict=True)
                         if g == code and p == code)
    if support == 0:
        # The control carries no instance of this code, so recall is not defined.
        # Reporting 0.0 here would invent a measurement out of an absent one.
        return CodeScore(code, 0, n_predicted, 0, None, None, None, None,
                         status="no_support_in_control")
    interval = wilson_interval(true_positives, support)
    recall = true_positives / support
    precision = true_positives / n_predicted if n_predicted else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and (precision + recall) > 0
        else None
    )
    return CodeScore(
        code=code,
        support=support,
        predicted=n_predicted,
        true_positives=true_positives,
        recall=recall,
        recall_ci95=(interval.low, interval.high),
        precision=precision,
        f1=f1,
    )


def validate(
    detector: object,
    control: Iterable[Utterance],
    codebook_hash: str,
    control_name: str,
    codes: Sequence[str],
) -> ValidationRecord:
    """Recall, precision and F1 per code against a labelled control.

    The control's gold label lives in `corpus_meta["gold_code"]`, put there by a
    committed mapping table rather than inferred at runtime.
    """
    utterances = list(control)
    gold = [u.corpus_meta.get("gold_code") for u in utterances]
    predicted = [detector.code(u).code for u in utterances]  # type: ignore[attr-defined]
    return ValidationRecord(
        detector_name=getattr(detector, "name", type(detector).__name__),
        detector_version=getattr(detector, "version", "unknown"),
        codebook_hash=codebook_hash,
        control_corpus=control_name,
        n_utterances=len(utterances),
        scores={code: _score_one_code(code, gold, predicted) for code in codes},
    )


def validate_from_result(
    result: object,
    control: Iterable[Utterance],
    codebook_hash: str,
    control_name: str,
    codes: Sequence[str],
) -> ValidationRecord:
    """Score a DetectorResult against a labelled control, aligning on uid.

    Utterances the detector declined to label are excluded from the denominator
    AND counted in `n_skipped`. A detector that abstains on an item has not got
    it wrong, but it has not got it right either, and burying abstentions in the
    denominator would flatter or punish it arbitrarily. The count is reported so
    a reader can recompute either way.
    """
    labels = {label.uid: label.code for label in result.labels}  # type: ignore[attr-defined]
    gold: list[str | None] = []
    predicted: list[str] = []
    n_skipped = 0
    for utt in control:
        if utt.uid not in labels:
            n_skipped += 1
            continue
        gold.append(utt.corpus_meta.get("gold_code"))
        predicted.append(labels[utt.uid])
    label_space = set(getattr(result, "label_space", ()) or codes)
    scores: dict[str, CodeScore] = {}
    for code in codes:
        score = _score_one_code(code, gold, predicted)
        if code not in label_space:
            # The detector cannot emit this code at all. Its zero is a property of
            # the instrument, not a measurement of the corpus.
            score = replace(score, status="outside_detector_label_space")
        scores[code] = score
    return ValidationRecord(
        detector_name=result.detector_name,  # type: ignore[attr-defined]
        detector_version=result.detector_version,  # type: ignore[attr-defined]
        codebook_hash=codebook_hash,
        control_corpus=control_name,
        n_utterances=len(gold),
        scores=scores,
        n_skipped=n_skipped,
    )


def write_validation(
    record: ValidationRecord, directory: Path = VALIDATION_DIR
) -> Path:
    """Persist a validation record under results/validation/ and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{record.detector_name}_{record.detector_version}_{record.control_corpus}"
    path = directory / f"{name}.json"
    path.write_text(json.dumps(asdict(record), indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return path


ValidationKey = tuple[str, str, str]


def load_validations(
    directory: Path = VALIDATION_DIR,
) -> dict[ValidationKey, ValidationRecord]:
    """Load every persisted validation record, keyed by detector and codebook hash."""
    records: dict[ValidationKey, ValidationRecord] = {}
    if not directory.is_dir():
        return records
    for path in sorted(directory.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        scores = {
            code: _code_score_from_json(entry)
            for code, entry in raw["scores"].items()
        }
        record = ValidationRecord(
            detector_name=raw["detector_name"],
            detector_version=raw["detector_version"],
            codebook_hash=raw["codebook_hash"],
            control_corpus=raw["control_corpus"],
            n_utterances=raw["n_utterances"],
            scores=scores,
            n_skipped=raw.get("n_skipped", 0),
            generated_utc=raw["generated_utc"],
        )
        records[record.key] = record
    return records


def _code_score_from_json(entry: Mapping[str, Any]) -> CodeScore:
    """Rebuild a CodeScore, restoring the CI tuple that JSON stored as a list."""
    interval = entry.get("recall_ci95")
    return CodeScore(
        code=str(entry["code"]),
        support=int(entry["support"]),
        predicted=int(entry["predicted"]),
        true_positives=int(entry["true_positives"]),
        recall=entry["recall"],
        recall_ci95=(float(interval[0]), float(interval[1])) if interval else None,
        precision=entry["precision"],
        f1=entry["f1"],
        status=str(entry.get("status", "measured")),
    )


def require_validation(
    detector: object, codebook_hash: str, directory: Path = VALIDATION_DIR
) -> ValidationRecord:
    """Return the validation record for this detector, or raise.

    Keyed on (name, version, codebook hash) together: a detector validated against
    an older codebook has not been validated against this one, and silently reusing
    that record is how a rate outlives the instrument that earned it.
    """
    name = getattr(detector, "name", type(detector).__name__)
    version = getattr(detector, "version", "unknown")
    key = (name, version, codebook_hash)
    records = load_validations(directory)
    if key not in records:
        raise UnvalidatedDetectorError(
            f"detector {name} v{version} has no validation record for codebook "
            f"{codebook_hash}. Records available: {sorted(records)}. "
            "No rate may be reported until one exists."
        )
    return records[key]


def shuffled_control(utts: Iterable[Utterance], seed: int) -> list[Utterance]:
    """Token-shuffle within each message, preserving length and vocabulary.

    Rung 2 compares the detector's rate on real agent text against its rate on
    this control. A rate not materially above the control means the detector is
    firing on surface features, not on content.
    """
    rng = random.Random(seed)
    shuffled: list[Utterance] = []
    from dataclasses import replace

    for utt in utts:
        if not utt.text:
            shuffled.append(utt)
            continue
        tokens = utt.text.split()
        rng.shuffle(tokens)
        shuffled.append(replace(utt, text=" ".join(tokens)))
    return shuffled
