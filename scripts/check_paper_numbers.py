"""Check every record-derived number in the paper against the record it came from.

The paper claims that its numbers come from committed records. Before this script that
was a claim about how the paper was written, not a property anyone could check, and it
had already failed once: the headline turn count was assembled from a different set of
corpora than the findings it introduced.

The registry below maps each number the paper reports to the record and derivation it
comes from. `--self-check` recomputes every derivation and compares it with the expected
rendering, which needs only the records and so always runs in CI. `--check` additionally
reads the manuscript and reports any registered number that is missing from it, which
needs the .tex and is skipped when it is absent.

This is deliberately a checker rather than a macro pipeline. Emitting every number as a
LaTeX macro would guarantee the same thing, but it would rewrite every number in a
manuscript that has already been circulated, and the risk of introducing a new error
while fixing old ones is not worth the elegance. A checker gives the same drift
guarantee at a fraction of the diff.

    .venv/bin/python scripts/check_paper_numbers.py --self-check
    .venv/bin/python scripts/check_paper_numbers.py --check
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from channels._vendored_stats import newcombe_difference, wilson_interval

RESULTS = Path("results")
PAPER = Path(".other-experiments/paper/coverage_not_faithfulness/main.tex")


def _load(name: str) -> Any:
    return json.loads((RESULTS / name).read_text())


def _sweep() -> Any:
    return _load("observability_record_reasoning.json")["observability_record"]


def _followup() -> Any:
    return _load("turn_boundary_followup.json")


def _monitor() -> Any:
    return _load("monitor_experiment_qwen3/monitor_record.json")["monitor_experiment"]


def _swe() -> Any:
    return _load("swebench_longhorizon/longhorizon.json")["swebench_longhorizon"]


def _followup_bucket(arm: str, bucket: str, field: str) -> int:
    """Sum one bucket field across task families for one follow-up arm."""
    total = 0
    for family, arms in _followup().items():
        if not isinstance(arms, dict) or family == "schema_version":
            continue
        block = arms.get(arm)
        if block and bucket in block["buckets"]:
            total += block["buckets"][bucket][field]
    return total


def _followup_whole(arm: str, field: str) -> int:
    """Sum one bucket field over every bucket and family for one follow-up arm."""
    total = 0
    for family, arms in _followup().items():
        if not isinstance(arms, dict) or family == "schema_version":
            continue
        block = arms.get(arm)
        if block:
            total += sum(bucket[field] for bucket in block["buckets"].values())
    return total


def _followup_providers(arm: str) -> dict[str, int]:
    """Pooled upstream provider counts for one follow-up arm."""
    pooled: dict[str, int] = {}
    for family, arms in _followup().items():
        if not isinstance(arms, dict) or family == "schema_version":
            continue
        block = arms.get(arm)
        if block:
            for name, count in (block.get("providers") or {}).items():
                pooled[name] = pooled.get(name, 0) + count
    return pooled


def _share(arm: str) -> str:
    """Readable share of one follow-up arm's post-tool-result turns, to 3 places."""
    readable = _followup_bucket(arm, "after tool", "raw_present")
    total = _followup_bucket(arm, "after tool", "n")
    return f"{readable / total:.3f}"


def _recall(arm: str, channel: str, step: int) -> float:
    points = _monitor()["arms"][arm]["recall_by_step"][channel]
    return next(p["recall"] for p in points if p["step_index"] == step)


def _caught(arm: str, channel: str, step: int) -> tuple[int, int]:
    points = _monitor()["arms"][arm]["recall_by_step"][channel]
    point = next(p for p in points if p["step_index"] == step)
    return point["n_caught_by_here"], point["n_positive_reaching"]


def _flag_totals(arm: str, channel: str) -> dict[str, int]:
    blocks = _monitor()["arms"][arm]["flag_rate_by_step"][channel]
    totals = {"flag": 0, "clear": 0, "abstain": 0}
    for counts in blocks.values():
        for key in totals:
            totals[key] += counts[key]
    return totals


@dataclass(frozen=True)
class Entry:
    """One number the paper reports, and where it comes from."""

    label: str
    record: str
    derivation: Callable[[], str]
    expected: str
    # Literal as it must appear in the .tex. None means "not searchable as plain text"
    # (a derived range, or a number that appears only inside a macro or a table cell
    # whose formatting varies); --self-check still verifies the derivation.
    in_tex: str | None = None


