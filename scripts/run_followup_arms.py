"""Follow-up arms R1-R3: test the explanations for the positional results.

The long-horizon runs left two explanations standing that the logs could not settle:

- R1  claude-haiku-4.5 reasons at step 0 and never after a tool result. The request
      sent no interleaved-thinking header, and Anthropic documents that manual
      thinking budgets need that header to think between tool calls. R1 sends it.
- R2  the same haiku configuration as the original arm, re-run with every model call
      logged (Inspect logs raw payloads for only the first 5 calls by default), so the
      serving route and request are observable at every step. A replication.
- R3  gpt-oss-120b's decline and nemotron-3.5's ctf dip co-occur with OpenRouter
      routing between upstream providers. R3 pins the provider (no fallbacks) so
      routing and step position are no longer confounded.

Every arm keeps the original task, sample limit, token limit, timeout and retry
settings from scripts/run_*_families.sh, and writes to a staging root so that a
partially written log never enters a committed record. Move a completed arm into the
family's corpus directory only after its log reads `status=success`.

    set -a; source .env; set +a
    .venv/bin/python scripts/run_followup_arms.py --family agentharm
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STAGING = Path("data/inspect-runs-followup")
INTERLEAVED = {"anthropic-beta": "interleaved-thinking-2025-05-14"}


@dataclass(frozen=True)
class Family:
    """One task family with the settings its original arms were run under."""

    task: str
    task_args: dict[str, Any]
    score: bool
    max_connections: int
    timeout: int
    fail_on_error: float


@dataclass(frozen=True)
class Arm:
    """One follow-up arm: a model, its generate settings and its provider pin."""

    name: str
    model: str
    families: tuple[str, ...]
    reasoning_tokens: int | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    provider: dict[str, Any] | None = None


# Settings copied from scripts/run_agentic_arm.sh, run_ctf_families.sh and
# run_osbench_families.sh so the follow-up arms differ only in what they test.
FAMILIES = {
    "agentharm": Family(
        "inspect_evals/agentharm_benign", {"split": "test_public"}, False, 8, 180, 0.1
    ),
    "ctf": Family("inspect_evals/gdm_intercode_ctf", {}, True, 6, 240, 0.2),
    "osbench": Family("inspect_evals/agent_bench_os", {}, False, 4, 240, 0.2),
}

ALL = ("agentharm", "ctf", "osbench")
HAIKU = "openrouter/anthropic/claude-haiku-4.5"
GPT_OSS = "openrouter/openai/gpt-oss-120b"
NEMOTRON = "openrouter/nvidia/nemotron-3.5-lightning"


def _pin(slug: str, quantization: str | None = None) -> dict[str, Any]:
    """An OpenRouter provider preference that allows exactly one upstream."""
    pin: dict[str, Any] = {"order": [slug], "allow_fallbacks": False}
    if quantization:
        pin["quantizations"] = [quantization]
    return pin


ARMS = (
    Arm("claude-haiku-4.5-interleaved", HAIKU, ALL, 2048, INTERLEAVED),  # R1
    Arm("claude-haiku-4.5-replicate", HAIKU, ALL, 2048),  # R2
    # R3: the two upstreams the original gpt-oss arm was split across, both bf16.
    Arm("gpt-oss-120b-pin-deepinfra", GPT_OSS, ALL, provider=_pin("deepinfra", "bf16")),
    Arm("gpt-oss-120b-pin-akashml", GPT_OSS, ALL, provider=_pin("akashml", "bf16")),
    # R3: nemotron's ctf dip fell on DeepInfra-served calls; Phala served the rest.
    Arm("nemotron-3.5-pin-deepinfra", NEMOTRON, ("ctf",), provider=_pin("deepinfra")),
    Arm("nemotron-3.5-pin-phala", NEMOTRON, ("ctf",), provider=_pin("phala")),
)


def run_arm(arm: Arm, family_name: str, limit: int) -> str:
    """Run one arm on one family and return the log's status."""
    from inspect_ai import eval as inspect_eval

    family = FAMILIES[family_name]
    log_dir = STAGING / family_name / arm.name
    log_dir.mkdir(parents=True, exist_ok=True)
    model_args = {"provider": arm.provider} if arm.provider else {}
    logs = inspect_eval(
        family.task,
        model=arm.model,
        model_args=model_args,
        task_args=family.task_args,
        limit=limit,
        log_dir=str(log_dir),
        score=family.score,
        max_connections=family.max_connections,
        max_tokens=8192,
        timeout=family.timeout,
        max_retries=3,
        fail_on_error=family.fail_on_error,
        log_model_api=True,
        reasoning_tokens=arm.reasoning_tokens,
        extra_headers=arm.extra_headers or None,
        display="plain",
    )
    return str(logs[0].status)


def main() -> int:
    """Run every follow-up arm scheduled for one family, sequentially."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--family", choices=sorted(FAMILIES), required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--arms", nargs="*", help="subset of arm names to run")
    args = parser.parse_args()
    failed = 0
    for arm in ARMS:
        if args.family not in arm.families or (args.arms and arm.name not in args.arms):
            continue
        print(f"=== {arm.name} :: {args.family} n={args.limit}", flush=True)
        status = run_arm(arm, args.family, args.limit)
        print(f"### {arm.name} :: {args.family} status={status}", flush=True)
        failed += status != "success"
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
