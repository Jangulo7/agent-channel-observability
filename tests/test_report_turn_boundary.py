"""Turn-boundary pairing: roles, usage paired by message id, unpaired calls counted.

Every object here is a synthetic stand-in; no log is read.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from inspect_ai._util.content import ContentReasoning, ContentText

_spec = importlib.util.spec_from_file_location(
    "report_turn_boundary",
    Path(__file__).parents[1] / "scripts" / "report_turn_boundary.py",
)
assert _spec and _spec.loader
report_turn_boundary = importlib.util.module_from_spec(_spec)
# The script defines dataclasses, which look their module up in sys.modules.
sys.modules[_spec.name] = report_turn_boundary
_spec.loader.exec_module(report_turn_boundary)


@dataclass
class _Message:
    """Minimal stand-in for a chat message."""

    role: str
    content: Any = "synthetic"
    id: str | None = None


@dataclass
class _Usage:
    reasoning_tokens: int | None


@dataclass
class _Choice:
    message: _Message


@dataclass
class _Output:
    usage: _Usage | None
    message_id: str | None = None

    @property
    def choices(self) -> list[_Choice]:
        """One choice carrying the produced message's id, as Inspect records it."""
        if self.message_id is None:
            return []
        return [_Choice(_Message("assistant", id=self.message_id))]


@dataclass
class _ModelEvent:
    """Minimal stand-in for an Inspect ModelEvent."""

    output: _Output
    input: list[_Message] = field(default_factory=list)
    call: Any = None
    event: str = "model"


@dataclass
class _Sample:
    messages: list[_Message]
    events: list[Any]
    id: str = "synthetic-sample"


def _thinking() -> list[Any]:
    return [ContentReasoning(reasoning="synthetic thought"), ContentText(text="x")]


def test_preceding_role_is_the_message_immediately_before() -> None:
    messages = [
        _Message("system"), _Message("user"), _Message("assistant"),
        _Message("tool"), _Message("assistant"), _Message("user"),
        _Message("assistant"),
    ]
    assert report_turn_boundary.preceding_roles(messages) == [
        (0, "step 0"), (1, "after tool"), (2, "after user"),
    ]


def _assistants(*ids: str) -> list[_Message]:
    return [_Message("assistant", id=message_id) for message_id in ids]


def test_usage_pairs_by_message_id_and_counts_trailing_calls() -> None:
    events = [
        _ModelEvent(_Output(_Usage(n), message_id))
        for n, message_id in ((50, "SYN-0"), (0, "SYN-1"), (7, "SYN-never-written"))
    ]
    turns = _assistants("SYN-0", "SYN-1")
    tokens, trailing, missing = report_turn_boundary.pair_usage(turns, events)
    assert tokens == [50, 0]
    assert (trailing, missing) == (1, 0)


def test_turn_without_a_call_or_usage_is_unrecorded_not_zero() -> None:
    events = [_ModelEvent(_Output(None, "SYN-0"))]
    turns = _assistants("SYN-0", "SYN-1")
    tokens, trailing, missing = report_turn_boundary.pair_usage(turns, events)
    assert tokens == [None, None]
    assert (trailing, missing) == (0, 1)


def test_sample_counts_split_by_role_and_step() -> None:
    """Reasoning after the user, none after a tool: the pattern the script reports."""
    messages = [
        _Message("user"), _Message("assistant", _thinking(), "SYN-0"),
        _Message("tool"), _Message("assistant", [ContentText(text="x")], "SYN-1"),
        _Message("user"), _Message("assistant", _thinking(), "SYN-2"),
    ]
    events = [
        _ModelEvent(_Output(_Usage(12), "SYN-0"), input=[_Message("user")]),
        _ModelEvent(_Output(_Usage(0), "SYN-1"), input=[_Message("tool")]),
        _ModelEvent(_Output(_Usage(9), "SYN-2"), input=[_Message("user")]),
        _ModelEvent(
            _Output(_Usage(3), "SYN-never-written"), input=[_Message("assistant")]
        ),
    ]
    report = report_turn_boundary.ArmReport()
    report_turn_boundary.count_sample(
        report, _Sample(messages, events), "synthetic_arm", "synthetic_task"
    )
    after_tool = report.buckets["after tool"]
    after_user = report.buckets["after user"]
    assert after_tool.n == 1
    assert after_tool.raw_present == 0
    assert after_tool.absent_no_block == 1
    assert after_tool.reasoning_tokens_gt0 == 0
    assert after_user.n == 1
    assert after_user.raw_present == 1
    assert after_user.reasoning_tokens_gt0 == 1
    assert report.buckets["step 0"].n == 1
    assert report.unpaired_trailing_calls == 1
    assert report.pairing_role_mismatches == 0
    assert report.calls_without_raw_logged == 4


def test_header_config_reports_key_names_only() -> None:
    request = {
        "extra_headers": {"anthropic-beta": "synthetic-secret-value"},
        "extra_body": {"reasoning": {"max_tokens": 1}},
    }
    config = report_turn_boundary.request_config(request)
    assert config["header_keys"] == ["anthropic-beta"]
    assert config["interleaved_or_beta_header_key_present"] is True
    assert "synthetic-secret-value" not in repr(config)
