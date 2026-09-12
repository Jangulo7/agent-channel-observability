"""The Mythos loader against synthetic records shaped like the real transcript.

No real transcript content appears here: the corpus carries a do-not-train notice and
a canary, and `tests/` holds synthetic fixtures only.
"""

import json
from pathlib import Path

import pytest

from channels.errors import CorpusUnavailableError, SchemaDiscoveryError
from channels.loaders.mythos_transcript import (
    MythosTranscriptLoader,
    classify_record,
    has_partial_redaction,
    thinking_block_lengths,
)
from channels.schema import Channel, Provenance, ReasoningState

SYNTHETIC_ROWS = [
    {"record": "metadata", "title": "SYNTHETIC FIXTURE", "notice": "SYNTHETIC NOTICE"},
    {
        "record": "message",
        "index": "1",
        "role": "Assistant",
        "type": "TextMessage",
        "timestamp": "2026-01-01T00:00:00Z",
        "content": "<thinking>\nSYNTHETIC REASONING\n</thinking>\nSYNTHETIC OUTPUT",
    },
    {
        "record": "message",
        "index": "2",
        "role": "Assistant",
        "type": "ToolMessage",
        "timestamp": "2026-01-01T00:00:01Z",
        "tool_name": "synthetic_tool",
        "tool_call": "{}",
        "tool_result": "SYNTHETIC RESULT",
    },
    {
        "record": "message",
        "index": "3",
        "role": "Assistant",
        "type": "TextMessage",
        "timestamp": "2026-01-01T00:00:02Z",
        "content": "[redacted]",
    },
    {
        "record": "message",
        "index": "4",
        "role": "Human",
        "type": "TextMessage",
        "timestamp": "2026-01-01T00:00:03Z",
        "content": "SYNTHETIC HUMAN TURN",
    },
]


@pytest.fixture
def transcript(tmp_path: Path) -> Path:
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in SYNTHETIC_ROWS))
    return path


def test_missing_transcript_raises_naming_the_path(tmp_path: Path) -> None:
    loader = MythosTranscriptLoader(tmp_path / "absent.jsonl")
    assert loader.available() is False
    with pytest.raises(CorpusUnavailableError) as excinfo:
        loader.require_available()
    assert "absent.jsonl" in str(excinfo.value)


def test_schema_discovery_reports_observed_keys(tmp_path: Path) -> None:
    """A file with no message rows must say what keys it actually saw."""
    path = tmp_path / "transcript.jsonl"
    path.write_text(json.dumps({"record": "metadata", "unexpected_key": 1}))
    with pytest.raises(SchemaDiscoveryError) as excinfo:
        list(MythosTranscriptLoader(path).messages())
    assert "unexpected_key" in str(excinfo.value)


def test_step_index_covers_assistant_turns_only(transcript: Path) -> None:
    observations = list(MythosTranscriptLoader(transcript).observations())
    assert [o.step_index for o in observations] == [0, 1, 2]
    assert [o.state for o in observations] == [
        ReasoningState.RAW_PRESENT,
        ReasoningState.ABSENT,   # tool result: no content field to read
        ReasoningState.REDACTED,
    ]


def test_tool_message_has_no_reasoning_channel() -> None:
    """A record with no `content` key is ABSENT, not an error and not skipped."""
    assert classify_record({"type": "ToolMessage"}) is ReasoningState.ABSENT


def test_wholly_redacted_message_is_redacted() -> None:
    assert classify_record({"content": "[redacted]"}) is ReasoningState.REDACTED


def test_in_place_marker_does_not_make_a_turn_redacted() -> None:
    """An investigator's in-place redaction is provenance, not a withheld channel.

    The model did emit reasoning and we can read most of it; what we cannot read was
    removed by Anthropic, which `Provenance.REDACTED_PARTIAL` already records. Calling
    the turn REDACTED would conflate a provider withholding a channel with a publisher
    removing an IP address.
    """
    record = {"content": "<thinking>SYNTHETIC [redacted-ip-1] REASONING</thinking>"}
    assert classify_record(record) is ReasoningState.RAW_PRESENT
    assert has_partial_redaction(record) is True


def test_utterances_withhold_text_but_are_still_counted(transcript: Path) -> None:
    utterances = list(MythosTranscriptLoader(transcript).load())
    assert len(utterances) == 3
    assert all(u.text is None for u in utterances)
    assert all(u.provenance is Provenance.REDACTED_PARTIAL for u in utterances)
    assert all(u.corpus_meta["do_not_train"] is True for u in utterances)
    assert {u.channel for u in utterances} == {Channel.REASONING, Channel.TOOL_CALL}


def test_thinking_block_lengths_are_counts_not_text() -> None:
    lengths = thinking_block_lengths(
        {"content": "<thinking>SYNTHETIC</thinking><thinking>AB</thinking>"}
    )
    assert lengths == [9, 2]


def test_describe_records_the_n_equals_one_caveat(transcript: Path) -> None:
    description = MythosTranscriptLoader(transcript).describe()
    assert description.n_actors == 1
    assert any("n=1" in caveat for caveat in description.caveats)
    assert description.source_hash.startswith("sha256:")
