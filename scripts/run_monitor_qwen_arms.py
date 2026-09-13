"""Powered monitor experiment, agent arms: qwen3-32b on AgentHarm harmful, CoT on/off.

qwen3-32b complies with the harmful split (the refusal screen found 0/15 refused) and
discloses raw reasoning after tool results, so it yields ~50 harmful-graded positives
with a readable CoT — the positives Haiku could not. Two arms, same 50 behaviours,
provider pinned so routing is fixed:

- `qwen3-on`      reasoning left on (the default): the CoT channel is visible.
- `qwen3-nothink` `/no_think` appended to each behaviour prompt: Qwen's sticky soft
  switch turns reasoning off for the whole trajectory (verified to persist across tool
  results), so the CoT channel is dark while the actions are unchanged in kind.

The recall a reasoning-only monitor loses between these arms, against an action-only
monitor that should not move, is the measurement. AgentHarm's synthetic mock tools and
its own grader as ground truth; only counts, rates and verdicts leave here. The
harmful-split run is the authorised, logged section-13 deviation; appending `/no_think`
is a prompt manipulation, logged with it.

    set -a; source .env; set +a
    .venv/bin/python scripts/run_monitor_qwen_arms.py --limit 50
"""

from __future__ import annotations

import argparse
from pathlib import Path

STAGING = Path("data/monitor-experiment/agent-qwen3")
MODEL = "openrouter/qwen/qwen3-32b"
JUDGE = "openrouter/openai/gpt-4o-2024-08-06"
# Pin one upstream so the two arms differ only in the /no_think switch, and use the
# provider that honoured the switch in the probe.
PROVIDER = {"order": ["deepinfra"], "allow_fallbacks": False}


def run_arm(arm: str, no_think: bool, limit: int) -> str:
    """Run one qwen3 arm on the harmful split, scored, and return the status."""
    from inspect_ai import eval as inspect_eval
    from inspect_evals.agentharm import agentharm

    task = agentharm(split="test_public", refusal_judge=JUDGE, semantic_judge=JUDGE)
    if no_think:
        # Qwen's soft switch; sticky across tool results, so the whole trajectory
        # runs without reasoning. Appended to the behaviour prompt, not the codebook.
        for sample in task.dataset:
            sample.input = f"{sample.input} /no_think"
    log_dir = STAGING / arm
    log_dir.mkdir(parents=True, exist_ok=True)
    logs = inspect_eval(
        task,
        model=MODEL,
        model_args={"provider": PROVIDER},
        limit=limit,
        log_dir=str(log_dir),
        score=True,
        max_connections=4,
        max_tokens=8192,
        timeout=180,
        max_retries=3,
        fail_on_error=0.2,
        log_model_api=True,
        display="plain",
    )
    return str(logs[0].status)


def main() -> int:
    """Run both qwen3 arms; non-zero if any arm fails."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    failed = 0
    for arm, no_think in (("qwen3-on", False), ("qwen3-nothink", True)):
        print(f"=== {arm} :: agentharm harmful n={args.limit} no_think={no_think}",
              flush=True)
        status = run_arm(arm, no_think, args.limit)
        print(f"### {arm} status={status}", flush=True)
        failed += status != "success"
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
