"""Long-horizon arm: SWE-bench Verified on cheap open models, for coverage by step.

The transfer question the project could not answer: does reasoning disclosure hold
over long agentic trajectories, or decay with depth? SWE-bench gives real multi-step
tool use in a per-instance Docker sandbox. We measure the reasoning channel, not the
solve rate, so scoring is off; the point is the trajectory and its coverage by step,
not whether the bug was fixed. Cheap open models are used deliberately (running long
trajectories on frontier APIs is the cost wall); whether a cheap model sustains a long
trajectory is itself part of the answer. The same instances run under every model, so
the comparison is clean and the 2 GB images are pulled once.

    set -a; source .env; set +a
    .venv/bin/python scripts/run_swebench_arm.py --limit 10
"""

from __future__ import annotations

import argparse
from pathlib import Path

STAGING = Path("data/inspect-runs-swebench")
MODELS = [
    "openrouter/qwen/qwen3-32b",
    "openrouter/openai/gpt-oss-120b",
    "openrouter/nvidia/nemotron-3.5-lightning",
]


def run_arm(model: str, limit: int, message_limit: int) -> str:
    """Run one model on the first `limit` SWE-bench instances; return the status."""
    from inspect_ai import eval as inspect_eval

    arm = model.split("/")[-1]
    log_dir = STAGING / arm
    log_dir.mkdir(parents=True, exist_ok=True)
    logs = inspect_eval(
        "inspect_evals/swe_bench",
        model=model,
        limit=limit,
        message_limit=message_limit,  # raised from the task default of 30 for long runs
        log_dir=str(log_dir),
        score=False,  # we measure the reasoning channel, not the solve rate
        max_connections=4,
        max_tokens=8192,
        timeout=240,
        max_retries=3,
        fail_on_error=0.3,
        log_model_api=True,
        display="plain",
        sandbox_cleanup=True,
    )
    return str(logs[0].status)


def main() -> int:
    """Run the three cheap-model arms sequentially; non-zero if any fails."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--message-limit", type=int, default=120)
    args = parser.parse_args()
    failed = 0
    for model in MODELS:
        print(f"=== {model} :: swe_bench n={args.limit} mlimit={args.message_limit}",
              flush=True)
        status = run_arm(model, args.limit, args.message_limit)
        print(f"### {model} status={status}", flush=True)
        failed += status != "success"
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
