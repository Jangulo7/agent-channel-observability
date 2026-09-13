"""RQ3: how often does one agent normatively object to another?

This module does not answer that question, and the reason it does not is the
result. Three independent obstacles, each computed rather than asserted:

1. **Structural.** 70.2% of collusion.wiki pages carry exactly one agent, and a
   page edited by one agent cannot contain peer disagreement by construction.
2. **Instrumental.** The two detectors' rung-1 OBJ recall intervals do not
   overlap, so any rate would inherit a 3x detector-dependence before it
   inherited any sampling error. The recalls are read from the committed
   records under results/validation/ at call time, never restated here.
3. **Transfer.** Rung 2 is not built. Both instruments were validated on human
   Wikipedia prose; nothing here establishes that they transfer to agent
   protocol strings, which is what collusion.wiki actually contains.

`rq3_endpoint` therefore returns a bound and a refusal. Before an objection
count may become even a one-sided bound it calls `assert_primary_eligible` on
the utterances the count was made over and `require_validation` on the detector
that made it, and both raise.

The two sensitivity analyses shipped here are NOT the two registered in
PREREGISTRATION §8.2. The substitution is a deviation and `Rq3Result.deviations`
says so on every call.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from channels._vendored_stats import wilson_upper_bound
from channels.codebook import codebook_hash
from channels.detect import NliDetector
from channels.errors import ProvenanceError, UnvalidatedDetectorError
from channels.provenance import assert_primary_eligible
from channels.schema import Utterance
from channels.tree import TreeCoder
from channels.validate import VALIDATION_DIR, require_validation

#: (detector name, OBJ recall, 95% interval), as read from a validation record.
ObjRecall = tuple[str, float, tuple[float, float]]

#: What the analysis plan §8.2 pre-specified, verbatim in substance.
REGISTERED_SENSITIVITY_ANALYSES: tuple[str, ...] = (
    "exclude the dominant actor 'dse' (analysis plan §8.2)",
    "restrict to a stricter attribution subset defined by the source authors' "
    "filter criteria in manifest.json (analysis plan §8.2)",
)

#: What this module actually ships in their place.
SENSITIVITY_ANALYSES_RUN: tuple[str, ...] = (
    "recall correction: an observed rate divided by each detector's rung-1 OBJ "
    "recall (recall_corrected_bound) — exploratory, not registered",
    "denominator choice: one numerator over all pages and over multi-agent "
    "pages (denominator_sensitivity) — exploratory, not registered",
)

#: Plain-English record of the substitution. Travels with every result.
RQ3_DEVIATIONS: tuple[str, ...] = (
    "Neither sensitivity analysis pre-specified in the analysis plan §8.2 was run. "
    "Two other analyses (recall correction, denominator choice) were run instead. "
    "That substitution is a deviation from the pre-specified plan and belongs "
    "in its §11 deviations log.",
    "'Exclude the dominant actor dse' is ill-posed as registered: dse is a wiki "
    "holding 91.9% of revisions, not an actor, so excluding it removes most of "
    "the corpus rather than one dominant contributor.",
    "The stricter attribution subset was not run: nothing in this package "
    "implements the manifest.json filter criteria that would define it.",
    "Under §8.2 any further slicing is exploratory; no inference is drawn from "
    "the substitute analyses, and neither yields a reported rate.",
)

#: The two verbal instruments whose rung-1 disagreement is blocker 2.
RUNG1_DETECTORS: tuple[object, ...] = (TreeCoder(), NliDetector())


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
    rung1_obj_recalls: tuple[ObjRecall, ...] = ()
    sensitivity_analyses_registered: tuple[str, ...] = REGISTERED_SENSITIVITY_ANALYSES
    sensitivity_analyses_run: tuple[str, ...] = SENSITIVITY_ANALYSES_RUN
    deviations: tuple[str, ...] = RQ3_DEVIATIONS


def feasible_denominator(actors_per_page: Counter[int]) -> tuple[int, int, int]:
    """Split pages into (total, single-agent, multi-agent).

    Single-agent pages are not a small denominator; they are no denominator. The
    split is returned rather than the ratio so a reader can recompute.
    """
    total = sum(actors_per_page.values())
    single = actors_per_page.get(1, 0)
    return total, single, total - single


def rung1_obj_recalls(
    codebook: str | None = None, directory: Path = VALIDATION_DIR
) -> tuple[ObjRecall, ...]:
    """Read both rung-1 detectors' OBJ recall from their records, or raise."""
    current = codebook or codebook_hash()
    recalls: list[ObjRecall] = []
    for detector in RUNG1_DETECTORS:
        record = require_validation(detector, current, directory)
        score = record.scores.get("OBJ")
        if score is None or score.recall is None or score.recall_ci95 is None:
            status = "absent" if score is None else score.status
            raise UnvalidatedDetectorError(
                f"{record.detector_name} v{record.detector_version} has a record "
                f"for {current} but no measured OBJ recall (status={status})."
            )
        recalls.append((record.detector_name, score.recall, score.recall_ci95))
    return tuple(recalls)


