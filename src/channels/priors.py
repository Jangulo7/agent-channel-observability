"""Published constants with their provenance. No computation, no side effects.

Every value here is transcribed from a named source, and every caveat that must travel
with the number travels with it in the same object. A rate whose caveats live in a
different file gets cited without them.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PriorRate:
    """A published rate, with enough provenance to cite and to caveat."""

    value: float
    n: int | None
    source: str
    caveats: tuple[str, ...]


# AISI, "Cheating behaviour in frontier model evaluations", 21 July 2026, Figure 5.
# P(normative deliberation appears in reasoning | cheating action detected).
# Caveat 1: denominators are "cheating resamples", so these are conditional on
#   AISI's own monitor having detected the cheat.
# Caveat 2: resamples cluster within underlying actions, so AISI's intervals are
#   likely optimistic.
# Caveat 3: the bound derived from these applies only to detectors GATED on
#   deliberation. METR reports that no-reasoning agents are "not obviously less
#   monitorable", so action-only evidence can suffice.
AISI_DELIBERATION_COVERAGE = {
    "gpt-5.6-sol": PriorRate(0.50, 238, "AISI 2026-07-21 Fig 5", ()),
    "claude-mythos-preview": PriorRate(0.09, 166, "AISI 2026-07-21 Fig 5", ()),
    "claude-opus-4.7": PriorRate(0.00, 79, "AISI 2026-07-21 Fig 5", ()),
}

# AdaptThink (Zhang et al., EMNLP 2025, arXiv:2505.13417), RatioNT: share of
# instances answered in NoThinking mode, DeepSeek-R1-Distill-Qwen-7B.
# Used only to show that emission varies by task WITHIN a model. These are
# INDUCED by the authors' RL objective, not observed under no intervention.
ADAPTTHINK_TASK_SPREAD = {
    "gsm8k": PriorRate(
        0.996, None, "AdaptThink Table, 7B", ("induced by RL objective",)
    ),
    "math500": PriorRate(
        0.766, None, "AdaptThink Table, 7B", ("induced by RL objective",)
    ),
    "aime": PriorRate(
        0.063, None, "AdaptThink Table, 7B", ("induced by RL objective",)
    ),
}

# AdaptR1 (Wang et al., arXiv:2605.31062), Table 4, MuSiQue at lambda=0.9.
# Per-step no-think ratio. Shows emission varies by step POSITION within a
# trajectory. Their profile is induced by a reward whose lambda term pays for
# first-step no-think, and the whole profile is manipulable: lambda=0.2 gives
# ~0 everywhere, lambda=0.8 gives ~1 everywhere. Their Limitations disclaim
# transfer to long-horizon agentic settings, which is our setting.
ADAPTR1_STEP_PROFILE = {
    1: 1.0000, 2: 0.0000, 3: 0.8359, 4: 0.1983, 5: 0.3333, 6: 0.0000,
}

# NEEDS REVIEW: the pre-registration (§1) states AISI's *non*-deliberation figures as
# 49% / 91% / 100%, whose complements are 0.51 / 0.09 / 0.00. The spec's table, which
# the build instructions say to transcribe verbatim, gives 0.50 for gpt-5.6-sol. The
# 0.01 discrepancy is carried here unresolved rather than silently reconciled; the
# figure caption reports the spec's value and this note.
AISI_COMPLEMENT_DISCREPANCY = (
    "PREREGISTRATION.odt §1 implies 0.51 for gpt-5.6-sol (100% - 49%); "
    "SPEC §6 gives 0.50. Unresolved, not reconciled. Verify against AISI Figure 5."
)
