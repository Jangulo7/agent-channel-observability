"""Pair each assistant turn with the model call that produced it, by message id.

The provider's `reasoning_tokens` (ModelEvent.output.usage) is evidence about
whether reasoning was PRODUCED, which is a different question from whether it is
READABLE. To use it per turn, each turn needs the one call that produced it.

Pairing is by message id, not by position. Inspect gives the assistant message the
id of the call's output message, so the id names the producing call. Position does
not: the baseline vLLM logs interleave the scorer's own model calls, and the
reasoning sweep carries errored first attempts followed by the retried call that
wrote the message. Positional pairing would attribute a scorer's or a failed
attempt's token count to a turn it never produced.

Where a turn cannot be paired unambiguously - it has no id, no call carries its id,
or more than one does - its count is None and the turn is counted as unpaired.
Nothing is guessed. Counts come from `output.usage`, present on every call; the raw
`call` payload is logged only for the first few calls of a sample, so it is not read.
"""

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from channels.errors import InvalidTokenCountError


@dataclass(frozen=True)
class SamplePairing:
    """How one sample's assistant turns pair with its model calls."""

    call_for_turn: tuple[int | None, ...]  # per turn: index into the calls, or None
    tokens: tuple[int | None, ...]         # per turn: reasoning_tokens, or None
    unmatched_calls: tuple[int, ...]       # calls whose output became no turn
    ambiguous_turns: tuple[int, ...]       # turns whose id is shared: unattributable

    @property
    def unpaired_turns(self) -> tuple[int, ...]:
        """Indices of turns with no unambiguous producing call."""
        return tuple(i for i, call in enumerate(self.call_for_turn) if call is None)

    @property
    def paired_without_count(self) -> int:
        """Turns paired to a call whose usage reported no reasoning_tokens."""
        return sum(
            1 for call, tokens in zip(self.call_for_turn, self.tokens, strict=True)
            if call is not None and tokens is None
        )

    def trailing_calls(self) -> tuple[int, ...]:
        """Unmatched calls after the last paired call: the sample ended before a turn.

        With no paired call at all every unmatched call counts as trailing, because
        there is no paired call for them to sit between.
        """
        paired = [call for call in self.call_for_turn if call is not None]
        last = max(paired, default=-1)
        return tuple(index for index in self.unmatched_calls if index > last)


def assistant_turns(sample: Any) -> list[Any]:
    """The sample's assistant messages, in message order."""
    messages = getattr(sample, "messages", None) or []
    return [m for m in messages if getattr(m, "role", None) == "assistant"]


def model_calls(sample: Any) -> list[Any]:
    """The sample's ModelEvents, in event order, scorer and errored calls included."""
    events = getattr(sample, "events", None) or []
    return [e for e in events if getattr(e, "event", None) == "model"]


def output_message_id(call: Any) -> str | None:
    """The id of the message a call produced, or None when it produced no choice."""
    choices = getattr(getattr(call, "output", None), "choices", None) or []
    if not choices:
        return None
    message_id = getattr(getattr(choices[0], "message", None), "id", None)
    return str(message_id) if message_id is not None else None


def reasoning_tokens(call: Any) -> int | None:
    """The provider's reasoning_tokens for one call; None when not reported.

    Raises on a negative or non-integer count: a corrupt report is not a zero.
    """
    usage = getattr(getattr(call, "output", None), "usage", None)
    value = getattr(usage, "reasoning_tokens", None)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidTokenCountError(
            f"reasoning_tokens={value!r} on a model call; expected an integer >= 0 "
            "or None"
        )
    return value


def call_errored(call: Any) -> bool:
    """Whether a model call recorded an error (a failed attempt, often retried)."""
    return bool(getattr(call, "error", None))


def pair_turns(turns: Sequence[Any], calls: Sequence[Any]) -> SamplePairing:
    """Pair turns with calls by message id; unpairable turns get None, never a guess."""
    calls_by_id: dict[str, list[int]] = defaultdict(list)
    for index, call in enumerate(calls):
        message_id = output_message_id(call)
        if message_id is not None:
            calls_by_id[message_id].append(index)
    turn_ids = Counter(_turn_id(turn) for turn in turns)
    call_for_turn: list[int | None] = []
    ambiguous: list[int] = []
    for position, turn in enumerate(turns):
        turn_id = _turn_id(turn)
        matches = calls_by_id.get(turn_id, []) if turn_id is not None else []
        shared = turn_id is not None and (len(matches) > 1 or turn_ids[turn_id] > 1)
        if shared:
            ambiguous.append(position)
        call_for_turn.append(matches[0] if len(matches) == 1 and not shared else None)
    paired = {index for index in call_for_turn if index is not None}
    return SamplePairing(
        call_for_turn=tuple(call_for_turn),
        tokens=tuple(
            None if index is None else reasoning_tokens(calls[index])
            for index in call_for_turn
        ),
        unmatched_calls=tuple(i for i in range(len(calls)) if i not in paired),
        ambiguous_turns=tuple(ambiguous),
    )


def pair_sample(sample: Any) -> SamplePairing:
    """Pair one Inspect sample's assistant turns with its model calls."""
    return pair_turns(assistant_turns(sample), model_calls(sample))


def _turn_id(turn: Any) -> str | None:
    """A turn's message id as a string, or None when it has none."""
    value = getattr(turn, "id", None)
    return str(value) if value is not None else None
