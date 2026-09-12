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


def test_errored_samples_are_counted_not_silently_dropped(tmp_path: Path) -> None:
    """A sample that died leaves the denominator, and the shortfall is reported.

    This is the dropped-denominator failure in its subtlest form: an errored
    sample contributes no assistant turn, so a rate computed over the survivors
    is arithmetically correct and epistemically wrong unless the shortfall is
    stated. `describe()` states it.
    """
    from unittest.mock import patch

    from channels.loaders.inspect_logs import InspectLogLoader

    (tmp_path / "run.eval").write_bytes(b"placeholder")

    class _Results:
        completed_samples = 240
        total_samples = 250

    class _Header:
        status = "success"
        results = _Results()

    loader = InspectLogLoader(tmp_path)
    with patch("inspect_ai.log.read_eval_log", return_value=_Header()):
        assert loader.errored_samples() == 10


def test_arms_of_one_model_are_not_pooled(tmp_path: Path) -> None:
    """A model run under several configurations must not collapse into one label.

    Found by looking at Figure 1: `deepseek-v3.2` appeared as a single bar that
    was really the reasoning-on arm alone. Grouping on the model id pools arms
    that differ by exactly the variable under study - reasoning on vs off, or
    three reasoning_effort levels - which would have destroyed the axis the run
    exists to measure.
    """
    from unittest.mock import patch

    from channels.loaders.inspect_logs import InspectLogLoader

    for arm in ("reasoning-on", "reasoning-off"):
        (tmp_path / arm).mkdir()
        (tmp_path / arm / "run.eval").write_bytes(b"placeholder")

    class _Header:
        status = "success"

    loader = InspectLogLoader(tmp_path, label_by_directory=True)
    with patch("inspect_ai.log.read_eval_log", return_value=_Header()):
        paths = sorted(loader.log_paths())
    assert {loader._label_for(p, "same/model/id") for p in paths} == {
        "reasoning-on",
        "reasoning-off",
    }
    # Default behaviour is unchanged: the model id is the label.
    plain = InspectLogLoader(tmp_path)
    assert plain._label_for(paths[0], "same/model/id") == "same/model/id"
