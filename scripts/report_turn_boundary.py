"""Reasoning at the turn boundary: what follows a user message vs a tool result.

    uv run python scripts/report_turn_boundary.py [--json PATH]

What this establishes. For every (task family, arm) in the three agentic
families, assistant turns are split by the role of the message immediately
before them (step 0, the first move, is reported separately whatever precedes
it). For each group it counts how many turns carry readable reasoning
(RAW_PRESENT, classified by `channels.coverage`), redacted reasoning, a summary
only, or an empty/absent block, and how many had provider-billed
`reasoning_tokens > 0` (ModelEvent.output.usage, paired by position with the
assistant messages). Where a turn has no reasoning block AND the provider
reported zero reasoning tokens, the logs show no deliberation on that turn under
the run's request config, visible or billed-but-hidden. (For claude-haiku-4.5
this holds on every turn after a tool result, while turns after a user message
reason readably with tokens billed.) The request config
(generate-config reasoning settings, extra_body reasoning, header KEY names) and
the upstream provider names are reported so the condition is stated with it.

What it cannot establish. Why the provider did not reason. The logs show the
request as sent to OpenRouter and the usage OpenRouter returned; whatever
OpenRouter or the upstream provider did with the reasoning setting after that
is not observable here, and the token count is the provider's own report, not
an independent measurement. Raw calls (request, response, provider) are logged
only for the first calls of each sample, so the config and provider columns
describe those calls, not every call; the logged / not-logged split is printed.

Counts only: no message, reasoning or tool text is read into the output, and
header values are never printed.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from channels.coverage import observe_turns, reasoning_blocks
from channels.loaders.inspect_logs import InspectLogLoader
from channels.schema import ReasoningState

#: Task families, in the order they were run; one subdirectory per arm.
FAMILIES = {
    "agentharm": Path("data/inspect-runs-agentic"),
    "intercode_ctf": Path("data/inspect-runs-ctf"),
    "agent_bench_os": Path("data/inspect-runs-osbench"),
}

#: Header key fragments that would turn on Anthropic interleaved thinking.
INTERLEAVED_HEADER_MARKERS = ("anthropic-beta", "interleaved")

STEP0 = "step 0"


@dataclass
class BucketCounts:
    """Counts for one (family, arm, preceding-role) group of assistant turns."""

    n: int = 0
    raw_present: int = 0
    redacted: int = 0
    summary_only: int = 0
    absent_no_block: int = 0
    absent_empty_block: int = 0
    usage_recorded: int = 0
    reasoning_tokens_gt0: int = 0


@dataclass
class ArmReport:
    """Everything counted for one arm in one family."""

    buckets: dict[str, BucketCounts] = field(default_factory=dict)
    n_samples: int = 0
    unpaired_trailing_calls: int = 0
    unpaired_turns: int = 0
    pairing_role_mismatches: int = 0
    calls_with_raw_logged: int = 0
    calls_without_raw_logged: int = 0
    providers: Counter[str] = field(default_factory=Counter)
    first_call_config: dict[str, Any] | None = None


def preceding_roles(messages: Sequence[Any]) -> list[tuple[int, str]]:
    """(step index, bucket) for each assistant message, in message order."""
    contexts: list[tuple[int, str]] = []
    step = 0
    for index, message in enumerate(messages):
        if getattr(message, "role", None) != "assistant":
            continue
        previous = getattr(messages[index - 1], "role", None) if index else None
        contexts.append((step, STEP0 if step == 0 else f"after {previous}"))
        step += 1
    return contexts


def pair_usage(
    n_turns: int, model_events: Sequence[Any]
) -> tuple[list[int | None], int, int]:
    """Pair assistant turns with model calls by position.

    Returns per-turn reasoning_tokens (None where no call or no usage was
    recorded), the count of trailing calls with no assistant turn, and the count
    of turns with no call. Unpaired items are counted, never silently dropped.
    """
    tokens: list[int | None] = []
    for event in model_events[:n_turns]:
        usage = getattr(getattr(event, "output", None), "usage", None)
        value = getattr(usage, "reasoning_tokens", None) if usage else None
        tokens.append(int(value) if value is not None else None)
    unpaired_turns = max(0, n_turns - len(model_events))
    tokens.extend([None] * unpaired_turns)
    return tokens, max(0, len(model_events) - n_turns), unpaired_turns


def _absent_kind(message: Any) -> str:
    """Whether an ABSENT turn had no reasoning block or only empty ones."""
    return "absent_empty_block" if reasoning_blocks(message) else "absent_no_block"


def _count_turn(
    bucket: BucketCounts, state: ReasoningState, message: Any, tokens: int | None
) -> None:
    """Add one assistant turn to its bucket."""
    bucket.n += 1
    if state is ReasoningState.RAW_PRESENT:
        bucket.raw_present += 1
    elif state is ReasoningState.REDACTED:
        bucket.redacted += 1
    elif state is ReasoningState.SUMMARY_ONLY:
        bucket.summary_only += 1
    else:
        kind = _absent_kind(message)
        setattr(bucket, kind, getattr(bucket, kind) + 1)
    if tokens is not None:
        bucket.usage_recorded += 1
        bucket.reasoning_tokens_gt0 += tokens > 0


def count_sample(report: ArmReport, sample: Any, arm: str, task_class: str) -> None:
    """Count one sample's assistant turns into the arm report."""
    messages = list(getattr(sample, "messages", None) or [])
    assistants = [m for m in messages if getattr(m, "role", None) == "assistant"]
    states = [o.state for o in observe_turns(sample, arm, task_class)]
    events = [e for e in getattr(sample, "events", []) if e.event == "model"]
    tokens, trailing, missing = pair_usage(len(assistants), events)
    report.n_samples += 1
    report.unpaired_trailing_calls += trailing
    report.unpaired_turns += missing
    contexts = preceding_roles(messages)
    for (_, bucket), message, state, used in zip(
        contexts, assistants, states, tokens, strict=True
    ):
        counts = report.buckets.setdefault(bucket, BucketCounts())
        _count_turn(counts, state, message, used)
    _check_pairing(report, messages, events)
    _count_calls(report, events)


