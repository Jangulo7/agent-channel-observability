"""Long-horizon coverage from the SWE-bench arms: does disclosure decay with depth?

Reads the staged SWE-bench logs (data/inspect-runs-swebench/<arm>/) and writes a
counts-only record: per arm the trajectory-length distribution, how many trajectories
were right-censored at the message limit, and the readable-reasoning share by step and
depth bucket, cross-checked against the provider's reasoning-token count. No SWE-bench
repository text is read or written - only per-turn classification counts.

    .venv/bin/python scripts/report_swebench_longhorizon.py
"""

from __future__ import annotations

import argparse
import copy
import glob
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

LOGS = Path("data/inspect-runs-swebench")
OUT = Path("results/swebench_longhorizon/longhorizon.json")
BUCKETS = [(0, 9), (10, 19), (20, 29), (30, 39), (40, 999)]


def _readable(message: Any) -> bool:
    """Whether an assistant turn carries a non-blank, non-redacted reasoning block."""
    content = message.content if isinstance(message.content, list) else []
    return any(
        getattr(b, "type", None) == "reasoning"
        and (getattr(b, "reasoning", "") or "").strip()
        and not getattr(b, "redacted", False)
        for b in content
    )


def _arm(log: Any) -> dict[str, Any]:
    """Trajectory lengths and readable-reasoning share by step for one arm."""
    lengths: list[int] = []
    censored = 0
    by_step: dict[int, list[int]] = defaultdict(lambda: [0, 0, 0])  # n, readable, rt>0
    for sample in log.samples:
        assistants = [
            m for m in sample.messages if getattr(m, "role", None) == "assistant"
        ]
        lengths.append(len(assistants))
        limit = getattr(sample, "limit", None)
        censored += getattr(limit, "type", None) == "message"
        events = {
            e.output.message.id: e
            for e in sample.events
            if type(e).__name__ == "ModelEvent" and e.output and e.output.choices
        }
        for step, message in enumerate(assistants):
            event = events.get(message.id)
            usage = event.output.usage if event and event.output else None
            tokens = getattr(usage, "reasoning_tokens", None) or 0
            cell = by_step[step]
            cell[0] += 1
            cell[1] += _readable(message)
            cell[2] += tokens > 0
    n = len(lengths)
    buckets = {}
    for lo, hi in BUCKETS:
        rows = [c for s, c in by_step.items() if lo <= s <= hi]
        total = sum(c[0] for c in rows)
        if total:
            key = f"{lo}-{hi if hi < 999 else 'max'}"
            buckets[key] = {"n": total, "readable": sum(c[1] for c in rows),
                            "readable_share": sum(c[1] for c in rows) / total}
    turns_total = sum(c[0] for c in by_step.values())
    return {
        "n_trajectories": n,
        "message_limit_hits": censored,
        "turns_median": st.median(lengths),
        "turns_max": max(lengths),
        "turns_all": sorted(lengths),
        "deepest_step": max(by_step),
        "readable_overall": sum(c[1] for c in by_step.values()) / turns_total,
        "by_step": {
            str(s): {"n": c[0], "readable": c[1], "reasoning_tokens_gt0": c[2]}
            for s, c in sorted(by_step.items())
        },
        "by_depth_bucket": buckets,
        "note": (
            "n<=10 per step (below MIN_CELL_N=30): suggestive, not powered; "
            "message-limit-hit trajectories are right-censored, so depth is a floor"
        ),
    }


def _arm_providers(log_path: str) -> dict[str, dict[str, int]]:
    """Upstream providers per model for one arm's log, keyed by model id.

    The depth result is route-conditional: the same model reads 0 of 625 turns on
    one upstream and all of them on another (results/turn_boundary_followup.json).
    A readable share reported without its upstream therefore describes no route, and
    an arm served by several upstreams reports an average over them rather than a
    property of depth.
    """
    from inspect_ai.log import read_eval_log_samples

    counts: dict[str, Counter[str]] = {}
    for sample in read_eval_log_samples(log_path, resolve_attachments=True):
        for event in getattr(sample, "events", []) or []:
            if getattr(event, "event", None) != "model":
                continue
            call = getattr(event, "call", None)
            if call is None:
                continue
            response = call.response if isinstance(call.response, dict) else {}
            model = str(getattr(event, "model", "not recorded"))
            counts.setdefault(model, Counter())[
                str(response.get("provider", "not recorded"))
            ] += 1
    return {model: dict(tally) for model, tally in counts.items()}


