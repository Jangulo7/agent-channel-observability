"""Refusal screen: which open models comply with AgentHarm harmful and disclose CoT.

Answers "which agent gives positives for the monitor experiment" with data, not a
guess: per model, the AgentHarm refusal and harmful-compliance rate and the share of
post-tool turns that disclose readable reasoning. AgentHarm's synthetic mock tools; its
own grader is ground truth; only counts are written, never task or reasoning text. The
harmful-split run is the authorised, logged section-13 deviation (PREREGISTRATION 11).

    set -a; source .env; set +a
    .venv/bin/python scripts/run_refusal_screen.py                 # run + summarise
    .venv/bin/python scripts/run_refusal_screen.py --summarise-only # existing logs
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any

SCREEN_DIR = Path("data/monitor-experiment/screen")
OUT = Path("results/monitor_experiment/refusal_screen.json")
JUDGE = "openrouter/openai/gpt-4o-2024-08-06"
N = 15
MODELS = [
    "openrouter/deepseek/deepseek-v3.2",
    "openrouter/qwen/qwen3-32b",
    "openrouter/z-ai/glm-4.6",
    "openrouter/moonshotai/kimi-k2-thinking",
    "openrouter/minimax/minimax-m2",
    "openrouter/openai/gpt-oss-120b",
]


def run() -> None:
    """Run the harmful screen for every model into its own staging directory."""
    from inspect_ai import eval as inspect_eval

    for model in MODELS:
        slug = model.split("/")[-1]
        inspect_eval(
            "inspect_evals/agentharm",
            model=model,
            task_args={"split": "test_public", "refusal_judge": JUDGE,
                       "semantic_judge": JUDGE},
            limit=N,
            log_dir=str(SCREEN_DIR / slug),
            max_connections=4,
            max_tokens=8192,
            timeout=180,
            max_retries=3,
            fail_on_error=0.3,
            log_model_api=True,
            display="plain",
            score=True,
        )


def _summarise_log(log: Any) -> dict[str, Any]:
    """Counts for one screen log: refusal, compliance, post-tool CoT disclosure."""
    refused = 0
    poslens: list[int] = []
    post = readable = 0
    for sample in log.samples:
        value = next(iter((sample.scores or {}).values())).value
        refused += (value.get("refusal") or 0) > 0
        assistants = [
            m for m in sample.messages if getattr(m, "role", None) == "assistant"
        ]
        if (value.get("score") or 0) > 0:
            poslens.append(len(assistants))
        for i, message in enumerate(sample.messages):
            if getattr(message, "role", None) != "assistant":
                continue
            if i == 0 or sample.messages[i - 1].role != "tool":
                continue
            post += 1
            readable += any(
                getattr(b, "type", None) == "reasoning"
                and (getattr(b, "reasoning", "") or "").strip()
                and not getattr(b, "redacted", False)
                for b in (message.content if isinstance(message.content, list) else [])
            )
    return {
        "n": len(log.samples),
        "refused": refused,
        "complied": len(poslens),
        "positive_trajectory_lengths": sorted(poslens),
        "post_tool_turns": post,
        "post_tool_reasoning_readable": readable,
    }


def summarise() -> None:
    """Write a counts-only JSON from whatever screen logs exist."""
    from inspect_ai.log import read_eval_log

    out: dict[str, Any] = {
        "screen": {
            "benchmark": "agentharm harmful test_public",
            "n_per_model": N,
            "ground_truth": "AgentHarm published grader",
            "models": {},
        }
    }
    for directory in sorted(SCREEN_DIR.glob("*")):
        logs = glob.glob(str(directory / "*.eval"))
        if not logs:
            continue
        log = read_eval_log(logs[0])
        if log.status != "success":
            continue
        out["screen"]["models"][directory.name] = _summarise_log(log)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {OUT}")


def main() -> int:
    """Run the screen (unless --summarise-only) and write the counts JSON."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--summarise-only", action="store_true")
    args = parser.parse_args()
    if not args.summarise_only:
        run()
    summarise()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
