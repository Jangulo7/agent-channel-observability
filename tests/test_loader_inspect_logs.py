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


def test_incomplete_logs_are_excluded_and_named(tmp_path: Path) -> None:
    """A log still being written must leave the denominator, and be reported.

    Found live: the sweep was mid-run and `channels gate` crashed reading a log
    with status=started. Silently including it would have been worse than the
    crash - a partial log shrinks a denominator without saying so, which is the
    exact failure emission.py exists to prevent.
    """
    from unittest.mock import patch

    from channels.loaders.inspect_logs import InspectLogLoader

    (tmp_path / "started.eval").write_bytes(b"not a real log")
    loader = InspectLogLoader(tmp_path)
    # An unreadable header counts as incomplete rather than crashing the run.
    assert loader.incomplete_logs() == [tmp_path / "started.eval"]
    assert loader.log_paths() == []

    class _Header:
        status = "success"

    with patch("inspect_ai.log.read_eval_log", return_value=_Header()):
        assert loader.incomplete_logs() == []
        assert loader.log_paths() == [tmp_path / "started.eval"]
