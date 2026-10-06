"""The serving configuration of the monitor experiment's agent arms, from local logs.

The paper's argument is that a monitor result reported without its serving configuration
is uninterpretable. Its own monitor record reported none: no upstream provider, no
generate config, no request headers. This reads them out of the two agent logs that
are already on disk and writes them into the record, in the same shape and under the
same key names `report_turn_boundary.py` already uses for the header and route arms,
so one parser reads both.

No model call and no network: the logs were written on 2026-09-13 and are read as
they stand. Only counts, config keys and header KEY names are recorded - never a
header value, a prompt or a completion.

Each log holds two models' calls, the agent and AgentHarm's own semantic grader, so
every count is keyed by model. Pooling them would attribute the grader's upstream to
the agent: the raw pooled counts for the reasoning-on arm are DeepInfra 172, OpenAI
120 and Azure 82, of which only the DeepInfra calls are the agent's.

    .venv/bin/python scripts/report_monitor_provenance.py
    .venv/bin/python scripts/report_monitor_provenance.py --write

`--write` is append-only: the script refuses to run if any pre-existing value in the
record would change.
"""

from __future__ import annotations

import argparse
import copy
import glob
import json
from collections import Counter
from pathlib import Path
from typing import Any

from channels.provider_usage import request_config

LOGS = Path("data/monitor-experiment/agent-qwen3")
RECORD = Path("results/monitor_experiment_qwen3/monitor_record.json")

# The record's arm names, and the log directory each was run in.
ARM_DIRS = {
    "qwen3-on": "qwen3-on",
    "qwen3-nothink": "qwen3-nothink",
}


def _arm_provenance(arm_dir: Path) -> dict[str, Any]:
    """Providers, generate config and first-call request config for one arm."""
    from inspect_ai.log import read_eval_log, read_eval_log_samples

    paths = sorted(Path(p) for p in glob.glob(str(arm_dir / "*.eval")))
    if not paths:
        raise SystemExit(f"no .eval log under {arm_dir}")

    # Each log holds two models' calls: the agent under test and AgentHarm's own
    # semantic grader. Pooling them would attribute the grader's upstream to the
    # agent, so every count below is keyed by model and the agent's is picked out by
    # the eval header's own `model` field rather than by guessing from the name.
    providers: dict[str, Counter[str]] = {}
    generate: dict[str, Any] = {}
    first_call_config: dict[str, dict[str, Any]] = {}
    raw_logged: Counter[str] = Counter()
    raw_missing: Counter[str] = Counter()
    agent_model: str | None = None

    for path in paths:
        header = read_eval_log(str(path), header_only=True)
        agent_model = str(header.eval.model)
        config = header.eval.model_generate_config
        generate.setdefault("reasoning_effort", config.reasoning_effort)
        generate.setdefault("reasoning_tokens", config.reasoning_tokens)
        generate.setdefault("temperature", config.temperature)
        generate.setdefault(
            "extra_body_reasoning", (config.extra_body or {}).get("reasoning")
        )
        for sample in read_eval_log_samples(str(path), resolve_attachments=True):
            for event in getattr(sample, "events", []) or []:
                if getattr(event, "event", None) != "model":
                    continue
                model = str(getattr(event, "model", "not recorded"))
                call = getattr(event, "call", None)
                if call is None:
                    raw_missing[model] += 1
                    continue
                raw_logged[model] += 1
                response = call.response if isinstance(call.response, dict) else {}
                providers.setdefault(model, Counter())[
                    str(response.get("provider", "not recorded"))
                ] += 1
                if model not in first_call_config:
                    first_call_config[model] = request_config(call.request)

    if agent_model is None:
        raise SystemExit(f"{arm_dir}: no eval header found")

    other = sorted(model for model in providers if model != agent_model)
    return {
        "logs": [path.name for path in paths],
        "agent_model": agent_model,
        "providers": dict(providers.get(agent_model, Counter())),
        "generate_config": generate,
        "first_call_config": first_call_config.get(agent_model),
        "calls_with_raw_logged": raw_logged[agent_model],
        "calls_without_raw_logged": raw_missing[agent_model],
        # The grader is ground truth for every positive, so its model id and upstream
        # belong in the record for the same reason the agent's do.
        "grader_models": {
            model: {
                "providers": dict(providers[model]),
                "calls_with_raw_logged": raw_logged[model],
            }
            for model in other
        },
    }


def _describe(arm_name: str, provenance: dict[str, Any]) -> None:
    """Print one arm's provenance, so the text can be written from the output."""
    providers = provenance["providers"]
    total = sum(providers.values())
    print(f"  {arm_name}")
    print(f"    logs: {', '.join(provenance['logs'])}")
    print(f"    agent model: {provenance['agent_model']}")
    if providers:
        pinned = len(providers) == 1 or (
            len(providers) == 2 and "not recorded" in providers
        )
        served = ", ".join(f"{name} {count}" for name, count in sorted(
            providers.items(), key=lambda item: -item[1]
        ))
        print(f"    upstream over {total} logged call(s): {served}")
        print(f"    single upstream: {'yes' if pinned else 'NO - not pinned'}")
    else:
        print("    upstream: NOT RECORDED in these logs")
    print(f"    generate config: {json.dumps(provenance['generate_config'])}")
    first = provenance["first_call_config"] or {}
    print(f"    header keys: {', '.join(first.get('header_keys', [])) or 'none'}")
    print(
        f"    extra_body keys: "
        f"{', '.join(first.get('extra_body_keys', [])) or 'none'}"
    )
    for model, block in provenance["grader_models"].items():
        served = ", ".join(
            f"{name} {count}" for name, count in sorted(block["providers"].items())
        )
        print(f"    grader {model}: {block['calls_with_raw_logged']} call(s); {served}")


def main() -> int:
    """Print each arm's serving configuration; with --write, append it to the record."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="append the provenance blocks to the record (append-only)",
    )
    args = parser.parse_args()

    if not RECORD.exists():
        print(f"no record at {RECORD}")
        return 1

    payload = json.loads(RECORD.read_text())
    before = copy.deepcopy(payload)
    arms = payload["monitor_experiment"]["arms"]

    print(f"monitor-experiment agent arms, serving configuration from {LOGS}")
    for arm_name, dir_name in ARM_DIRS.items():
        if arm_name not in arms:
            raise SystemExit(f"record has no arm {arm_name!r}")
        provenance = _arm_provenance(LOGS / dir_name)
        _describe(arm_name, provenance)
        arms[arm_name].update(
            {
                "providers": provenance["providers"],
                "generate_config": provenance["generate_config"],
                "first_call_config": provenance["first_call_config"],
                "grader_models": provenance["grader_models"],
            }
        )

    if not args.write:
        return 0

    _assert_append_only(before, payload)
    RECORD.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {RECORD}")
    return 0


def _assert_append_only(before: Any, after: Any, path: str = "") -> None:
    """Raise unless `after` only adds keys to `before`. See the module docstring."""
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


if __name__ == "__main__":
    raise SystemExit(main())
