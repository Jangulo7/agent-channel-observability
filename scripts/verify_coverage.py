"""Cross-check our four-state classification against the provider's own accounting.

The positional profiles differ so sharply between vendors - flat at 1.0, a
gradual decline, a cliff to zero after the first turn - that the first question
a reader should ask is whether they are real or an artefact of how Inspect or
OpenRouter package a multi-turn conversation.

This answers it with an independent instrument. Every model call is logged as a
`ModelEvent` carrying the PROVIDER's own `reasoning_tokens` count
(`ModelEvent.output.usage.reasoning_tokens`), which is produced by their billing
path and not by anything in this repository, and which exists on every call.
(Raw call payloads are only logged for the first few calls per sample, so they
cannot be used.) Two directions are checked:

- the provider billed reasoning tokens and we recorded no reasoning block at all;
- we recorded readable reasoning (RAW_PRESENT) and the provider reports exactly
  zero reasoning tokens (an explicit 0; a missing count is not evidence).

    uv run python scripts/verify_coverage.py

Exits 0 when there is no disagreement, 1 on any disagreement, 2 with no logs.
"""

from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from inspect_ai._util.content import ContentReasoning

from channels.coverage import classify_reasoning, classify_turn
from channels.schema import ReasoningState

#: The three agentic families: the only corpora whose model calls pair one-to-one
#: with assistant turns, which is what this check needs.
LOG_ROOTS = (
    Path("data/inspect-runs-agentic"),
    Path("data/inspect-runs-ctf"),
    Path("data/inspect-runs-osbench"),
)

SCOPE_STATEMENT = (
    "Verifies: " + ", ".join(str(root) for root in LOG_ROOTS)
    + " (the three agentic families).\n"
    "Out of scope: data/inspect-runs (baseline), whose logs carry the scorer's own "
    "ModelEvents interleaved with the model's calls, so calls cannot be paired with "
    "assistant turns; and data/inspect-runs-reasoning (reasoning sweep), a "
    "single-turn sweep this script does not pair."
)


@dataclass
class SampleCheck:
    """What one sample's cross-check found, split by whether it is a disagreement."""

    disagreements: list[str] = field(default_factory=list)
    unpaired_trailing: list[str] = field(default_factory=list)   # informational
    blank_with_tokens: int = 0                                     # informational
    calls: int = 0
    turns: int = 0

    def absorb(self, other: SampleCheck) -> None:
        """Add another check's findings and counts to this one."""
        self.disagreements += other.disagreements
        self.unpaired_trailing += other.unpaired_trailing
        self.blank_with_tokens += other.blank_with_tokens
        self.calls += other.calls
        self.turns += other.turns


def _reasoning_blocks(message: object) -> list[ContentReasoning]:
    """Reasoning blocks on one assistant turn, readable or withheld."""
    content = getattr(message, "content", None)
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, ContentReasoning)]


def _accounted_for(message: object) -> bool:
    """Whether a provider's reasoning tokens are explained by what we recorded.

    Readable reasoning explains them. So does a REDACTED block: the provider
    reasoned, billed for it, and withheld the text - which is the `redacted`
    state, not a measurement failure. Only a turn with no reasoning block of any
    kind leaves billed tokens unexplained, and that would be our bug.
    """
    return bool(_reasoning_blocks(message))


def _state(message: object) -> ReasoningState:
    """Our four-state classification of one turn, from its reasoning blocks."""
    return classify_turn([classify_reasoning(b) for b in _reasoning_blocks(message)])


def _provider_tokens(call: object) -> int | None:
    """The provider's reasoning_tokens for one call; None when not reported."""
    usage = getattr(getattr(call, "output", None), "usage", None)
    return getattr(usage, "reasoning_tokens", None)


def _output_message_id(call: object) -> str | None:
    """The id of the message a call produced, used to confirm positional pairing."""
    choices = getattr(getattr(call, "output", None), "choices", None) or []
    if not choices:
        return None
    return getattr(getattr(choices[0], "message", None), "id", None)