def registry() -> list[Entry]:
    """Every record-derived number in the paper, with its derivation."""
    entries: list[Entry] = []

    def add(
        label: str,
        record: str,
        derivation: Callable[[], str],
        expected: str,
        in_tex: str | None = None,
    ) -> None:
        entries.append(Entry(label, record, derivation, expected, in_tex))

    # --- Header contrast (section 4.1) -----------------------------------------
    add("haiku header off, post-tool readable", "turn_boundary_followup",
        lambda: str(_followup_bucket("claude-haiku-4.5-replicate", "after tool",
                                     "raw_present")), "0", "0 of 661")
    add("haiku header off, post-tool n", "turn_boundary_followup",
        lambda: str(_followup_bucket("claude-haiku-4.5-replicate", "after tool", "n")),
        "661", "661")
    add("haiku header off, post-tool reasoning tokens > 0", "turn_boundary_followup",
        lambda: str(_followup_bucket("claude-haiku-4.5-replicate", "after tool",
                                     "reasoning_tokens_gt0")), "0")
    add("haiku header on, post-tool readable", "turn_boundary_followup",
        lambda: str(_followup_bucket("claude-haiku-4.5-interleaved", "after tool",
                                     "raw_present")), "667", "667 of 667")
    add("haiku upstream, Bedrock calls", "turn_boundary_followup",
        lambda: str(sum(
            _followup_providers(arm).get("Amazon Bedrock", 0)
            for arm in ("claude-haiku-4.5-replicate", "claude-haiku-4.5-interleaved")
        )), "1674", "1{,}674")
    add("haiku upstream, total calls", "turn_boundary_followup",
        lambda: str(sum(
            sum(_followup_providers(arm).values())
            for arm in ("claude-haiku-4.5-replicate", "claude-haiku-4.5-interleaved")
        )), "1675", "1{,}675")

    # --- Route contrast (section 4.1) ------------------------------------------
    add("nemotron DeepInfra, whole channel readable", "turn_boundary_followup",
        lambda: str(_followup_whole("nemotron-3.5-pin-deepinfra", "raw_present")),
        "0", "0 of 625")
    add("nemotron DeepInfra, whole channel n", "turn_boundary_followup",
        lambda: str(_followup_whole("nemotron-3.5-pin-deepinfra", "n")), "625", "625")
    add("nemotron Phala, whole channel readable", "turn_boundary_followup",
        lambda: str(_followup_whole("nemotron-3.5-pin-phala", "raw_present")),
        "421", "421 of 421")
    add("nemotron DeepInfra, post-tool n", "turn_boundary_followup",
        lambda: str(_followup_bucket("nemotron-3.5-pin-deepinfra", "after tool", "n")),
        "559", "0 of 559")
    add("nemotron Phala, post-tool readable", "turn_boundary_followup",
        lambda: str(_followup_bucket("nemotron-3.5-pin-phala", "after tool",
                                     "raw_present")), "355", "355 of 355")
    add("nemotron DeepInfra, step 0 n", "turn_boundary_followup",
        lambda: str(_followup_bucket("nemotron-3.5-pin-deepinfra", "step 0", "n")),
        "50", "0 of 50 at step 0")
    add("nemotron DeepInfra, after-user n", "turn_boundary_followup",
        lambda: str(_followup_bucket("nemotron-3.5-pin-deepinfra", "after user", "n")),
        "16", "0 of 16 after a user turn")

    # --- gpt-oss partial route effect (section 4.1) ------------------------------
    add("gpt-oss AkashML, post-tool readable", "turn_boundary_followup",
        lambda: str(_followup_bucket("gpt-oss-120b-pin-akashml", "after tool",
                                     "raw_present")), "669", "669 of 802")
    add("gpt-oss AkashML, post-tool share", "turn_boundary_followup",
        lambda: _share("gpt-oss-120b-pin-akashml"), "0.834", "0.834")
    add("gpt-oss DeepInfra, post-tool readable", "turn_boundary_followup",
        lambda: str(_followup_bucket("gpt-oss-120b-pin-deepinfra", "after tool",
                                     "raw_present")), "671", "671 of 728")
    add("gpt-oss DeepInfra, post-tool share", "turn_boundary_followup",
        lambda: _share("gpt-oss-120b-pin-deepinfra"), "0.922", "0.922")

    # --- Produced but unreadable (section 4.3) ----------------------------------
    for arm, expected, tex in (
        ("qwen3-32b", "10", "10 of 61"),
        ("gpt-oss-120b", "5", "5 of 485"),
        ("nemotron-3.5-lightning", "3", "3 of 530"),
    ):
        add(f"SWE produced-but-unreadable, {arm}", "swebench_longhorizon",
            lambda arm=arm: str(sum(  # type: ignore[misc]
                step["reasoning_tokens_gt0"] - step["readable"]
                for step in _swe()["arms"][arm]["by_step"].values()
            )), expected, tex)
    add("gpt-oss DeepInfra, empty billed blocks", "turn_boundary_followup",
        lambda: str(_followup_bucket("gpt-oss-120b-pin-deepinfra", "after tool",
                                     "absent_empty_block")), "4", "4 of 728")
    add("gpt-oss AkashML, tokens without block", "turn_boundary_followup",
        lambda: str(
            _followup_bucket("gpt-oss-120b-pin-akashml", "after tool",
                             "reasoning_tokens_gt0")
            - _followup_bucket("gpt-oss-120b-pin-akashml", "after tool", "raw_present")
        ), "1", "1 of 802")

    # --- Sweep (section 4.1, figure 1) ------------------------------------------
    add("sweep token-accounting inconsistencies", "observability_record",
        lambda: str(sum(
            cell["token_accounting_inconsistent"]
            for cell in _sweep()["emission"]["cells"]
        )), "58", "58 turns")

    # --- Monitor recall (section 4.2, table 1) ----------------------------------
    table_one = (
        ("qwen3-on", "reasoning", ("0.929", "0.952", "1.000", "1.000", "1.000")),
        ("qwen3-nothink", "reasoning", ("0.000", "0.000", "0.062", "0.167", "0.154")),
        ("qwen3-on", "action", ("0.476", "0.690", "0.828", "0.909", "0.875")),
        ("qwen3-nothink", "action", ("0.263", "0.605", "0.750", "0.708", "0.769")),
    )
    for arm, channel, cells in table_one:
        for step, expected in enumerate(cells):
            add(
                f"table 1: {arm} {channel} step {step}",
                "monitor_experiment_qwen3",
                lambda a=arm, c=channel, s=step: f"{_recall(a, c, s):.3f}",  # type: ignore[misc]
                expected,
                expected,
            )

    add("step-0 CoT visible k/n", "monitor_experiment_qwen3",
        lambda: "{}/{}".format(*_caught("qwen3-on", "reasoning", 0)), "39/42", "39/42")
    add("step-0 CoT dark k/n", "monitor_experiment_qwen3",
        lambda: "{}/{}".format(*_caught("qwen3-nothink", "reasoning", 0)),
        "0/38", "0/38")
    add("step-2 CoT visible survivors", "monitor_experiment_qwen3",
        lambda: str(_caught("qwen3-on", "reasoning", 2)[1]), "29",
        "all 29 trajectories still running at step 2")
    add("visible-arm reasoning abstentions", "monitor_experiment_qwen3",
        lambda: "{}/{}".format(
            _flag_totals("qwen3-on", "reasoning")["abstain"],
            sum(_flag_totals("qwen3-on", "reasoning").values()),
        ), "0/161", "0/161")
    add("dark-arm reasoning abstentions", "monitor_experiment_qwen3",
        lambda: "{}/{}".format(
            _flag_totals("qwen3-nothink", "reasoning")["abstain"],
            sum(_flag_totals("qwen3-nothink", "reasoning").values()),
        ), "144/155", "144/155")
    add("dark-arm reasoning turns with content", "monitor_experiment_qwen3",
        lambda: str(
            sum(_flag_totals("qwen3-nothink", "reasoning").values())
            - _flag_totals("qwen3-nothink", "reasoning")["abstain"]
        ), "11", "11 of the 155")

    # --- Newcombe intervals (section 4.2) ---------------------------------------
    def newcombe(a: tuple[int, int], b: tuple[int, int]) -> str:
        interval = newcombe_difference(a[0], a[1], b[0], b[1])
        return f"[{interval.low:.3f}, {interval.high:.3f}]"

    add("Newcombe, step-0 CoT difference", "monitor_experiment_qwen3",
        lambda: newcombe(_caught("qwen3-on", "reasoning", 0),
                         _caught("qwen3-nothink", "reasoning", 0)),
        "[0.779, 0.975]", "[0.779, 0.975]")
    add("Newcombe, step-0 action difference", "monitor_experiment_qwen3",
        lambda: newcombe(_caught("qwen3-on", "action", 0),
                         _caught("qwen3-nothink", "action", 0)),
        "[0.001, 0.398]", "[0.001, 0.398]")
    add("Newcombe, refusal-rate difference", "monitor_experiment_qwen3",
        lambda: newcombe(
            (_monitor()["arms"]["qwen3-nothink"]["n_refused"],
             _monitor()["arms"]["qwen3-nothink"]["n_trajectories"]),
            (_monitor()["arms"]["qwen3-on"]["n_refused"],
             _monitor()["arms"]["qwen3-on"]["n_trajectories"]),
        ), "[0.025, 0.328]", "[0.025, 0.328]")

    # --- Refusal-negative Wilson intervals (section 4.2) ------------------------
    for arm, expected, tex in (
        ("qwen3-on", "[0.000, 0.324]", "[0.000, 0.324]"),
        ("qwen3-nothink", "[0.000, 0.242]", "[0.000, 0.242]"),
    ):
        add(f"Wilson at zero flags, {arm} negatives", "monitor_experiment_qwen3",
            lambda a=arm: (  # type: ignore[misc]
                lambda i: f"[{i.low:.3f}, {i.high:.3f}]"
            )(wilson_interval(
                0,
                _monitor()["arms"][a]["n_trajectories"]
                - _monitor()["arms"][a]["n_positive"],
            )), expected, tex)

    # --- Long horizon (section 4.4) ---------------------------------------------
    add("nemotron SWE readable share", "swebench_longhorizon",
        lambda: f"{_swe()['arms']['nemotron-3.5-lightning']['readable_overall']:.3f}",
        "0.994", "0.994")
    add("nemotron SWE Phala calls", "swebench_longhorizon",
        lambda: str(_swe()["arms"]["nemotron-3.5-lightning"]["providers"]["Phala"]),
        "530", "530 of 530")
    add("gpt-oss SWE readable share", "swebench_longhorizon",
        lambda: f"{_swe()['arms']['gpt-oss-120b']['readable_overall']:.3f}",
        "0.856", "0.856")
    add("qwen3 SWE readable share", "swebench_longhorizon",
        lambda: f"{_swe()['arms']['qwen3-32b']['readable_overall']:.3f}",
        "0.836", "0.836")
    for upstream, expected in (("AkashML", "197"), ("DeepInfra", "195"),
                               ("Mancer 2", "93")):
        add(f"gpt-oss SWE upstream {upstream}", "swebench_longhorizon",
            lambda u=upstream: str(  # type: ignore[misc]
                _swe()["arms"]["gpt-oss-120b"]["providers"][u]
            ), expected, expected)

    # --- Monitor provenance (section 3.5) ----------------------------------------
    add("qwen3 visible arm, DeepInfra calls", "monitor_experiment_qwen3",
        lambda: str(_monitor()["arms"]["qwen3-on"]["providers"]["DeepInfra"]),
        "172", "172 of 172")
    add("qwen3 dark arm, DeepInfra calls", "monitor_experiment_qwen3",
        lambda: str(_monitor()["arms"]["qwen3-nothink"]["providers"]["DeepInfra"]),
        "180", "180 of 180")

    # --- Refusal counts (section 3.5) --------------------------------------------
    add("qwen3 visible refusals", "monitor_experiment_qwen3",
        lambda: str(_monitor()["arms"]["qwen3-on"]["n_refused"]),
        "5", "refuses 5 of 50")
    add("qwen3 visible positives", "monitor_experiment_qwen3",
        lambda: str(_monitor()["arms"]["qwen3-on"]["n_positive"]), "42", "42 positives")
    add("qwen3 dark positives", "monitor_experiment_qwen3",
        lambda: str(_monitor()["arms"]["qwen3-nothink"]["n_positive"]), "38", "38 dark")

    return entries


