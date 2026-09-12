"""Human annotation: drawing samples, storing labels, measuring agreement.

Three properties make these labels usable as a gold standard, and each is
enforced here rather than left to the coder's discipline:

* **Blind.** Nothing in this module can surface a detector's prediction. A coder
  who has seen `TreeCoder`'s answer is no longer an independent measurement of
  the thing `TreeCoder` is being validated against.
* **Deterministic.** A sample is a pure function of (population, task, n, seed),
  so a second coder receives exactly the same items and Cohen's kappa is
  computed on matched pairs rather than on two different samples.
* **Text-free output.** A saved record holds uids and codes, never corpus text,
  so `results/annotations/` is publishable under a corpus with no licence.
"""

from __future__ import annotations

import json
import random
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from channels.schema import Utterance

ANNOTATION_DIR = Path(__file__).resolve().parents[2] / "results" / "annotations"


@dataclass(frozen=True)
class AnnotationTask:
    """One coding job: which population, which question, which allowed answers."""

    name: str
    question: str
    choices: dict[str, str]

    def choice_keys(self) -> tuple[str, ...]:
        """Single-key answers the coder may give, in display order."""
        return tuple(self.choices)


#: Is a checksum-detected revert actually disagreement, or housekeeping? This is
#: the only calibration REVERT will ever have: no public corpus carries human
#: revert-intent labels, so there is nothing else to validate it against.
REVERT_VALIDITY = AnnotationTask(
    name="revert_validity",
    question="Does this revert REJECT the other agent's contribution?",
    choices={
        "d": "disagreement - rejects the other agent's content or approach",
        "h": "housekeeping - cleanup, spam or vandalism removal, formatting",
        "u": "unclear from what is shown",
    },
)

#: Does the message channel carry verbal objection at all? TreeCoder screened
#: 12,773 summaries and predicted zero OBJ, but that screen is unvalidated on
#: this corpus, so it supports neither a rate nor a bound until a human checks.
MESSAGE_CODE = AnnotationTask(
    name="message_code",
    question="Which codebook code fits this message?",
    choices={
        "o": "OBJ - says a peer's action is wrong or impermissible",
        "r": "REF - declines a peer's request",
        "e": "ESC - reports or threatens to report a peer to a third party",
        "w": "WARN - warns a peer of consequences",
        "n": "NORM - cites a rule or policy without objecting",
        "l": "SELF_LICENSE - justifies a peer's norm-violating action",
        "s": "SHARE - coordination: request, answer, status, offer",
        "u": "UNCL - inter-agent but intent undeterminable",
    },
)

TASKS: dict[str, AnnotationTask] = {
    REVERT_VALIDITY.name: REVERT_VALIDITY,
    MESSAGE_CODE.name: MESSAGE_CODE,
}


@dataclass(frozen=True)
class Label:
    """One coding decision. Carries no corpus text."""

    uid: str
    choice: str
    seconds: float
    utc: str


@dataclass
class AnnotationRecord:
    """Every label one coder gave on one sample, with the instrument version."""

    sample_id: str
    task: str
    codebook_hash: str
    coder_id: str
    n_requested: int
    seed: int
    labels: list[Label] = field(default_factory=list)
    started_utc: str = field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    @property
    def coded_uids(self) -> set[str]:
        """Uids already coded, so a stopped session resumes where it left off."""
        return {label.uid for label in self.labels}

    def path(self, directory: Path = ANNOTATION_DIR) -> Path:
        """Where this record is stored."""
        return directory / f"{self.sample_id}__{self.coder_id}.json"

    def save(self, directory: Path = ANNOTATION_DIR) -> Path:
        """Write the record, creating the directory if needed."""
        directory.mkdir(parents=True, exist_ok=True)
        target = self.path(directory)
        target.write_text(
            json.dumps(asdict(self), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return target


def sample_id_for(task: AnnotationTask, n: int, seed: int) -> str:
    """Stable identifier for a sample, so two coders provably share one."""
    return f"{task.name}_n{n}_seed{seed}"


def draw_sample(
    population: Sequence[Utterance], task: AnnotationTask, n: int, seed: int
) -> list[Utterance]:
    """Draw a reproducible random sample, sorted by uid before shuffling.

    Sorting first matters: the population arrives in file order, and two runs
    that read the corpus differently would otherwise shuffle different lists
    from the same seed and silently hand two coders different items.
    """
    if n <= 0:
        raise ValueError(f"n={n}: sample size must be positive")
    ordered = sorted(population, key=lambda utt: utt.uid)
    if n > len(ordered):
        raise ValueError(
            f"n={n} exceeds the population of {len(ordered)}; "
            "a sample cannot be larger than what it is drawn from"
        )
    rng = random.Random(seed)
    return rng.sample(ordered, n)


def load_record(path: Path) -> AnnotationRecord:
    """Load a saved record, restoring its labels."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    record = AnnotationRecord(
        sample_id=raw["sample_id"],
        task=raw["task"],
        codebook_hash=raw["codebook_hash"],
        coder_id=raw["coder_id"],
        n_requested=raw["n_requested"],
        seed=raw["seed"],
        started_utc=raw["started_utc"],
    )
    record.labels = [Label(**entry) for entry in raw["labels"]]
    return record


def cohens_kappa(
    first: Mapping[str, str], second: Mapping[str, str]
) -> tuple[float, int]:
    """Cohen's kappa on the items both coders labelled, with that item count.

    Returns (kappa, n_overlap). Kappa corrects observed agreement for the
    agreement two coders would reach by chance given their marginal frequencies,
    which raw percent-agreement does not: on a task where 90% of items take one
    code, two coders who always guess that code agree 90% of the time and have
    demonstrated nothing.
    """
    shared = sorted(set(first) & set(second))
    n = len(shared)
    if n == 0:
        raise ValueError("the two coders share no labelled items")
    agreed = sum(1 for uid in shared if first[uid] == second[uid])
    observed = agreed / n

    categories = {first[uid] for uid in shared} | {second[uid] for uid in shared}
    expected = 0.0
    for category in categories:
        p_first = sum(1 for uid in shared if first[uid] == category) / n
        p_second = sum(1 for uid in shared if second[uid] == category) / n
        expected += p_first * p_second
    if expected >= 1.0:
        # Both coders used exactly one category. Agreement is total but chance
        # agreement is also total, so kappa is undefined rather than perfect.
        return float("nan"), n
    return (observed - expected) / (1.0 - expected), n