def _check_pairing(
    report: ArmReport, messages: Sequence[Any], events: Sequence[Any]
) -> None:
    """Count pairs whose call input does not end in the turn's preceding role."""
    indices = [
        i for i, m in enumerate(messages) if getattr(m, "role", None) == "assistant"
    ]
    for index, event in zip(indices, events, strict=False):
        expected = getattr(messages[index - 1], "role", None) if index else None
        inputs = getattr(event, "input", None) or []
        observed = getattr(inputs[-1], "role", None) if inputs else None
        report.pairing_role_mismatches += expected != observed


def _count_calls(report: ArmReport, events: Iterable[Any]) -> None:
    """Tally provider names and whether the raw call was logged."""
    for event in events:
        call = getattr(event, "call", None)
        if call is None:
            report.calls_without_raw_logged += 1
            continue
        report.calls_with_raw_logged += 1
        response = call.response if isinstance(call.response, dict) else {}
        report.providers[str(response.get("provider", "not recorded"))] += 1
        if report.first_call_config is None:
            report.first_call_config = request_config(call.request)


def request_config(request: dict[str, Any]) -> dict[str, Any]:
    """Reasoning settings and header KEY names from one logged request; no values."""
    extra_body = request.get("extra_body") or {}
    header_keys = sorted((request.get("extra_headers") or {}).keys())
    return {
        "extra_body_keys": sorted(extra_body.keys()),
        "extra_body_reasoning": extra_body.get("reasoning"),
        "request_reasoning_effort": request.get("reasoning_effort"),
        "header_keys": header_keys,
        "interleaved_or_beta_header_key_present": any(
            marker in key.lower()
            for key in header_keys
            for marker in INTERLEAVED_HEADER_MARKERS
        ),
    }


def arm_report(paths: Sequence[Path], arm: str) -> tuple[ArmReport, dict[str, Any]]:
    """Count every complete log for one arm; return it with its generate config."""
    from inspect_ai.log import read_eval_log, read_eval_log_samples

    report = ArmReport()
    generate: dict[str, Any] = {}
    for path in paths:
        header = read_eval_log(str(path), header_only=True)
        config = header.eval.model_generate_config
        generate.setdefault("reasoning_effort", config.reasoning_effort)
        generate.setdefault("reasoning_tokens", config.reasoning_tokens)
        generate.setdefault(
            "extra_body_reasoning", (config.extra_body or {}).get("reasoning")
        )
        task_class = str(header.eval.task).rsplit("/", maxsplit=1)[-1]
        for sample in read_eval_log_samples(str(path), resolve_attachments=True):
            count_sample(report, sample, arm, task_class)
    return report, generate


