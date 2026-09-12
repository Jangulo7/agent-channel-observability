"""The Inspect loader against synthetic samples, plus its missing-data behaviour."""

from pathlib import Path

import pytest

from channels.errors import CorpusUnavailableError
from channels.loaders.inspect_logs import InspectLogLoader, sample_utterances
from channels.schema import Channel

from .fixtures.synthetic import FakeMessage, FakeSample, FakeToolCall


def test_missing_logs_raise_naming_the_path(tmp_path: Path) -> None:
    """An absent corpus is a result, and it must name the path it looked in."""
    loader = InspectLogLoader(tmp_path / "no_such_logs")
    assert loader.available() is False
    with pytest.raises(CorpusUnavailableError) as excinfo:
        loader.require_available()
    assert "no_such_logs" in str(excinfo.value)


def test_tool_calls_become_utterances() -> None:
    sample = FakeSample(
        id="SYNTHETIC_SAMPLE_1",
        messages=[
            FakeMessage(
                role="assistant",
                content="SYNTHETIC",
                tool_calls=[FakeToolCall(function="synthetic_bash")],
            )
        ],
    )
    utterances = list(
        sample_utterances(sample, "SYNTHETIC-MODEL-A", "synthetic_task", "synthetic")
    )
    assert len(utterances) == 1
    assert utterances[0].channel is Channel.TOOL_CALL
    assert utterances[0].text == "synthetic_bash"
    assert utterances[0].step_index == 0
