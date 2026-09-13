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
from pathlib import Path

from inspect_ai._util.content import ContentReasoning, ContentText

_spec = importlib.util.spec_from_file_location(
    "verify_coverage", Path(__file__).parents[1] / "scripts" / "verify_coverage.py"
)
assert _spec and _spec.loader
verify_coverage = importlib.util.module_from_spec(_spec)
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