def collect() -> dict[str, dict[str, dict[str, Any]]]:
    """Run every family and arm present on disk; absent families are named."""
    results: dict[str, dict[str, dict[str, Any]]] = {}
    for family, root in FAMILIES.items():
        loader = InspectLogLoader(root, label_by_directory=True)
        by_arm: dict[str, list[Path]] = {}
        for path in loader.log_paths():
            by_arm.setdefault(path.parent.name, []).append(path)
        if not by_arm:
            print(f"_{family}: no complete logs under {root}_\n")
            continue
        results[family] = {}
        for arm, paths in sorted(by_arm.items()):
            report, generate = arm_report(paths, arm)
            results[family][arm] = {"generate_config": generate, **asdict(report)}
            # asdict rebuilds a Counter from (key, value) pairs, counting the
            # pairs; the provider tally is restored from the source object.
            results[family][arm]["providers"] = dict(report.providers)
            results[family][arm]["incomplete_logs_excluded"] = len(
                [p for p in loader.incomplete_logs() if p.parent.name == arm]
            )
    return results


def _share(part: int, whole: int) -> str:
    """A share with its counts, or n/a for an empty denominator."""
    return f"{part / whole:.3f} ({part}/{whole})" if whole else "n/a (0/0)"


def _turn_row(arm: str, name: str, b: dict[str, int]) -> str:
    """One markdown row of turn counts."""
    absent = b["absent_no_block"] + b["absent_empty_block"]
    cells = [
        f"`{arm}`", name, str(b["n"]), _share(b["raw_present"], b["n"]),
        _share(b["redacted"], b["n"]), _share(b["summary_only"], b["n"]),
        _share(absent, b["n"]),
        _share(b["reasoning_tokens_gt0"], b["usage_recorded"]),
    ]
    return "| " + " | ".join(cells) + " |"


def print_turn_tables(results: dict[str, dict[str, dict[str, Any]]]) -> None:
    """One markdown table per family: turns by preceding role."""
    for family, arms in results.items():
        print(f"### {family}: assistant turns by preceding message role\n")
        print("| arm | preceding | n | readable | redacted | summary only "
              "| empty/absent block | reasoning_tokens > 0 |")
        print("|---|---|---|---|---|---|---|---|")
        for arm, data in arms.items():
            for name in sorted(data["buckets"], key=lambda b: (b != STEP0, b)):
                print(_turn_row(arm, name, data["buckets"][name]))
        print()


def _config_row(family: str, arm: str, data: dict[str, Any]) -> str:
    """One markdown row of request config, providers and pairing bookkeeping."""
    gen, first = data["generate_config"], data["first_call_config"] or {}
    providers = ", ".join(
        f"{name} {count}" for name, count in sorted(data["providers"].items())
    )
    cells = [
        family, f"`{arm}`", str(gen.get("reasoning_effort")),
        str(gen.get("reasoning_tokens")), json.dumps(gen.get("extra_body_reasoning")),
        json.dumps(first.get("extra_body_reasoning")),
        ", ".join(first.get("header_keys", [])) or "none",
        str(first.get("interleaved_or_beta_header_key_present")),
        providers or "none",
        f"{data['calls_with_raw_logged']} / {data['calls_without_raw_logged']}",
        f"{data['unpaired_trailing_calls']} / {data['unpaired_turns']}",
        str(data["pairing_role_mismatches"]),
    ]
    return "| " + " | ".join(cells) + " |"


def print_config_tables(results: dict[str, dict[str, dict[str, Any]]]) -> None:
    """Request config, provider distribution and pairing bookkeeping per arm."""
    print("### request config (first logged call) and upstream providers\n")
    print("| family | arm | gen reasoning_effort | gen reasoning_tokens "
          "| gen extra_body.reasoning | request extra_body.reasoning | header keys "
          "| beta/interleaved key | providers (logged calls) "
          "| calls logged / not | unpaired calls / turns | role mismatches |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for family, arms in results.items():
        for arm, data in arms.items():
            print(_config_row(family, arm, data))
    print()


def main(argv: list[str] | None = None) -> int:
    """Print the turn-boundary tables; optionally write the counts as JSON."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    results = collect()
    if not results:
        print("no agentic corpora available")
        return 2
    print_turn_tables(results)
    print_config_tables(results)
    if args.json is not None:
        text = json.dumps(results, indent=2, sort_keys=True, default=str)
        args.json.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
