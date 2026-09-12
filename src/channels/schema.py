"""The one normalised record every loader produces and every analysis consumes.

This module is a leaf. It imports nothing from `loaders/`, `tree.py` or `detect.py`,
and it must stay that way: the schema's stability is what lets a new corpus be added
without touching analysis code. Corpus-specific fields live in `corpus_meta` and
never graduate to the top level.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Channel(str, Enum):
    """Which observable channel an utterance came through.

    The distinction that matters for this project is between channels an external
    evaluator can read by default (visible output, tool calls) and channels that
    exist only if the model chose to emit them and the API chose to expose them
    (reasoning), plus channels that may carry no human oversight at all
    (inter-agent messages).
    """

    REASONING = "reasoning"
    VISIBLE_OUTPUT = "visible_output"
    TOOL_CALL = "tool_call"
    INTER_AGENT_MESSAGE = "inter_agent_message"
    HUMAN_MESSAGE = "human_message"
    SYSTEM_MESSAGE = "system_message"
    EVENT = "event"


class Provenance(str, Enum):
    """How close the recorded text is to what the agent actually emitted.

    Anything other than VERBATIM or REDACTED_PARTIAL has passed through a human or
    a model between the agent and us, and is therefore evidence about the
    intermediary as much as about the agent.
    """

    VERBATIM = "verbatim"
    REDACTED_PARTIAL = "redacted_partial"
    PARAPHRASE = "paraphrase"
    INVESTIGATOR_SUMMARY = "investigator_summary"
    INVESTIGATOR_TEXT = "investigator_text"
    UNCERTAIN_MEANING = "uncertain_meaning"
    SYNTHETIC = "synthetic"


class ReasoningState(str, Enum):
    """How much of an assistant turn's reasoning an external observer can read."""

    RAW_PRESENT = "raw_present"
    SUMMARY_ONLY = "summary_only"
    REDACTED = "redacted"
    ABSENT = "absent"


@dataclass(frozen=True)
class Utterance:
    """One observable unit: a message, a reasoning block, an action or an event."""

    uid: str                       # stable, f"{corpus}:{local_id}"
    corpus: str
    channel: Channel
    provenance: Provenance
    text: str | None               # None when withheld; still counted as uninspectable
    actor: str | None              # required for clustering; None must raise there
    addressee: str | None = None
    thread_id: str | None = None
    timestamp: str | None = None   # ISO 8601 UTC
    timestamp_is_reconstructed: bool = False
    seq: int | None = None         # position within thread_id, 0-based
    step_index: int | None = None  # assistant-turn index in trajectory
    model: str | None = None
    task_class: str | None = None  # benchmark or task family
    reasoning_state: ReasoningState | None = None
    reasoning_effort: str | None = None
    source_ref: str | None = None
    # NEEDS REVIEW: spec §3 writes this as a bare `dict`; mypy --strict (also a
    # spec requirement) rejects that. Parameterised as the loosest thing that
    # typechecks. Field name and semantics are unchanged.
    corpus_meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TurnObservation:
    """One assistant turn, with the reasoning state we could observe for it."""

    model: str
    task_class: str
    step_index: int
    state: ReasoningState
    reasoning_effort: str | None = None
    sample_id: str | None = None   # the cluster key; one trajectory is one cluster


@dataclass(frozen=True)
class RateWithCI:
    """A rate with its interval, its denominator, and how it was weighted.

    `weighting` is part of the value, not metadata about it: an action-weighted mean
    over step indices and an unweighted one answer different questions, and a number
    that does not say which it is cannot be checked.
    """

    rate: float | None
    ci_low: float | None
    ci_high: float | None
    n: int
    method: str
    weighting: str = "unweighted"
    n_clusters: int | None = None
    low_n: bool = False
    status: str = "ok"


@dataclass(frozen=True)
class CorpusDescription:
    """What a loader must say about its corpus before any rate may be reported."""

    name: str
    n_utterances: int
    n_actors: int
    actor_concentration: float | None
    date_range: tuple[str, str] | None
    source_hash: str
    licence: str
    caveats: tuple[str, ...]
