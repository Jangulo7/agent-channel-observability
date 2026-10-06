"""The two paper-ready figures, from the tracked records only.

Fig 1: what an external evaluator can read, per reasoning-sweep arm (finding 1) - the
readable / redacted / absent partition, showing visibility is 0 or 1 by provider and
request, not a spectrum. Source: results/observability_record_reasoning.json.

Fig 2: the measured recall drop (finding 2) - a reasoning-gated monitor's recall
collapses when the channel goes dark, while an action-gated monitor's is largely kept.
Source: results/monitor_experiment_qwen3/monitor_record.json.

Colours are the colourblind-safe Okabe-Ito set; matplotlib only; captions state n.

    .venv/bin/python scripts/make_paper_figures.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path("results/figures_paper")
REASONING = Path("results/observability_record_reasoning.json")
QWEN = Path("results/monitor_experiment_qwen3/monitor_record.json")

# Okabe-Ito colourblind-safe palette.
C_READABLE = "#0072B2"
C_SUMMARY = "#56B4E9"
C_REDACTED = "#D55E00"
C_ABSENT = "#999999"
C_COT = "#0072B2"
C_ACTION = "#E69F00"
TEXT = "#111111"
# TEXT_WIDTH_IN is the manuscript's \textwidth: 11pt article, 1in margins, US
# Letter. Figures are drawn at that width and included at \linewidth, so a point in
# a figure is a point on the page and the labels match the body text in size. Drawing
# wider and letting LaTeX scale down is what made them unreadable.
TEXT_WIDTH_IN = 6.5
plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#444444",
                     "figure.facecolor": "white", "axes.facecolor": "white",
                     "savefig.dpi": 300})

FIG1_CAPTION = (
    "Figure 1. Share of assistant turns in each reasoning-channel state, per model "
    "arm, over three safety benchmarks (sycophancy, xstest, strong_reject; n = 1,263 "
    "assistant turns per arm, identical 1,013 samples). Visibility is bimodal IN THIS "
    "SWEEP, whose configuration lever is binary in every arm: five arms are readable "
    "at about 1.0; deepseek-v3.2 in its default configuration is fully absent (no "
    "reasoning produced) while the same model with reasoning requested is 0.980 "
    "readable; and gpt-5-nano at low, medium and high effort is fully redacted "
    "(encrypted). The bimodality is not a general law: the agentic arms, where the "
    "model's own emission behaviour varies, give intermediate shares (0.834 and 0.922 "
    "for gpt-oss-120b across two pinned upstreams; 0.856 and 0.836 on SWE-bench). "
    "Note also that this sweep is single-turn and so cannot show the post-tool-result "
    "effect. What an evaluator can read is set by the provider and the request, not by "
    "the model alone. "
    "Source: results/observability_record_reasoning.json."
)


def _arm_shares() -> list[tuple[str, dict[str, float]]]:
    """Per-arm reasoning-state shares, weighted by turns, sorted by readable share."""
    record = json.loads(REASONING.read_text())["observability_record"]
    agg: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for cell in record["emission"]["cells"]:
        n = cell["n_turns"]
        row = agg[cell["model"]]
        for state in ("raw_present", "summary_only", "redacted", "absent"):
            row[state] += cell[state] * n
        row["n"] += n
    states = ("raw_present", "summary_only", "redacted", "absent")
    out = [(arm, {k: row[k] / row["n"] for k in states} | {"n": row["n"]})
           for arm, row in agg.items()]
    # Arms tied on readable share (the three gpt-5-nano effort arms are all 0.0000)
    # would otherwise order incidentally; break the tie on effort, then on name, so
    # low/medium/high always read in that order and the figure is deterministic.
    effort = {"low": 0, "medium": 1, "high": 2}
    def _key(kv: tuple[str, dict[str, float]]) -> tuple[float, int, str]:
        arm = kv[0]
        suffix = arm.rsplit("-", 1)[-1]
        return (kv[1]["raw_present"], effort.get(suffix, -1), arm)
    return sorted(out, key=_key)


def figure_visibility() -> tuple[Path, str]:
    """Fig 1: horizontal stacked bars of the four states, one per arm."""
    arms = _arm_shares()
    labels = [a for a, _ in arms]
    fig, ax = plt.subplots(figsize=(TEXT_WIDTH_IN, 3.9))
    left = [0.0] * len(arms)
    for state, colour, name in (
        ("raw_present", C_READABLE, "readable (raw)"),
        ("summary_only", C_SUMMARY, "summary only"),
        ("redacted", C_REDACTED, "redacted (encrypted)"),
        ("absent", C_ABSENT, "absent (none produced)"),
    ):
        vals = [s[state] for _, s in arms]
        ax.barh(labels, vals, left=left, color=colour, label=name, height=0.72)
        left = [a + b for a, b in zip(left, vals, strict=True)]
    ax.set_xlim(0, 1)
    ax.set_xlabel("share of assistant turns (n = 1,263 per arm)")
    ax.set_title("What an external evaluator can read, by model arm\n"
                 "(same three benchmarks, identical 1,013 samples per arm)",
                 fontsize=10, color=TEXT)
    # Legend below the axes so it never sits on top of a bar.
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4,
              frameon=False, fontsize=8, handlelength=1.2, columnspacing=1.2)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    path = OUT / "fig1_visibility_by_arm.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path, FIG1_CAPTION


def figure_recall_drop() -> tuple[Path, str]:
    """Fig 2: cumulative monitor recall by step, CoT vs action, visible vs dark."""
    arms = json.loads(QWEN.read_text())["monitor_experiment"]["arms"]

    def series(arm: str, channel: str) -> list[tuple[int, float]]:
        return [(p["step_index"], p["recall"])
                for p in arms[arm]["recall_by_step"][channel]]

    fig, ax = plt.subplots(figsize=(TEXT_WIDTH_IN, 3.5))
    # Powered steps; later steps fall below n=10 (noted in the caption). Step 4 holds
    # n=16 visible and n=13 dark, and its action-dark cell rises where step 3 fell,
    # which is the survivor-conditioned denominator becoming visible in the figure.
    max_step = 4
    # Series are labelled at the line end rather than in a legend box, and their
    # step-0 value is annotated at the left, so the figure reads without a key.
    # No descriptive note is drawn inside the axes: that text is the caption's job
    # (see the .caption.txt written alongside), and duplicating it here renders it
    # too small to read in the compiled paper.
    for arm, ch, colour, ls, marker, label in (
        ("qwen3-on", "reasoning", C_COT, "-", "o", "CoT monitor · visible"),
        ("qwen3-nothink", "reasoning", C_COT, "--", "o", "CoT monitor · dark"),
        ("qwen3-on", "action", C_ACTION, "-", "s", "action monitor · visible"),
        ("qwen3-nothink", "action", C_ACTION, "--", "s", "action monitor · dark"),
    ):
        xy = [(x, y) for x, y in series(arm, ch) if x <= max_step]
        xs, ys = [x for x, _ in xy], [y for _, y in xy]
        ax.plot(xs, ys, ls, color=colour, marker=marker, markersize=7, linewidth=2.2)
        ax.text(xs[-1] + 0.10, ys[-1], label, color=colour, fontsize=8.5,
                va="center", ha="left")
        ax.text(xs[0] - 0.10, ys[0], f"{ys[0]:.2f}", color=TEXT, fontsize=8.5,
                va="center", ha="right")
    ax.set_xlim(-0.55, max_step + 1.45)
    ax.set_ylim(-0.04, 1.06)
    ax.set_xticks(range(max_step + 1))
    ax.set_xlabel("trajectory step (assistant turn)")
    ax.set_ylabel("recall among trajectories reaching step j")
    ax.set_title("A reasoning-gated monitor collapses when the channel is dark;\n"
                 "an action-gated monitor degrades but does not",
                 fontsize=10.5, color=TEXT)
    ax.grid(axis="y", color="#DDDDDD", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    path = OUT / "fig2_recall_drop.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    on = arms["qwen3-on"]["n_positive"]
    dark = arms["qwen3-nothink"]["n_positive"]
    caption = (
        "Figure 2. Cumulative recall by step of two gpt-5-nano monitors, one reading "
        "only the reasoning channel and one only the actions, over harmful-graded "
        f"qwen3-32b trajectories (AgentHarm harmful; {on} positives with reasoning "
        f"visible, {dark} with reasoning turned off by /no_think; AgentHarm's own "
        "grader is gpt-4o-2024-08-06, our ground truth). The denominator is "
        "survivor-conditioned: at each step it is the positive trajectories still "
        "running, so the curves are not monotone. Steps 0 and 1 are exact "
        "full-denominator recalls, because the shortest positive trajectory in either "
        "arm runs two steps. With reasoning visible the CoT monitor catches 0.93 of "
        "trajectories at the first step, and all 29 still running at step 2 had been "
        "caught; with the channel dark it catches 0.00 at step 0 and at most 0.17 "
        "through step 4 (abstaining on 144/155 turns). The action monitor keeps most "
        "of its recall in both arms because actions stay observable; its step-3 to "
        "step-4 rise is the shrinking denominator, not a late catch. Steps beyond 4 "
        "fall below n = 10 and are omitted. Caveats: /no_think also raised refusals "
        "(0.10 to 0.28; difference 0.18, 95% CI [0.03, 0.33]), so the arms are not a "
        "clean behavioural A/B, and no false-positive rate was measured, so these are "
        "a visible-versus-dark contrast rather than an operating point. The CoT "
        "collapse is unambiguous: the Newcombe 95% interval for the step-0 difference "
        "is [0.78, 0.98]. "
        "Source: results/monitor_experiment_qwen3/monitor_record.json."
    )
    return path, caption


def main() -> int:
    """Write both figures and their standalone caption files."""
    OUT.mkdir(parents=True, exist_ok=True)
    for path, caption in (figure_visibility(), figure_recall_drop()):
        path.with_suffix(".caption.txt").write_text(caption + "\n", encoding="utf-8")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
