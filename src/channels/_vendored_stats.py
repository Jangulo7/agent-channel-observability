"""Statistics vendored from `safety-eval-pipeline`, with attribution.

Origin: https://github.com/Jangulo7/safety-eval-pipeline, `src/safety_eval/stats.py`
(tag v1.1.0), DOI 10.5281/zenodo.22182741. MIT licensed, same author.

The spec asks for `wilson_interval`, `wilson_upper_bound` and `bootstrap_ci`. The
upstream module actually exports `wilson`, `wilson_from_rate` and `bootstrap_mean`,
and has no one-sided bound at all. Rather than rename upstream code — whose edge
cases are already correct and already tested there — the originals are copied
verbatim below and the spec's three names are provided as thin wrappers at the end
of the file. `wilson_upper_bound` is genuinely new code and is marked as such.
"""
# NEEDS REVIEW: spec §1.2 names three functions that do not exist upstream under
# those names. Vendored the real ones verbatim and added the spec's names as
# wrappers; `wilson_upper_bound` had to be written fresh.

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from channels.errors import InvalidRateError

# 95% two-sided normal quantile. Hardcoded rather than pulled from scipy so that the
# interval maths has no dependency and is trivially checkable against a table.
Z_95 = 1.959963984540054


@dataclass(frozen=True)
class Interval:
    """A confidence interval, or an explicit statement that none could be computed."""

    low: float
    high: float
    method: str
    level: float = 0.95

    @property
    def available(self) -> bool:
        return not (math.isnan(self.low) or math.isnan(self.high))

    def overlaps(self, other: Interval) -> bool:
        """Whether two intervals overlap.

        Used for tie detection. Note this is a deliberately *conservative* test: two
        non-overlapping 95% intervals imply a difference, but overlapping ones do not imply
        the absence of one. The leaderboard therefore only ever claims 'tied', never
        'significantly different'.
        """
        if not (self.available and other.available):
            return True  # unknown uncertainty: refuse to claim a difference
        return self.low <= other.high and other.low <= self.high

    def as_dict(self) -> dict[str, float | str]:
        return {"ci_low": self.low, "ci_high": self.high, "ci_method": self.method,
                "ci_level": self.level}


UNAVAILABLE = Interval(math.nan, math.nan, "unavailable")


def wilson(successes: float, n: int, z: float = Z_95, scale: float = 1.0) -> Interval:
    """Wilson score interval for a proportion, returned on the metric's native scale.

    ``scale`` is the metric's upper bound: 1.0 for a fraction, 100.0 for a percentage. The
    proportion is computed in [0, 1] and the interval is scaled back afterwards, so a
    percentage metric gets a percentage interval.

    Args:
        successes: count of successes (may be fractional — XSTest counts a partial refusal
            as half a refusal before rounding into its rate).
        n: denominator. **This must be the number of *scored* samples**, not the number
            requested: samples the grader failed to parse leave the denominator entirely.
        z: normal quantile for the desired level.
        scale: metric upper bound.

    Returns:
        An ``Interval`` on the native scale, or ``UNAVAILABLE`` when ``n <= 0``.
    """
    if n <= 0:
        return UNAVAILABLE
    p = successes / n
    p = min(1.0, max(0.0, p))
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return Interval(
        low=max(0.0, centre - margin) * scale,
        high=min(1.0, centre + margin) * scale,
        method=f"wilson-{'pct' if scale != 1.0 else 'unit'}",
    )


def wilson_from_rate(rate: float, n: int, scale: float = 1.0, z: float = Z_95) -> Interval:
    """Wilson interval when only the aggregate rate is known, not the raw counts.

    Inspect reports the metric, not the successes, so this back-computes the count. It is
    exact for integer-valued counts and a close approximation otherwise.
    """
    if n <= 0 or math.isnan(rate):
        return UNAVAILABLE
    return wilson(successes=(rate / scale) * n, n=n, z=z, scale=scale)


def bootstrap_mean(
    values: Sequence[float],
    iterations: int = 10_000,
    level: float = 0.95,
    seed: int = 42,
) -> Interval:
    """Percentile bootstrap interval for the mean of per-sample values.

    Seeded, so the published interval is reproducible from the same log — an interval that
    moves between renderings of the same data is not evidence of anything.
    """
    clean = [v for v in values if v is not None and not math.isnan(v)]
    n = len(clean)
    if n == 0:
        return UNAVAILABLE
    if n == 1:
        return Interval(clean[0], clean[0], "bootstrap-degenerate", level)

    import random

    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(iterations):
        total = 0.0
        for _ in range(n):
            total += clean[rng.randrange(n)]
        means.append(total / n)
    means.sort()
    alpha = (1.0 - level) / 2.0
    lo = means[int(alpha * iterations)]
    hi = means[min(iterations - 1, int((1.0 - alpha) * iterations))]
    return Interval(low=lo, high=hi, method="bootstrap-percentile", level=level)




# --------------------------------------------------------------------------
# Below this line is NOT vendored. Written for this project.
# --------------------------------------------------------------------------


def wilson_interval(successes: float, n: int, confidence: float = 0.95) -> Interval:
    """Two-sided Wilson score interval, under the name the spec uses."""
    return wilson(successes, n, z=_z_for(confidence, two_sided=True))


def wilson_upper_bound(successes: float, n: int, confidence: float = 0.95) -> float:
    """One-sided upper bound on a proportion; the reportable number when zero is observed.

    With zero events the two-sided interval's lower limit is 0.0, and reporting the
    point estimate alone would say "no signal found" when the data only support
    "nothing observed in n trials". This returns the value X in "rate below X with
    `confidence` confidence".
    """
    if n <= 0:
        raise InvalidRateError(f"n must be positive for an upper bound, got n={n}")
    # One-sided at level c is the two-sided interval's upper limit at level 2c - 1.
    return wilson(successes, n, z=_z_for(confidence, two_sided=False)).high


def bootstrap_ci(
    values: Sequence[float],
    seed: int,
    n_resamples: int = 10_000,
    level: float = 0.95,
) -> Interval:
    """Seeded percentile bootstrap for the mean, under the name the spec uses."""
    return bootstrap_mean(values, iterations=n_resamples, level=level, seed=seed)


def _z_for(confidence: float, two_sided: bool) -> float:
    """Return the normal quantile for a confidence level.

    Only the levels this project actually reports are tabulated, because pulling in
    scipy for an inverse normal CDF would add a dependency the spec does not allow,
    and an unchecked rational approximation is worse than an explicit table.
    """
    if not 0.0 < confidence < 1.0:
        raise InvalidRateError(
            f"confidence must lie in (0, 1), got {confidence}"
        )
    table = {(0.95, True): Z_95, (0.99, True): 2.5758293035489004,
             (0.90, True): 1.6448536269514722,
             (0.95, False): 1.6448536269514722,
             (0.99, False): 2.3263478740408408,
             (0.90, False): 1.2815515655446004}
    key = (round(confidence, 4), two_sided)
    if key not in table:
        raise InvalidRateError(
            f"no tabulated normal quantile for confidence={confidence} "
            f"(two_sided={two_sided}); tabulated levels are 0.90, 0.95, 0.99"
        )
    return table[key]
