"""Four-state classification of how much of an assistant turn's reasoning is readable.

The unit is the **turn**, not the reasoning block. A turn may carry several blocks and
they may disagree — one raw, one redacted — and something has to decide what the turn
as a whole was. This module takes the strongest limitation present, so that turn is
REDACTED rather than RAW_PRESENT.

That is a judgement call, and it is deliberately the conservative one: the question
this project asks is whether an external evaluator could reconstruct why the agent
acted, and a turn with a hole in it does not support that reconstruction. Reporting it
as raw would let a partially withheld turn count as evidence of monitorability.
"""

from collections.abc import Iterable, Sequence
from typing import Any

from channels.schema import ReasoningState, TurnObservation

# Strongest limitation first. `classify_turn` takes the first state present in this
# order, which is what makes a mixed turn conservative rather than optimistic.
_SEVERITY: tuple[ReasoningState, ...] = (
    ReasoningState.REDACTED,
    ReasoningState.SUMMARY_ONLY,
    ReasoningState.RAW_PRESENT,
    ReasoningState.ABSENT,
)


def classify_reasoning(block: Any) -> ReasoningState:
    """Return the observable state of one Inspect ContentReasoning block.

    Order matters: a redacted block may still carry a summary, and we record the
    stronger limitation. See Inspect's ContentReasoning fields (reasoning, summary,
    signature, redacted). A reasoning or summary string that is blank after stripping
    carries nothing an evaluator could read, so it counts as empty.
    """
    if getattr(block, "redacted", False):
        return ReasoningState.REDACTED
    if _has_text(getattr(block, "reasoning", None)):
        return ReasoningState.RAW_PRESENT
    if _has_text(getattr(block, "summary", None)):
        return ReasoningState.SUMMARY_ONLY
    return ReasoningState.ABSENT


def _has_text(value: Any) -> bool:
    """Return whether a reasoning or summary field holds any non-whitespace text.

    A bare truthiness test would call "\\n\\n" readable reasoning: providers emit
    whitespace-only blocks when they reasoned but disclosed nothing, and scoring those
    RAW_PRESENT would count an empty channel as evidence of monitorability.
    """
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def classify_turn(states: Sequence[ReasoningState]) -> ReasoningState:
    """Collapse one turn's block states into the turn's state, worst limitation wins.

    An empty sequence means the turn carried no reasoning block at all, which is
    ABSENT: the API exposed nothing, and that is a measurement, not a gap.
    """
    if not states:
        return ReasoningState.ABSENT
    present = set(states)
    for candidate in _SEVERITY:
        if candidate in present:
            return candidate
    return ReasoningState.ABSENT


def reasoning_blocks(message: Any) -> list[Any]:
    """Return the ContentReasoning blocks carried by one assistant message.

    Inspect stores message content either as a plain string or as a list of content
    blocks. Only the list form can carry reasoning, so the string form yields none.
    """
    content = getattr(message, "content", None)
    if not isinstance(content, list):
        return []
    return [block for block in content if getattr(block, "type", None) == "reasoning"]


def trajectory_id(sample: Any) -> str:
    """Return the cluster key for one trajectory: the sample id, qualified by epoch.

    Inspect reuses a sample's id across epochs, so a bare id would merge repeated
    runs of the same task into one cluster and understate the number of
    trajectories. Epoch 1 keeps the bare id so single-epoch records are unchanged.
    """
    sample_id = str(getattr(sample, "id", "unknown"))
    epoch = getattr(sample, "epoch", None)
    if epoch is None or epoch == 1:
        return sample_id
    return f"{sample_id}#epoch{epoch}"


def observe_turns(
    sample: Any,
    model: str,
    task_class: str,
    reasoning_effort: str | None = None,
) -> list[TurnObservation]:
    """Classify every assistant turn in one Inspect sample.

    `step_index` is the 0-based index of the assistant turn within the sample's
    message sequence, counting assistant turns only. Non-assistant messages do not
    advance it, so step 3 means "the agent's fourth move", which is the quantity the
    positional profile is about.
    """
    observations: list[TurnObservation] = []
    sample_id = trajectory_id(sample)
    step_index = 0
    for message in getattr(sample, "messages", []) or []:
        if getattr(message, "role", None) != "assistant":
            continue
        observations.append(
            TurnObservation(
                model=model,
                task_class=task_class,
                step_index=step_index,
                state=_state_for_message(message),
                reasoning_effort=reasoning_effort,
                sample_id=sample_id,
            )
        )
        step_index += 1
    return observations


def state_counts(
    observations: Iterable[TurnObservation],
) -> dict[ReasoningState, int]:
    """Count observations per state, with every state present even when zero.

    Zeroes are kept because a state that never occurred is a finding; dropping it
    would make the four-state distribution unreadable without the raw data.
    """
    counts = dict.fromkeys(ReasoningState, 0)
    for observation in observations:
        counts[observation.state] += 1
    return counts


def _state_for_message(message: Any) -> ReasoningState:
    """Classify one assistant message, preferring block evidence over the attribute.

    Inspect 0.3.260's `ChatMessageAssistant` has no `reasoning` attribute — the spec
    asks us to read one, so this reads it defensively via `getattr` for forward
    compatibility and falls back to the content blocks, which is where 0.3.260
    actually puts it.
    """
    blocks = reasoning_blocks(message)
    if blocks:
        return classify_turn([classify_reasoning(block) for block in blocks])
    # NEEDS REVIEW: spec §9.1 says to read `ChatMessageAssistant.reasoning`; that
    # field does not exist in the pinned inspect-ai 0.3.260. Read defensively.
    attribute = getattr(message, "reasoning", None)
    if _has_text(attribute):
        return ReasoningState.RAW_PRESENT
    return ReasoningState.ABSENT
