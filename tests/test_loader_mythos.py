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


@pytest.mark.parametrize(
    "content", ["[redacted-SYNTHETICLABEL]", "  [redacted]\n", "[redacted-syn-1]"]
)
def test_whole_message_labelled_marker_is_redacted(content: str) -> None:
    """A labelled marker as the whole message is withheld, not absent reasoning."""
    assert classify_record({"content": content}) is ReasoningState.REDACTED
    assert has_partial_redaction({"content": content}) is False


def test_marker_beside_other_text_is_not_whole_message_redaction() -> None:
    record = {"content": "SYNTHETIC OUTPUT [redacted-syn-1]"}
    assert classify_record(record) is ReasoningState.ABSENT
    assert has_partial_redaction(record) is True


def _write_rows(path: Path, contents: list[str | None]) -> Path:
    rows: list[dict[str, object]] = [{"record": "metadata", "title": "SYNTHETIC"}]
    for index, content in enumerate(contents):
        row: dict[str, object] = {
            "record": "message", "index": str(index), "role": "Assistant",
            "type": "TextMessage", "timestamp": f"2026-01-01T00:00:{index:02d}Z",
        }
        if content is not None:
            row["content"] = content
        rows.append(row)
    path.write_text("\n".join(json.dumps(row) for row in rows))
    return path


def test_describe_computes_the_partial_redaction_caveat(tmp_path: Path) -> None:
    """The caveat's counts and the counterfactual rate are computed, not typed.

    Eight synthetic turns: four RAW_PRESENT, of which two carry in-place markers (one
    inside <thinking>, one outside it). Kept RAW_PRESENT the rate is 4/8; were the
    marked turns REDACTED it would be 2/8.
    """
    path = _write_rows(tmp_path / "transcript.jsonl", [
        "<thinking>SYNTHETIC [redacted-syn-1] REASONING</thinking>SYNTHETIC",
        "<thinking>SYNTHETIC REASONING</thinking>SYNTHETIC [redacted]",
        "<thinking>SYNTHETIC REASONING</thinking>SYNTHETIC",
        "<thinking>SYNTHETIC REASONING</thinking>",
        "[redacted-syn-2]",
        "SYNTHETIC OUTPUT ONLY",
        None,
        "[redacted]",
    ])
    loader = MythosTranscriptLoader(path)
    states = [o.state for o in loader.observations()]
    assert states.count(ReasoningState.RAW_PRESENT) == 4
    assert states.count(ReasoningState.REDACTED) == 2
    caveat = next(c for c in loader.describe().caveats if "in-place" in c)
    assert caveat.startswith("2 of 4 RAW_PRESENT turns")
    assert "(1 inside a <thinking> block)" in caveat
    assert "raw_present 0.5000" in caveat
    assert "would be 0.2500" in caveat
