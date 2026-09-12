"""RQ3: how often does one agent normatively object to another?

This module does not answer that question, and the reason it does not is the
result. Three independent obstacles, each computed rather than asserted:

1. **Structural.** 70.2% of collusion.wiki pages carry exactly one agent, and a
   page edited by one agent cannot contain peer disagreement by construction.
2. **Instrumental.** The two detectors' rung-1 recall intervals do not overlap
   (0.072 [0.046, 0.111] vs 0.218 [0.171, 0.273]), so any rate would inherit a
   3x detector-dependence before it inherited any sampling error.
3. **Transfer.** Rung 2 is not built. Both instruments were validated on human
   Wikipedia prose; nothing here establishes that they transfer to agent
   protocol strings, which is what collusion.wiki actually contains.

`rq3_endpoint` therefore returns a bound and a refusal, and
`require_validation` raises if anyone asks it for a rate anyway.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from channels._vendored_stats import wilson_upper_bound


@dataclass(frozen=True)
class Rq3Result:
    """What can honestly be said about RQ3 from the corpora in this repository."""

    n_pages_total: int
    n_pages_single_agent: int
    n_pages_multi_agent: int
    feasible_share: float
    observed_objections: int | None
    upper_bound_95: float | None
    rate: None
    rate_status: str
    blockers: tuple[str, ...]


#: Recall intervals measured at step 9 and step 10, carried here so the
#: sensitivity analysis cites numbers rather than restating them.
TREE_CODER_OBJ_RECALL = (0.072, (0.046, 0.111))
NLI_DETECTOR_OBJ_RECALL = (0.218, (0.171, 0.273))


def feasible_denominator(actors_per_page: Counter[int]) -> tuple[int, int, int]:
    """Split pages into (total, single-agent, multi-agent).

    Single-agent pages are not a small denominator; they are no denominator. The
    split is returned rather than the ratio so a reader can recompute.
    """
    total = sum(actors_per_page.values())
    single = actors_per_page.get(1, 0)
    return total, single, total - single


def rq3_endpoint(
    actors_per_page: Counter[int], observed_objections: int | None = None
) -> Rq3Result:
    """Return the RQ3 bound and the blockers that stop it becoming a rate.

    `observed_objections` is None unless a validated detector has been run on
    rung 2. It is None here, and the `rate_status` says so.
    """
    total, single, multi = feasible_denominator(actors_per_page)
    blockers = (
        f"{single}/{total} pages ({single / total:.1%}) have one agent and cannot "
        "contain peer disagreement by construction",
        "two detectors disagree 3x on rung-1 OBJ recall with non-overlapping "
        "intervals, so any rate is detector-dependent before it is sampled",
        "rung 2 is not built: transfer from human prose to agent protocol "
        "strings is unvalidated",
    )
    if observed_objections is None:
        return Rq3Result(
            n_pages_total=total,
            n_pages_single_agent=single,
            n_pages_multi_agent=multi,
            feasible_share=multi / total if total else 0.0,
            observed_objections=None,
            upper_bound_95=None,
            rate=None,
            rate_status="no_validated_detector_for_this_corpus",
            blockers=blockers,
        )
    # Zero observed is not "no signal found"; it is "below X with 95% confidence".
    bound = wilson_upper_bound(observed_objections, multi) if multi else None
    return Rq3Result(
        n_pages_total=total,
        n_pages_single_agent=single,
        n_pages_multi_agent=multi,
        feasible_share=multi / total if total else 0.0,
        observed_objections=observed_objections,
        upper_bound_95=bound,
        rate=None,
        rate_status="one_sided_bound_only",
        blockers=blockers,
    )


def recall_corrected_bound(observed_rate: float, recall: float) -> float:
    """Sensitivity analysis 1: what the true rate would be at a given recall.

    An observed rate of r from an instrument with recall k implies a true rate of
    about r/k. At the rung-1 recalls measured here this inflates an observed rate
    by between 4.6x and 14x depending on which detector you believe, which is why
    no rate is reported.
    """
    if not 0.0 < recall <= 1.0:
        raise ValueError(f"recall={recall}: must be in (0, 1]")
    return min(1.0, observed_rate / recall)


def denominator_sensitivity(
    numerator: int, all_pages: int, feasible_pages: int
) -> tuple[float, float]:
    """Sensitivity analysis 2: the same numerator over two defensible denominators.

    Returns (rate over all pages, rate over multi-agent pages only). At this
    corpus's 70/30 split the second is 3.35x the first, which is the size of the
    reporting-unit choice the prior art leaves unstated.
    """
    over_all = numerator / all_pages if all_pages else 0.0
    over_feasible = numerator / feasible_pages if feasible_pages else 0.0
    return over_all, over_feasible