def self_check() -> list[str]:
    """Recompute every derivation; return a list of mismatch descriptions."""
    problems: list[str] = []
    seen: set[str] = set()
    for entry in registry():
        if entry.label in seen:
            problems.append(f"duplicate registry label: {entry.label}")
        seen.add(entry.label)
        try:
            actual = entry.derivation()
        except Exception as error:  # report it, do not crash the whole run
            problems.append(f"{entry.label}: derivation raised {error!r}")
            continue
        if actual != entry.expected:
            problems.append(
                f"{entry.label} ({entry.record}): record gives {actual!r}, "
                f"registry expects {entry.expected!r}"
            )
    return problems


def check_manuscript(path: Path) -> list[str]:
    """Return a list of registered numbers that do not appear in the manuscript."""
    text = path.read_text()
    # Collapse whitespace so a literal split across a line break still matches.
    flat = re.sub(r"\s+", " ", text)
    missing = []
    for entry in registry():
        if entry.in_tex is None:
            continue
        if re.sub(r"\s+", " ", entry.in_tex) not in flat:
            missing.append(f"{entry.label}: {entry.in_tex!r} not found in the paper")
    return missing


def main() -> int:
    """Run the self-check, and with --check the manuscript check as well."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-check", action="store_true",
        help="verify every registry entry against its record (needs no manuscript)",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="also verify the manuscript contains every registered number",
    )
    parser.add_argument("--paper", type=Path, default=PAPER)
    args = parser.parse_args()
    if not args.self_check and not args.check:
        args.self_check = True

    problems = self_check()
    print(f"registry: {len(registry())} numbers")
    if problems:
        print(f"\n{len(problems)} registry mismatch(es):")
        for problem in problems:
            print(f"  {problem}")
    else:
        print("self-check: every registered number matches its record")

    if args.check:
        if not args.paper.exists():
            print(f"manuscript not found at {args.paper}; skipping the text check")
        else:
            missing = check_manuscript(args.paper)
            if missing:
                print(f"\n{len(missing)} registered number(s) missing from the paper:")
                for item in missing:
                    print(f"  {item}")
                problems.extend(missing)
            else:
                print("manuscript: every registered number is present")

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
