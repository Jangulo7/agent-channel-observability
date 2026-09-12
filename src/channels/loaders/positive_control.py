"""WikiTactics as the rung-1 positive control.

De Kock, Stafford & Vlachos, "How to disagree well", EMNLP 2022.
213 conversations / 3,865 utterances of Wikipedia talk-page disagreement.

**No licence file exists in the source repository.** Reuse rests on the paper, so
this loader publishes counts and never utterance text; `describe()` reports the
licence as unstated and the publication-safety test keeps text out of `results/`.

Rung 1 is human prose. Transferring an instrument validated here to agent
protocol strings is **not** established by anything in this repository; that is
rung 2 and it is not built. See the Limitations section of the README.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from channels.errors import SchemaDiscoveryError
from channels.loaders.base import actor_concentration, file_hash
from channels.schema import Channel, CorpusDescription, Provenance, Utterance

#: Keys every conversation must carry. Reported with the keys actually seen.
REQUIRED_CONVERSATION_KEYS = ("conv_id", "utterances")
REQUIRED_UTTERANCE_KEYS = ("text", "username")

# ---------------------------------------------------------------------------
# The label -> code mapping. COMMITTED AND EXPLICIT, never inferred at runtime.
#
# Assigned a priori from each label's published definition in De Kock et al.,
# before any recall was computed. Two consequences are deliberate:
#
#   * The Graham-hierarchy rebuttal labels DH4-DH7 are argument-quality levels.
#     They are disputes about whether a claim is CORRECT, which the codebook
#     routes out of scope at gate G1. They map to None, meaning "not a codebook
#     category", which is different from UNCL ("inter-agent but undetermined").
#   * ESC, WARN, NORM and SELF_LICENSE have NO WikiTactics equivalent. Recall for
#     those four codes is therefore UNDEFINED on this control, not zero. Reporting
#     it as zero would be inventing a measurement.
#
# The source data contains near-duplicate annotator spellings of the same label
# (e.g. two forms of DH1 and three of DH4). Every observed variant is listed
# explicitly so that an unmapped label raises rather than being silently dropped.
# ---------------------------------------------------------------------------
LABEL_TO_CODE: Mapping[str, str | None] = {
    # --- coordination labels: the shared-task denominator ---
    "Coordinating edits": "SHARE",
    "Contextualisation": "SHARE",
    "Providing clarification": "SHARE",
    "Asking questions": "SHARE",
    "Suggesting a compromise": "SHARE",
    "Conceding / recanting": "SHARE",
    "Other": None,
    "Other: Quote": None,
    "I don't know": None,
    # --- rebuttal labels ---
    # Policing the discussion is conduct-directed: it tells a peer that how they
    # are behaving is out of bounds. That is the codebook's OBJ.
    "DH3: Policing the discussion": "OBJ",
    # Bailing out is withdrawal from the exchange: the codebook's REF.
    "DH-1: Bailing out": "REF",
    # Hostility and ad hominem attack the person, not the conduct's permissibility.
    "DH0: Name calling/hostility": None,
    "DH1: Ad hominem/ad argument": None,
    "DH1: Attacks to the person or argument": None,
    "DH2: Attempted derailing/off-topic": None,
    "DH2: Attempted derailing / off-topic comments": None,
    # DH4-DH7 are correctness disputes; gate G1 routes them out of scope.
    "DH4: Repeated argument": None,
    "DH4: Stating your stance": None,
    "DH4: Stating your stance without evidence or reasoning": None,
    "DH5: Counterargument": None,
    "DH5: Counterargument with new evidence / reasoning": None,
    "DH6: Refutation": None,
    "DH6: Refutation of opponent's argument (with evidence or reasoning)": None,
    "DH7: Refuting the central point": None,
}

#: Codes this control can measure recall for. The other four have no equivalent.
MEASURABLE_CODES: tuple[str, ...] = ("OBJ", "REF", "SHARE")
UNMEASURABLE_CODES: tuple[str, ...] = ("ESC", "WARN", "NORM", "SELF_LICENSE")


def map_to_codebook(labels: tuple[str, ...]) -> str | None:
    """Return the codebook code for a WikiTactics utterance, or None if out of scope.

    Where an utterance carries several labels the most specific normative code
    wins, because an utterance that both coordinates and polices is an objection
    embedded in coordination and the objection is the event of interest.
    """
    mapped = []
    for label in labels:
        if label not in LABEL_TO_CODE:
            raise SchemaDiscoveryError(
                f"wikitactics: label {label!r} is not in the committed mapping. "
                f"Labels mapped: {sorted(LABEL_TO_CODE)}"
            )
        mapped.append(LABEL_TO_CODE[label])
    for code in ("OBJ", "REF"):
        if code in mapped:
            return code
    return "SHARE" if "SHARE" in mapped else None


@dataclass
class WikiTacticsLoader:
    """Loads WikiTactics conversations into utterances carrying gold codes."""

    path: Path
    name: str = "wikitactics"

    def available(self) -> bool:
        """Whether the single WikiTactics JSON file is present."""
        return self.path.is_file()

    def require_available(self) -> Path:
        """Return the path, or raise naming exactly what was checked."""
        if not self.available():
            raise SchemaDiscoveryError(
                f"wikitactics: no corpus at {self.path}. Missing data is a result; "
                "download it with the command in docs/DATA_PROVENANCE.md"
            )
        return self.path

    def _conversations(self) -> list[dict[str, Any]]:
        """Parse the file and check the schema against the keys actually present."""
        raw = json.loads(self.require_available().read_text(encoding="utf-8"))
        if not isinstance(raw, list) or not raw:
            raise SchemaDiscoveryError("wikitactics: expected a non-empty JSON list")
        observed = set(raw[0])
        missing = [key for key in REQUIRED_CONVERSATION_KEYS if key not in observed]
        if missing:
            raise SchemaDiscoveryError(
                f"wikitactics: conversation missing {missing}; "
                f"keys observed: {sorted(observed)}"
            )
        return raw

    def load(self, **kwargs: Any) -> Iterator[Utterance]:
        """Yield one Utterance per turn, with its gold code in `corpus_meta`.

        Text IS carried here because the coder needs it, but it is never written
        to `results/`: this corpus has no licence and only counts are published.
        """
        for conversation in self._conversations():
            conv_id = str(conversation["conv_id"])
            for seq, turn in enumerate(conversation["utterances"]):
                absent = [k for k in REQUIRED_UTTERANCE_KEYS if k not in turn]
                if absent:
                    raise SchemaDiscoveryError(
                        f"wikitactics: utterance missing {absent}; "
                        f"keys observed: {sorted(turn)}"
                    )
                labels = tuple(
                    (turn.get("coordination_labels") or [])
                    + (turn.get("rebuttal_labels") or [])
                )
                yield Utterance(
                    uid=f"wikitactics:{conv_id}:{seq}",
                    corpus="wikitactics",
                    channel=Channel.INTER_AGENT_MESSAGE,
                    provenance=Provenance.VERBATIM,
                    text=turn["text"],
                    actor=str(turn["username"]),
                    thread_id=conv_id,
                    seq=seq,
                    source_ref="De Kock, Stafford & Vlachos, EMNLP 2022",
                    corpus_meta={
                        "gold_code": map_to_codebook(labels),
                        "labels": list(labels),
                        "split": conversation.get("split"),
                        "escalation_label": conversation.get("escalation_label"),
                    },
                )

    def describe(self) -> CorpusDescription:
        """Counts, actor concentration and the licence caveat. No text."""
        utterances = list(self.load())
        conversations = {utt.thread_id for utt in utterances}
        return CorpusDescription(
            name=self.name,
            n_utterances=len(utterances),
            n_actors=len({utt.actor for utt in utterances}),
            actor_concentration=actor_concentration([u.actor for u in utterances]),
            date_range=None,
            source_hash=file_hash(self.path),
            licence="none stated; reuse rests on De Kock et al., EMNLP 2022",
            caveats=(
                "Human Wikipedia editors, not agents. Rung 1 only: transfer of "
                "the instrument to agent protocol strings is unvalidated.",
                "Four codebook codes (ESC, WARN, NORM, SELF_LICENSE) have no "
                "WikiTactics equivalent, so their recall is undefined here, "
                "not zero.",
                "No licence file in the source repository; counts published, "
                "utterance text withheld.",
                f"{len(conversations)} conversations; recall measurable for "
                f"{list(MEASURABLE_CODES)}, undefined for "
                f"{list(UNMEASURABLE_CODES)}.",
            ),
        )
