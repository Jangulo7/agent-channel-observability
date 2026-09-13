"""Cross-check our four-state classification against the provider's own accounting.

The positional profiles differ so sharply between vendors - flat at 1.0, a
gradual decline, a cliff to zero after the first turn - that the first question
a reader should ask is whether they are real or an artefact of how Inspect or
OpenRouter package a multi-turn conversation.

This answers it with an independent instrument. Every model call is logged as a
`ModelEvent` carrying the PROVIDER's own `reasoning_tokens` count, which is
produced by their billing path and not by anything in this repository. If the
provider reports reasoning tokens on a turn we classified as having no readable
reasoning, that is our bug. If it reports zero, the model genuinely did not
reason and the shape is real.

    uv run python scripts/verify_coverage.py

Exits non-zero on any disagreement.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from inspect_ai._util.content import ContentReasoning

#: Corpora whose logs carry per-call model events.
LOG_ROOTS = (
    Path("data/inspect-runs-agentic"),
    Path("data/inspect-runs-ctf"),
    Path("data/inspect-runs-osbench"),
)


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


def _check_one_log(path: Path) -> list[str]:
    """Return a list of disagreements between our view and the provider's."""
    from inspect_ai.log import read_eval_log

    log = read_eval_log(str(path))
    problems: list[str] = []
    for sample in log.samples or []:
        calls = [e for e in (sample.events or []) if type(e).__name__ == "ModelEvent"]
        assistants = [
            m for m in sample.messages if getattr(m, "role", None) == "assistant"
        ]
        # Pair the nth model call with the nth assistant turn. A mismatch in
        # length is itself worth reporting rather than silently zipping short.
        if len(calls) != len(assistants):
            problems.append(
                f"{path.name}:{sample.id}: {len(calls)} model calls but "
                f"{len(assistants)} assistant turns"
            )
        for index, (call, message) in enumerate(zip(calls, assistants, strict=False)):
            usage = getattr(getattr(call, "output", None), "usage", None)
            provider_tokens = getattr(usage, "reasoning_tokens", None) or 0
            # The asymmetry that matters: the provider billed for reasoning and
            # we recorded NOTHING - neither readable nor withheld. The reverse
            # is fine: a provider may simply not report a count.
            if provider_tokens > 0 and not _accounted_for(message):
                problems.append(
                    f"{path.name}:{sample.id} step {index}: provider reports "
                    f"{provider_tokens} reasoning tokens and we recorded no "
                    "reasoning block at all"
                )
    return problems


def main() -> int:
    """Verify every available agentic log; exit non-zero on disagreement."""
    logs = [p for root in LOG_ROOTS if root.is_dir() for p in root.rglob("*.eval")]
    if not logs:
        print("no logs to verify", file=sys.stderr)
        return 2

    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    problems: list[str] = []
    for path in sorted(logs):
        arm = path.parent.name
        found = _check_one_log(path)
        problems.extend(found)
        totals[arm][0] += 1
        totals[arm][1] += len(found)

    print(f"{len(logs)} log(s) across {len(totals)} arm(s)\n")
    for arm, (n_logs, n_bad) in sorted(totals.items()):
        status = "OK" if n_bad == 0 else f"{n_bad} DISAGREEMENT(S)"
        print(f"  {arm:22s} {n_logs} log(s)  {status}")

    if problems:
        print(f"\n{len(problems)} disagreement(s); first 10:")
        for line in problems[:10]:
            print(f"  - {line}")
        print(
            "\nA disagreement means the provider billed for reasoning on a turn "
            "we recorded as unreadable. That is a measurement bug, not a finding."
        )
        return 1

    print(
        "\nNo disagreements. Wherever a provider billed for reasoning we "
        "recorded a\nreasoning block - readable where it was disclosed, "
        "`redacted` where it was\nwithheld - and wherever we recorded nothing "
        "the provider billed nothing.\nThe positional shapes are properties of "
        "the models, not of this pipeline."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