def _instrument_blocker(recalls: Sequence[ObjRecall]) -> str:
    """State the detector disagreement from the measured intervals."""
    (low_name, low_r, low_ci), (high_name, high_r, high_ci) = sorted(
        recalls, key=lambda r: r[1]
    )
    overlap = "overlapping" if low_ci[1] >= high_ci[0] else "non-overlapping"
    ratio = f"{high_r / low_r:.1f}x" if low_r > 0 else "by an undefined ratio"
    return (
        f"two detectors disagree {ratio} on rung-1 OBJ recall ({low_name} "
        f"{low_r:.3f} [{low_ci[0]:.3f}, {low_ci[1]:.3f}] vs {high_name} "
        f"{high_r:.3f} [{high_ci[0]:.3f}, {high_ci[1]:.3f}]) with {overlap} "
        "intervals, so any rate is detector-dependent before it is sampled"
    )


def _gate_observed_count(
    utterances: Sequence[Utterance] | None,
    detector: object | None,
    codebook: str,
    directory: Path,
) -> None:
    """Run both guards before an objection count may become a bound."""
    if utterances is None:
        raise ProvenanceError(
            "observed_objections was given without the utterances it was counted "
            "over, so their provenance cannot be checked. Pass utterances=."
        )
    assert_primary_eligible(utterances)
    if detector is None:
        raise UnvalidatedDetectorError(
            "observed_objections was given without the detector that produced it. "
            "An unidentified instrument has no validation record, and no bound "
            "may be computed from its count. Pass detector=."
        )
    require_validation(detector, codebook, directory)


def rq3_endpoint(
    actors_per_page: Counter[int],
    observed_objections: int | None = None,
    *,
    utterances: Sequence[Utterance] | None = None,
    detector: object | None = None,
    codebook: str | None = None,
    validation_dir: Path = VALIDATION_DIR,
) -> Rq3Result:
    """Return the RQ3 bound and the blockers that stop it becoming a rate.

    `observed_objections` is None unless a validated detector has been run on
    rung 2; supplying it requires the utterances and detector behind it.
    """
    current = codebook or codebook_hash()
    if utterances is not None:
        assert_primary_eligible(utterances)
    if observed_objections is not None:
        _gate_observed_count(utterances, detector, current, validation_dir)
    recalls = rung1_obj_recalls(current, validation_dir)
    total, single, multi = feasible_denominator(actors_per_page)
    blockers = (
        f"{single}/{total} pages ({single / total:.1%}) have one agent and cannot "
        "contain peer disagreement by construction",
        _instrument_blocker(recalls),
        "rung 2 is not built: transfer from human prose to agent protocol "
        "strings is unvalidated",
    )
    # Zero observed is not "no signal found"; it is "below X with 95% confidence".
    bound = (
        wilson_upper_bound(observed_objections, multi)
        if observed_objections is not None and multi
        else None
    )
    return Rq3Result(
        n_pages_total=total,
        n_pages_single_agent=single,
        n_pages_multi_agent=multi,
        feasible_share=multi / total if total else 0.0,
        observed_objections=observed_objections,
        upper_bound_95=bound,
        rate=None,
        rate_status=(
            "no_validated_detector_for_this_corpus"
            if observed_objections is None
            else "one_sided_bound_only"
        ),
        blockers=blockers,
        rung1_obj_recalls=recalls,
    )


def recall_corrected_bound(observed_rate: float, recall: float) -> float:
    """Exploratory, unregistered: the true rate an observed rate implies at a recall.

    Shipped in place of the analyses pre-specified in the analysis plan §8.2; see
    RQ3_DEVIATIONS.
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
    """Exploratory, unregistered: one numerator over two defensible denominators.

    Shipped in place of the analyses pre-specified in the analysis plan §8.2; see
    RQ3_DEVIATIONS. Returns (rate over all pages, rate over multi-agent pages
    only). At this corpus's 70/30 split the second is 3.35x the first, which is
    the size of the reporting-unit choice the prior art leaves unstated.
    """
    over_all = numerator / all_pages if all_pages else 0.0
    over_feasible = numerator / feasible_pages if feasible_pages else 0.0
    return over_all, over_feasible
