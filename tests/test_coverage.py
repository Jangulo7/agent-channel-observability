"""Four-state classification, including the mixed-turn judgement call."""

from channels.coverage import classify_reasoning, classify_turn, observe_turns
from channels.schema import ReasoningState

from .fixtures.synthetic import FakeMessage, FakeReasoningBlock, FakeSample


def test_classify_reasoning_states() -> None:
    """One case per state, plus the case the docstring warns about."""
    assert (
        classify_reasoning(FakeReasoningBlock(reasoning="SYNTHETIC CHAIN"))
        is ReasoningState.RAW_PRESENT
    )
    assert (
        classify_reasoning(FakeReasoningBlock(summary="SYNTHETIC SUMMARY"))
        is ReasoningState.SUMMARY_ONLY
    )
    assert classify_reasoning(FakeReasoningBlock()) is ReasoningState.ABSENT
    # A redacted block that also carries a summary records the stronger limitation.
    assert (
        classify_reasoning(
            FakeReasoningBlock(redacted=True, summary="SYNTHETIC SUMMARY")
        )
        is ReasoningState.REDACTED
    )


def test_mixed_turn_takes_strongest_limitation() -> None:
    """One raw block and one redacted block make the turn REDACTED, not RAW_PRESENT."""
    assert (
        classify_turn([ReasoningState.RAW_PRESENT, ReasoningState.REDACTED])
        is ReasoningState.REDACTED
    )
    assert (
        classify_turn([ReasoningState.RAW_PRESENT, ReasoningState.SUMMARY_ONLY])
        is ReasoningState.SUMMARY_ONLY
    )


def test_turn_with_no_blocks_is_absent() -> None:
    assert classify_turn([]) is ReasoningState.ABSENT


def test_step_index_counts_assistant_turns_only() -> None:
    """A user message between two assistant turns must not advance the step index."""
    sample = FakeSample(
        id="SYNTHETIC_SAMPLE_1",
        messages=[
            FakeMessage(role="system", content="SYNTHETIC SYSTEM"),
            FakeMessage(
                role="assistant",
                content=[FakeReasoningBlock(reasoning="SYNTHETIC CHAIN")],
            ),
            FakeMessage(role="user", content="SYNTHETIC USER"),
            FakeMessage(role="assistant", content="SYNTHETIC PLAIN TEXT"),
        ],
    )
    observations = observe_turns(sample, "SYNTHETIC-MODEL-A", "synthetic_task")
    assert [o.step_index for o in observations] == [0, 1]
    assert [o.state for o in observations] == [
        ReasoningState.RAW_PRESENT,
        ReasoningState.ABSENT,
    ]


def test_whitespace_only_reasoning_is_not_raw_present() -> None:
    """A block whose reasoning is blank after stripping carries nothing readable.

    Truthiness alone would score "\\n  \\n" as RAW_PRESENT and count an empty channel
    as evidence of monitorability.
    """
    assert (
        classify_reasoning(FakeReasoningBlock(reasoning="  \n\t "))
        is ReasoningState.ABSENT
    )
    assert (
        classify_reasoning(FakeReasoningBlock(summary=" \n "))
        is ReasoningState.ABSENT
    )
    # Blank reasoning beside a real summary is SUMMARY_ONLY, not RAW_PRESENT.
    assert (
        classify_reasoning(
            FakeReasoningBlock(reasoning="\n", summary="SYNTHETIC SUMMARY")
        )
        is ReasoningState.SUMMARY_ONLY
    )


def test_whitespace_only_reasoning_attribute_is_absent() -> None:
    """The attribute fallback applies the same blank-is-empty rule as the blocks."""

    class _AttributeMessage:
        role = "assistant"
        content = "SYNTHETIC PLAIN TEXT"
        reasoning = "   "

    sample = FakeSample(id="SYNTHETIC_SAMPLE_WS", messages=[_AttributeMessage()])  # type: ignore[list-item]
    observations = observe_turns(sample, "SYNTHETIC-MODEL-A", "synthetic_task")
    assert [o.state for o in observations] == [ReasoningState.ABSENT]


def test_repeated_epochs_are_separate_trajectories() -> None:
    """The same sample id in epochs 1 and 2 must yield two cluster keys, not one."""
    first = FakeSample(
        id="SYNTHETIC_SAMPLE_1",
        messages=[FakeMessage(role="assistant", content="SYNTHETIC A")],
    )
    second = FakeSample(
        id="SYNTHETIC_SAMPLE_1",
        messages=[FakeMessage(role="assistant", content="SYNTHETIC B")],
    )
    second.epoch = 2  # type: ignore[attr-defined]
    ids = {
        o.sample_id
        for sample in (first, second)
        for o in observe_turns(sample, "SYNTHETIC-MODEL-A", "synthetic_task")
    }
    assert ids == {"SYNTHETIC_SAMPLE_1", "SYNTHETIC_SAMPLE_1#epoch2"}
