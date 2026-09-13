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
cannot be used.) Each turn is paired with the call that produced it by message id,
through `channels.provider_usage`, the same implementation the loader uses. Two
directions are checked:

- the provider billed reasoning tokens and we recorded no reasoning block at all;
- we recorded readable reasoning (RAW_PRESENT) and the provider reports exactly
  zero reasoning tokens (an explicit 0; a missing count is not evidence). This is
  labelled "provider token accounting inconsistent with returned reasoning": the
  returned reasoning is direct evidence, so the count is the suspect side (a
  provider-pinned gpt-oss-120b upstream has been seen doing exactly this).

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
from channels.provider_usage import (
    SamplePairing,
    assistant_turns,
    call_errored,
    model_calls,
    pair_turns,
    reasoning_tokens,
)
from channels.schema import ReasoningState

#: The three agentic families: multi-turn corpora whose providers report
#: reasoning_tokens, which is what this check needs.
LOG_ROOTS = (
    Path("data/inspect-runs-agentic"),
    Path("data/inspect-runs-ctf"),
    Path("data/inspect-runs-osbench"),
)

SCOPE_STATEMENT = (
    "Verifies: " + ", ".join(str(root) for root in LOG_ROOTS)
    + " (the three agentic families).\n"
    "Out of scope: data/inspect-runs (baseline), whose vLLM calls report no "
    "reasoning_tokens, so there is nothing to cross-check (its interleaved scorer "
    "calls are skipped by id pairing); and data/inspect-runs-reasoning (reasoning "
    "sweep), a single-turn sweep this script does not verify."
)


@dataclass
class SampleCheck:
    """What one sample's cross-check found, split by whether it is a disagreement."""

    disagreements: list[str] = field(default_factory=list)
    unpaired_trailing: list[str] = field(default_factory=list)   # informational
    errored_mid_calls: list[str] = field(default_factory=list)   # informational
    blank_with_tokens: int = 0                                     # informational
    calls: int = 0
    turns: int = 0

    def absorb(self, other: SampleCheck) -> None:
        """Add another check's findings and counts to this one."""
        self.disagreements += other.disagreements
        self.unpaired_trailing += other.unpaired_trailing
        self.errored_mid_calls += other.errored_mid_calls
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


def check_sample(
    label: str, calls: Sequence[object], turns: Sequence[object]
) -> SampleCheck:
    """Pair each assistant turn with its model call by message id and check each pair.

    A turn no call can be paired to is a disagreement. A call whose output became no
    turn is informational when it trails the last paired call (the sample ended by
    error or limit) or recorded an error mid-sample (a failed attempt, retried), unless
    it reports reasoning tokens; any other unmatched call means a message is missing.
    """
    result = SampleCheck(calls=len(calls), turns=len(turns))
    pairing = pair_turns(turns, calls)
    if len(calls) < len(turns):
        result.disagreements.append(
            f"{label}: {len(calls)} model calls but {len(turns)} assistant turns"
        )
    for index in pairing.unpaired_turns:
        result.disagreements.append(
            f"{label} step {index}: no model call carries this turn's message id"
        )
    _check_unmatched_calls(label, calls, pairing, result)
    for index, message in enumerate(turns):
        if pairing.call_for_turn[index] is not None:
            _check_pair(f"{label} step {index}", pairing.tokens[index], message, result)
    return result


def _check_unmatched_calls(
    label: str, calls: Sequence[object], pairing: SamplePairing, result: SampleCheck
) -> None:
    """Sort calls that produced no turn into disagreements and informational lines."""
    trailing = set(pairing.trailing_calls())
    for index in pairing.unmatched_calls:
        tokens = reasoning_tokens(calls[index])
        line = f"{label} call {index}: no assistant message, reasoning_tokens={tokens}"
        if tokens:
            result.disagreements.append(line)
        elif index in trailing:
            result.unpaired_trailing.append(line)
        elif call_errored(calls[index]):
            result.errored_mid_calls.append(line)
        else:
            result.disagreements.append(
                f"{line}; mid-sample and not errored, so id pairing broken"
            )


def _check_pair(
    label: str, tokens: int | None, message: object, result: SampleCheck
) -> None:
    """Apply the billed-but-unrecorded and readable-but-unbilled checks to one pair."""
    if tokens and tokens > 0 and not _accounted_for(message):
        result.disagreements.append(
            f"{label}: provider reports {tokens} reasoning tokens and we recorded "
            "no reasoning block at all"
        )
    elif tokens and tokens > 0 and _state(message) is ReasoningState.ABSENT:
        result.blank_with_tokens += 1
    if tokens == 0 and _state(message) is ReasoningState.RAW_PRESENT:
        result.disagreements.append(
            f"{label}: provider token accounting inconsistent with returned "
            "reasoning - we recorded RAW_PRESENT and the provider reports exactly 0 "
            "reasoning tokens (the token count is the suspect side)"
        )


def check_log(path: Path) -> SampleCheck:
    """Return the merged cross-check of every sample in one log."""
    from inspect_ai.log import read_eval_log

    merged = SampleCheck()
    for sample in read_eval_log(str(path)).samples or []:
        merged.absorb(check_sample(
            f"{path.name}:{sample.id}", model_calls(sample), assistant_turns(sample)
        ))
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
    errored = [line for f in per_arm.values() for line in f.errored_mid_calls]
    blank = sum(f.blank_with_tokens for f in per_arm.values())
    _print_lines("DISAGREEMENTS", disagreements)
    _print_lines("Informational - unpaired trailing calls reporting 0/None "
                 "reasoning tokens (sample ended before a message was written)",
                 trailing)
    _print_lines("Informational - errored mid-sample calls reporting 0/None "
                 "reasoning tokens (failed attempts; a later call wrote the turn)",
                 errored)
    print(f"\nInformational - turns with a reasoning block present but blank, where "
          f"the provider billed reasoning tokens (classified ABSENT): {blank}")
    if disagreements:
        print("\nA disagreement is a measurement bug until explained, not a finding.")
        return 1
    print("\nNo disagreements in the verified roots.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
