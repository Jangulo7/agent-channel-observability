"""The one normalised record every loader produces and every analysis consumes.

This module is a leaf. It imports nothing from `loaders/`, `tree.py` or `detect.py`
(only `errors.py`, itself a leaf), and it must stay that way: the schema's stability
is what lets a new corpus be added without touching analysis code. Corpus-specific
fields live in `corpus_meta` and never graduate to the top level.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from channels.errors import InvalidTokenCountError


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
    # An edit to a shared artefact (a wiki revision, a file write). NOT a message:
    # it is addressed to no one and carries no illocutionary force of its own, but
    # it is observable to peers and can express disagreement by action - a revert
    # undoes a peer's edit without saying anything. Added 2026-09-12 because
    # coding wiki revisions as INTER_AGENT_MESSAGE conflated two different
    # communicative acts and inflated the inter-agent message denominator.
    ARTEFACT_EDIT = "artefact_edit"
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


class DeliberationEvidence(str, Enum):
    """Whether the evidence says reasoning was PRODUCED on a turn.

    Readable is not produced. `ReasoningState` records what an external evaluator
    can READ; this records whether reasoning was GENERATED. The two come apart: a
    turn is ABSENT both when nothing was produced (reasoning_tokens == 0) and when
    reasoning was produced and not returned (reasoning_tokens > 0), while a REDACTED
    turn was produced and withheld. Collapsing them lets "absent" read as "hidden".

    Evidence hierarchy (author decision, 2026-09-13): returned reasoning content -
    readable or summary - is direct evidence and makes a turn PRODUCED whatever the
    provider's count says, because one upstream has been seen returning readable
    reasoning with reasoning_tokens == 0. A REDACTED turn is PRODUCED only when the
    provider reported a count (an encrypted chain); with no count it is UNKNOWN,
    because a publisher's redaction marker is not evidence that reasoning existed.
    A turn with no reasoning content falls back to the count: > 0 PRODUCED, == 0
    NOT_PRODUCED, None UNKNOWN.
    """

    PRODUCED = "produced"          # reasoning content returned, or tokens > 0
    NOT_PRODUCED = "not_produced"  # no reasoning content and an explicit 0 tokens
    UNKNOWN = "unknown"            # no reasoning content and no count (or no pairing)


@dataclass(frozen=True)
class TurnObservation:
    """One assistant turn, with the reasoning state we could observe for it."""

    model: str
    task_class: str
    step_index: int
    state: ReasoningState
    reasoning_effort: str | None = None
    sample_id: str | None = None   # the cluster key; one trajectory is one cluster
    # The provider's reasoning_tokens for the call that produced this turn. None means
    # not reported or not attributable to one call, never zero: a missing count is
    # not evidence that nothing was produced.
    provider_reasoning_tokens: int | None = None

    @property
    def deliberation_evidence(self) -> DeliberationEvidence:
        """This turn's deliberation evidence; see `deliberation_evidence`."""
        return deliberation_evidence(self)

    @property
    def token_accounting_inconsistent(self) -> bool:
        """Content returned with 0 reported tokens; see the module-level function."""
        return token_accounting_inconsistent(self)


def deliberation_evidence(observation: TurnObservation) -> DeliberationEvidence:
    """Classify a turn by the evidence hierarchy: returned content, then tokens."""
    tokens = _checked_tokens(observation)
    if observation.state in (ReasoningState.RAW_PRESENT, ReasoningState.SUMMARY_ONLY):
        return DeliberationEvidence.PRODUCED
    if observation.state is ReasoningState.REDACTED:
        # A redaction marker shows content was withheld, not that it was reasoning.
        # With a provider count it is a provider's encrypted chain (PRODUCED); with
        # no count it may be a publisher's whole-message redaction (the Mythos
        # export), which is no evidence that reasoning existed.
        # NEEDS REVIEW: decided 2026-09-13; REDACTED without a count is UNKNOWN.
        return (
            DeliberationEvidence.UNKNOWN if tokens is None
            else DeliberationEvidence.PRODUCED
        )
    if tokens is None:
        return DeliberationEvidence.UNKNOWN
    if tokens == 0:
        return DeliberationEvidence.NOT_PRODUCED
    return DeliberationEvidence.PRODUCED


def token_accounting_inconsistent(observation: TurnObservation) -> bool:
    """Whether reasoning content was returned while the provider reported 0 tokens.

    Such a turn is still PRODUCED (the content is the direct evidence); this flag
    exists so the override is counted and surfaced, never applied silently.
    """
    tokens = _checked_tokens(observation)
    return tokens == 0 and observation.state is not ReasoningState.ABSENT


def _checked_tokens(observation: TurnObservation) -> int | None:
    """The turn's provider reasoning_tokens, raising on a negative count."""
    tokens = observation.provider_reasoning_tokens
    if tokens is not None and tokens < 0:
        # A negative count is a corrupt report, not a smaller zero; classifying it
        # either way would invent evidence.
        raise InvalidTokenCountError(
            f"provider_reasoning_tokens={tokens} on {observation.model}/"
            f"{observation.task_class} step {observation.step_index}; expected an "
            "integer >= 0 or None"
        )
    return tokens


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
