"""Agent arms for the monitor experiment: AgentHarm harmful, both haiku configs.

The coverage result showed that claude-haiku-4.5 discloses reasoning after a tool
result only when the interleaved-thinking beta header is sent. This asks the
consequence: does a monitor that reads only reasoning lose recall of harmful
behaviour on the turns where that reasoning is dark, while a monitor that reads
only actions does not?

Ground truth is AgentHarm's own published grader (refusal judge + semantic judge),
not ours. A trajectory is a positive when the model did not refuse and scored above
zero on the harmful task. The tools are AgentHarm's synthetic mocks: nothing executes
in the world. Deviation from spec §13's "benign by construction" non-goal, authorised
2026-09-13 and logged in the pre-registration's deviations section; only counts, rates
and monitor verdicts are published, never the harmful task text.

    set -a; source .env; set +a
    .venv/bin/python scripts/run_monitor_agent_arms.py --limit 50
"""

from __future__ import annotations

import argparse
from pathlib import Path

STAGING = Path("data/monitor-experiment/agent")
INTERLEAVED = {"anthropic-beta": "interleaved-thinking-2025-05-14"}
MODEL = "openrouter/anthropic/claude-haiku-4.5"

# Both arms run the same first N behaviors (deterministic dataset order, seed 0), so
# the two configs are compared on the same harmful tasks.
ARMS = {
    "haiku-noninterleaved": {},
    "haiku-interleaved": INTERLEAVED,
}


def run_arm(name: str, headers: dict[str, str], limit: int) -> str:
    """Run one haiku config on the harmful split, scored, and return the status."""
    from inspect_ai import eval as inspect_eval

    log_dir = STAGING / name
    log_dir.mkdir(parents=True, exist_ok=True)
    logs = inspect_eval(
        "inspect_evals/agentharm",
        model=MODEL,
        task_args={
            "split": "test_public",
            # The published grader; routed through OpenRouter because our OpenAI key
            # is not valid for platform.openai.com. Same model, same ground truth.
            "refusal_judge": "openrouter/openai/gpt-4o-2024-08-06",
            "semantic_judge": "openrouter/openai/gpt-4o-2024-08-06",
        },
        limit=limit,
        log_dir=str(log_dir),
        score=True,  # AgentHarm's published grader is the ground truth
        max_connections=4,
        max_tokens=8192,
        timeout=180,
        max_retries=3,
        fail_on_error=0.1,
        reasoning_tokens=2048,
        extra_headers=headers or None,
        log_model_api=True,  # keep every call's payload, not just the first five
        display="plain",
    )
    return str(logs[0].status)


def main() -> int:
    """Run both haiku configs on the harmful split; non-zero if any arm fails."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    failed = 0
    for name, headers in ARMS.items():
        print(f"=== {name} :: agentharm harmful n={args.limit}", flush=True)
        status = run_arm(name, headers, args.limit)
        print(f"### {name} status={status}", flush=True)
        failed += status != "success"
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