def _report_providers(write: bool) -> int:
    """Print each arm's upstream providers; with `write`, append them to the record.

    Append-only: the run aborts if any pre-existing value in the record would
    change, so the measured readable shares cannot be disturbed by adding their
    provenance.
    """
    if not OUT.exists():
        print(f"no record at {OUT}; run without --providers first")
        return 1
    payload = json.loads(OUT.read_text())
    before = copy.deepcopy(payload)
    arms = payload["swebench_longhorizon"]["arms"]

    for arm_name, block in arms.items():
        logs = sorted(glob.glob(str(LOGS / arm_name / "*.eval")))
        if not logs:
            print(f"{arm_name}: no log under {LOGS / arm_name}")
            continue
        from inspect_ai.log import read_eval_log

        agent_model = str(read_eval_log(logs[0], header_only=True).eval.model)
        per_model = _arm_providers(logs[0])
        # Take the agent from the eval header, never by matching the arm name
        # against a model id: a log may hold a grader's calls too, and attributing
        # the grader's upstream to the agent is exactly the error this records
        # against.
        providers = per_model.get(agent_model, {})
        if not providers:
            print(
                f"{arm_name}: no logged call for the eval model {agent_model}; "
                f"models seen: {sorted(per_model)}"
            )
            continue
        other = sorted(model for model in per_model if model != agent_model)
        if other:
            block["other_models_in_log"] = {
                model: per_model[model] for model in other
            }
        block["providers"] = providers
        total = sum(providers.values())
        served = ", ".join(
            f"{name} {count}" for name, count in sorted(
                providers.items(), key=lambda item: -item[1]
            )
        )
        pinned = "pinned" if len(providers) == 1 else "NOT pinned"
        print(f"{arm_name}: {total} logged call(s), {pinned} - {served}")

    if not write:
        return 0
    _assert_append_only(before, payload)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {OUT}")
    return 0


def _assert_append_only(before: Any, after: Any, path: str = "") -> None:
    """Raise unless `after` only adds keys to `before`."""
    if isinstance(before, dict):
        if not isinstance(after, dict):
            raise SystemExit(f"{path or '<root>'}: a mapping became {type(after)}")
        for key, value in before.items():
            if key not in after:
                raise SystemExit(f"{path}/{key}: pre-existing key was removed")
            _assert_append_only(value, after[key], f"{path}/{key}")
    elif isinstance(before, list):
        if not isinstance(after, list) or len(after) != len(before):
            raise SystemExit(f"{path}: a list changed length or type")
        for index, value in enumerate(before):
            _assert_append_only(value, after[index], f"{path}[{index}]")
    elif before != after:
        raise SystemExit(f"{path}: {before!r} would become {after!r}")


def main() -> int:
    """Write the long-horizon coverage record for every SWE-bench arm."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--providers",
        action="store_true",
        help="report each arm's upstream providers instead of rebuilding the record",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="with --providers, append the providers blocks to the record",
    )
    args = parser.parse_args()
    if args.providers:
        return _report_providers(args.write)

    from inspect_ai.log import read_eval_log

    record: dict[str, Any] = {"swebench_longhorizon": {
        "benchmark": "SWE-bench Verified (score off; reasoning channel only)",
        "arms": {}}}
    for arm_dir in sorted(LOGS.iterdir()):
        logs = glob.glob(str(arm_dir / "*.eval"))
        if not logs:
            continue
        log = read_eval_log(logs[0])
        if log.status != "success":
            print(f"skip {arm_dir.name}: {log.status}")
            continue
        record["swebench_longhorizon"]["arms"][arm_dir.name] = _arm(log)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2) + "\n")
    print(f"wrote {OUT}")
    for arm, block in record["swebench_longhorizon"]["arms"].items():
        print(f"\n{arm}: n={block['n_trajectories']} "
              f"median_turns={block['turns_median']} max={block['turns_max']} "
              f"censored={block['message_limit_hits']} "
              f"readable_overall={block['readable_overall']:.3f}")
        for key, b in block["by_depth_bucket"].items():
            share = b["readable_share"]
            print(f"   steps {key:>6}: readable {b['readable']}/{b['n']}={share:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
