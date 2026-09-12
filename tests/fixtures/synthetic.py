"""Synthetic fixtures. Obviously synthetic by design — no real corpus data in tests/.

Every string here is a stand-in the reader can recognise as fake at a glance. The
project's own thesis forbids tests that could be mistaken for measurements.
"""

from dataclasses import dataclass, field
from typing import Any

from channels.schema import ReasoningState, TurnObservation


@dataclass
class FakeReasoningBlock:
    """Stands in for Inspect's ContentReasoning. Same four fields, no dependency."""

    type: str = "reasoning"
    reasoning: str | None = None
    summary: str | None = None
    signature: str | None = None
    redacted: bool = False


@dataclass
class FakeToolCall:
    """Stands in for Inspect's ToolCall."""

    id: str = "SYNTHETIC_CALL"
    function: str = "synthetic_tool"
    arguments: dict[str, Any] = field(default_factory=dict)
    parse_error: str | None = None


@dataclass
class FakeMessage:
    """Stands in for an Inspect chat message."""

    role: str
    content: Any = ""
    tool_calls: list[FakeToolCall] = field(default_factory=list)


@dataclass
class FakeSample:
    """Stands in for an Inspect EvalSample."""

    id: str
    messages: list[FakeMessage] = field(default_factory=list)
    events: list[Any] = field(default_factory=list)


def turns(
    states: list[ReasoningState],
    model: str = "SYNTHETIC-MODEL-A",
    task_class: str = "synthetic_task",
    sample_id: str = "SYNTHETIC_SAMPLE_1",
    effort: str | None = None,
) -> list[TurnObservation]:
    """Build a trajectory whose step j has states[j]; len(states) is its length."""
    return [
        TurnObservation(
            model=model,
            task_class=task_class,
            step_index=index,
            state=state,
            reasoning_effort=effort,
            sample_id=sample_id,
        )
        for index, state in enumerate(states)
    ]