def check_sample(
    label: str, calls: Sequence[object], turns: Sequence[object]
) -> SampleCheck:
    """Pair the nth model call with the nth assistant turn and check each pair.

    Calls beyond the last assistant turn are trailing calls whose output never
    became a message (the sample ended by error or limit). One that reports
    reasoning tokens is a disagreement; one that reports none is informational.
    Any other count mismatch, or a pair whose message ids differ, is a disagreement.
    """
    result = SampleCheck(calls=len(calls), turns=len(turns))
    if len(calls) < len(turns):
        result.disagreements.append(
            f"{label}: {len(calls)} model calls but {len(turns)} assistant turns"
        )
    for index, call in enumerate(calls[len(turns):], start=len(turns)):
        tokens = _provider_tokens(call)
        line = f"{label} call {index}: no assistant message, reasoning_tokens={tokens}"
        target = result.disagreements if tokens else result.unpaired_trailing
        target.append(line)
    for index, (call, message) in enumerate(zip(calls, turns, strict=False)):
        _check_pair(f"{label} step {index}", call, message, result)
    return result


def _check_pair(
    label: str, call: object, message: object, result: SampleCheck
) -> None:
    """Apply the pairing, billed-but-unrecorded and readable-but-unbilled checks."""
    call_id, message_id = _output_message_id(call), getattr(message, "id", None)
    if call_id and message_id and call_id != message_id:
        result.disagreements.append(
            f"{label}: call and turn message ids differ; positional pairing broken"
        )
        return
    tokens = _provider_tokens(call)
    if tokens and tokens > 0 and not _accounted_for(message):
        result.disagreements.append(
            f"{label}: provider reports {tokens} reasoning tokens and we recorded "
            "no reasoning block at all"
        )
    elif tokens and tokens > 0 and _state(message) is ReasoningState.ABSENT:
        result.blank_with_tokens += 1
    if tokens == 0 and _state(message) is ReasoningState.RAW_PRESENT:
        result.disagreements.append(
            f"{label}: we recorded RAW_PRESENT and the provider reports exactly 0 "
            "reasoning tokens"
        )


def check_log(path: Path) -> SampleCheck:
    """Return the merged cross-check of every sample in one log."""
    from inspect_ai.log import read_eval_log

    merged = SampleCheck()
    for sample in read_eval_log(str(path)).samples or []:
        calls = [e for e in (sample.events or []) if type(e).__name__ == "ModelEvent"]
        turns = [m for m in sample.messages if getattr(m, "role", None) == "assistant"]
        merged.absorb(check_sample(f"{path.name}:{sample.id}", calls, turns))
    return merged


def _print_lines(title: str, lines: Sequence[str], limit: int = 10) -> None:
    """Print a titled section with its count and at most `limit` of its lines."""
    shown = f" (first {limit})" if len(lines) > limit else ""
    print(f"\n{title}: {len(lines)}{shown}")
    for line in lines[:limit]:
        print(f"  - {line}")


def main() -> int:
    """Verify every available agentic log; exit non-zero on any disagreement."""
    print(SCOPE_STATEMENT)
    logs = [p for root in LOG_ROOTS if root.is_dir() for p in root.rglob("*.eval")]
    if not logs:
        print("no logs to verify", file=sys.stderr)
        return 2

    per_arm: dict[str, SampleCheck] = {}
    n_logs: Counter[str] = Counter()
    for path in sorted(logs):
        arm = f"{path.parent.parent.name}/{path.parent.name}"
        per_arm.setdefault(arm, SampleCheck()).absorb(check_log(path))
        n_logs[arm] += 1
    return _report(per_arm, n_logs)


def _report(per_arm: dict[str, SampleCheck], n_logs: Counter[str]) -> int:
    """Print the per-arm table and the three sections; return the exit code."""
    print(f"\n{sum(n_logs.values())} log(s) across {len(per_arm)} arm(s)\n")
    print(f"  {'arm':42s} logs  calls  turns  disagree  trailing  blank+tokens")
    for arm, found in sorted(per_arm.items()):
        print(f"  {arm:42s} {n_logs[arm]:4d} {found.calls:6d} {found.turns:6d} "
              f"{len(found.disagreements):9d} {len(found.unpaired_trailing):9d} "
              f"{found.blank_with_tokens:13d}")
    disagreements = [line for f in per_arm.values() for line in f.disagreements]
    trailing = [line for f in per_arm.values() for line in f.unpaired_trailing]
    blank = sum(f.blank_with_tokens for f in per_arm.values())
    _print_lines("DISAGREEMENTS", disagreements)
    _print_lines("Informational - unpaired trailing calls reporting 0/None "
                 "reasoning tokens (sample ended before a message was written)",
                 trailing)
    print(f"\nInformational - turns with a reasoning block present but blank, where "
          f"the provider billed reasoning tokens (classified ABSENT): {blank}")
    if disagreements:
        print("\nA disagreement is a measurement bug until explained, not a finding.")
        return 1
    print("\nNo disagreements in the verified roots.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
