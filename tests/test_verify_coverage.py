"""The coverage cross-check must still fail on a genuine measurement bug.

`verify_coverage.py` initially flagged 174 turns where the provider billed for
reasoning and we recorded none READABLE. Those were `gpt-5-nano` turns whose
reasoning is encrypted: the provider reasons, bills, and withholds the text,
which is the `redacted` state and precisely the finding — not a bug. The script
was corrected to ask whether a reasoning block was recorded AT ALL.

Correcting a check so that it passes is the same shape as weakening one, so
these tests exist to show the corrected check still has teeth.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from inspect_ai._util.content import ContentReasoning, ContentText

_spec = importlib.util.spec_from_file_location(
    "verify_coverage", Path(__file__).parents[1] / "scripts" / "verify_coverage.py"
)
assert _spec and _spec.loader
verify_coverage = importlib.util.module_from_spec(_spec)
# Registered before execution, as importlib's recipe requires: the script defines a
# dataclass, and dataclasses resolve their module through sys.modules.
sys.modules["verify_coverage"] = verify_coverage
_spec.loader.exec_module(verify_coverage)


class _Message:
    """Minimal stand-in for an assistant message."""

    def __init__(self, content: object) -> None:
        self.role = "assistant"
        self.content = content


def test_readable_reasoning_accounts_for_billed_tokens() -> None:
    message = _Message([ContentReasoning(reasoning="a placeholder chain")])
    assert verify_coverage._accounted_for(message) is True


def test_redacted_reasoning_also_accounts_for_billed_tokens() -> None:
    """The corrected behaviour: withheld reasoning explains the provider's bill."""
    message = _Message([ContentReasoning(reasoning="", redacted=True)])
    assert verify_coverage._accounted_for(message) is True


def test_no_reasoning_block_does_not_account_for_billed_tokens() -> None:
    """The teeth. A turn with no reasoning block leaves billed tokens unexplained.

    This is the real measurement bug the script exists to catch, and the
    correction did not stop it catching it.
    """
    text_only = _Message([ContentText(text="hello")])
    assert verify_coverage._accounted_for(text_only) is False
    assert verify_coverage._accounted_for(_Message("plain string content")) is False
    assert verify_coverage._accounted_for(_Message([])) is False


# --- pairing, trailing calls and the reverse check (synthetic stand-ins) ----------


class _Usage:
    def __init__(self, reasoning_tokens: int | None) -> None:
        self.reasoning_tokens = reasoning_tokens


class _Choice:
    def __init__(self, message_id: str) -> None:
        self.message = type("_Msg", (), {"id": message_id})()


class _Output:
    def __init__(self, tokens: int | None, message_id: str) -> None:
        self.usage = _Usage(tokens)
        self.choices = [_Choice(message_id)]


class _Call:
    """Minimal stand-in for a ModelEvent: output.usage and output.choices only."""

    def __init__(self, tokens: int | None, message_id: str = "SYN") -> None:
        self.output = _Output(tokens, message_id)


def _turn(content: object, message_id: str = "SYN") -> _Message:
    message = _Message(content)
    message.id = message_id  # type: ignore[attr-defined]
    return message


def test_trailing_call_without_tokens_is_informational_not_a_disagreement() -> None:
    turns = [_turn([ContentReasoning(reasoning="SYNTHETIC CHAIN")], "m0")]
    calls = [_Call(12, "m0"), _Call(0, "never-written"), _Call(None, "never")]
    result = verify_coverage.check_sample("SYNTHETIC", calls, turns)
    assert result.disagreements == []
    assert len(result.unpaired_trailing) == 2


def test_trailing_call_with_tokens_is_a_disagreement() -> None:
    turns = [_turn([ContentReasoning(reasoning="SYNTHETIC CHAIN")], "m0")]
    calls = [_Call(12, "m0"), _Call(40, "never-written")]
    result = verify_coverage.check_sample("SYNTHETIC", calls, turns)
    assert len(result.disagreements) == 1
    assert result.unpaired_trailing == []


def test_non_trailing_mismatch_is_a_disagreement() -> None:
    """An extra call in the middle breaks positional pairing, detected by id."""
    turns = [
        _turn([ContentText(text="SYNTHETIC")], "m0"),
        _turn([ContentText(text="SYNTHETIC")], "m1"),
    ]
    calls = [_Call(0, "m0"), _Call(0, "errored-mid"), _Call(0, "m1")]
    result = verify_coverage.check_sample("SYNTHETIC", calls, turns)
    assert any("pairing broken" in line for line in result.disagreements)

    fewer = verify_coverage.check_sample("SYNTHETIC", [_Call(0, "m0")], turns)
    assert any("1 model calls but 2" in line for line in fewer.disagreements)


def test_raw_present_with_explicit_zero_tokens_is_a_disagreement() -> None:
    """The reverse check: readable reasoning the provider says it never produced."""
    turn = _turn([ContentReasoning(reasoning="SYNTHETIC CHAIN")])
    zero = verify_coverage.check_sample("SYNTHETIC", [_Call(0)], [turn])
    assert len(zero.disagreements) == 1
    # A missing count is not evidence either way.
    unknown = verify_coverage.check_sample("SYNTHETIC", [_Call(None)], [turn])
    assert unknown.disagreements == []


def test_blank_block_with_billed_tokens_is_counted_not_a_disagreement() -> None:
    """A present-but-blank block explains nothing readable; it is reported apart."""
    turn = _turn([ContentReasoning(reasoning="  \n ")])
    result = verify_coverage.check_sample("SYNTHETIC", [_Call(30)], [turn])
    assert result.disagreements == []
    assert result.blank_with_tokens == 1


def test_billed_tokens_with_no_block_remain_a_disagreement() -> None:
    turn = _turn([ContentText(text="SYNTHETIC")])
    result = verify_coverage.check_sample("SYNTHETIC", [_Call(30)], [turn])
    assert len(result.disagreements) == 1
