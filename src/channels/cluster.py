"""Inference when observations are not independent.

Why this module exists, concretely: 91% of collusion.wiki revisions come from the
single actor `dse` (13,403 of 14,591, from the export's own manifest), so
per-observation independence is false and an unclustered interval would be
anticonservative — it would claim precision the data cannot support. The same problem
appears in the Mythos transcript from the other direction: 2,061 turns, but one
trajectory, so there is exactly one cluster and no clustered interval exists at all.

The module's rule is that it would rather return nothing than return a number computed
under an assumption it knows to be false.
"""

import random
from collections.abc import Callable, Mapping, Sequence

from channels._vendored_stats import wilson_interval
from channels.errors import InvalidRateError, MissingActorError
from channels.schema import RateWithCI, Utterance


def require_actors(utts: Sequence[Utterance]) -> list[str]:
    """Return each utterance's actor, raising if any is missing.

    Raises rather than dropping: an utterance with no actor cannot be assigned to a
    cluster, and pooling it would silently treat it as independent of everything else.
    """
    missing = [utt.uid for utt in utts if utt.actor is None]
    if missing:
        shown = ", ".join(missing[:10])
        more = "" if len(missing) <= 10 else f", and {len(missing) - 10} more"
        raise MissingActorError(
            f"{len(missing)} utterance(s) have actor=None and cannot be clustered: "
            f"{shown}{more}. Expected every utterance to carry an actor."
        )
    return [utt.actor for utt in utts if utt.actor is not None]


def design_effect(cluster_sizes: Sequence[int], icc: float = 1.0) -> float:
    """Kish design effect for unequal cluster sizes: 1 + (m_eff - 1) * icc.

    `icc = 1.0` is the worst case — observations within a cluster carry no independent
    information at all — and it is the default because this project has no estimate of
    the true intra-cluster correlation for any of its corpora. Using a smaller value
    without measuring it would buy narrower intervals with an assumption.
    """
    if not cluster_sizes:
        raise InvalidRateError("design effect needs at least one cluster")
    if not 0.0 <= icc <= 1.0:
        raise InvalidRateError(f"icc must lie in [0, 1], got {icc}")
    total = sum(cluster_sizes)
    if total == 0:
        raise InvalidRateError("design effect needs at least one observation")
    # Mean cluster size weighted by cluster size, which is what drives the inflation.
    mean_effective = sum(size * size for size in cluster_sizes) / total
    return 1.0 + (mean_effective - 1.0) * icc


def clustered_wilson(
    successes: int, n: int, clusters: Sequence[str], icc: float = 1.0
) -> RateWithCI:
    """Wilson interval on an effective sample size corrected for clustering.

    The correction divides n by the design effect before computing the interval, which
    widens it. With one cluster the effective sample size collapses to 1 and no useful
    interval exists; that is reported as a status rather than as a wide-but-finite
    interval, because "we cannot say" and "we can say very little" are different claims.
    """
    if n <= 0:
        return RateWithCI(None, None, None, 0, "none", "clustered",
                          status="no_denominator")
    sizes = _cluster_sizes(clusters)
    n_clusters = len(sizes)
    if n_clusters <= 1:
        return RateWithCI(
            rate=successes / n,
            ci_low=None,
            ci_high=None,
            n=n,
            method="clustered-wilson",
            weighting="clustered",
            n_clusters=n_clusters,
            status="single_cluster_no_interval",
        )
    effective_n = max(1.0, n / design_effect(sizes, icc))
    scaled_successes = (successes / n) * effective_n
    interval = wilson_interval(scaled_successes, round(effective_n))
    return RateWithCI(
        rate=successes / n,
        ci_low=interval.low,
        ci_high=interval.high,
        n=n,
        method="clustered-wilson",
        weighting="clustered",
        n_clusters=n_clusters,
    )


def naive_wilson(successes: int, n: int) -> RateWithCI:
    """The uncorrected interval, kept so the two can be compared side by side."""
    interval = wilson_interval(successes, n)
    return RateWithCI(
        rate=successes / n if n else None,
        ci_low=interval.low,
        ci_high=interval.high,
        n=n,
        method="wilson-naive",
        weighting="unclustered",
    )


def clustered_bootstrap(
    values_by_cluster: Mapping[str, Sequence[float]],
    statistic: Callable[[Sequence[float]], float],
    seed: int,
    n_resamples: int = 10_000,
    level: float = 0.95,
) -> RateWithCI:
    """Percentile bootstrap that resamples whole clusters, never observations.

    Resampling observations would reconstruct the independence assumption the clustering
    exists to avoid, so the resampling unit is the cluster and a drawn cluster brings
    all of its observations with it.
    """
    cluster_names = list(values_by_cluster)
    if not cluster_names:
        raise InvalidRateError("clustered bootstrap needs at least one cluster")
    n_observations = sum(len(values_by_cluster[name]) for name in cluster_names)
    if len(cluster_names) == 1:
        return RateWithCI(
            rate=statistic(values_by_cluster[cluster_names[0]]),
            ci_low=None,
            ci_high=None,
            n=n_observations,
            method="clustered-bootstrap",
            weighting="clustered",
            n_clusters=1,
            status="single_cluster_no_interval",
        )

    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(n_resamples):
        drawn: list[float] = []
        for _ in range(len(cluster_names)):
            name = cluster_names[rng.randrange(len(cluster_names))]
            drawn.extend(values_by_cluster[name])
        if drawn:
            estimates.append(statistic(drawn))
    estimates.sort()
    alpha = (1.0 - level) / 2.0
    low = estimates[int(alpha * len(estimates))]
    high = estimates[min(len(estimates) - 1, int((1.0 - alpha) * len(estimates)))]
    pooled = [v for name in cluster_names for v in values_by_cluster[name]]
    return RateWithCI(
        rate=statistic(pooled),
        ci_low=low,
        ci_high=high,
        n=n_observations,
        method="clustered-bootstrap",
        weighting="clustered",
        n_clusters=len(cluster_names),
    )


def zero_case_bound(n: int, confidence: float = 0.95) -> float:
    """One-sided upper bound on a rate when zero events were observed.

    The sentence this supports is "zero observed; rate below X with 95% confidence",
    never "no signal found". Those differ by everything: the second claims evidence of
    absence from a denominator that may have been far too small to show anything.
    """
    from channels._vendored_stats import wilson_upper_bound

    return wilson_upper_bound(0, n, confidence=confidence)


def _cluster_sizes(clusters: Sequence[str]) -> list[int]:
    """Sizes of each distinct cluster, in no particular order."""
    counts: dict[str, int] = {}
    for name in clusters:
        counts[name] = counts.get(name, 0) + 1
    return list(counts.values())
