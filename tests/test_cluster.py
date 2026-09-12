"""Inference under dependence, on the 91%-in-one-cluster shape that motivates it."""

import pytest

from channels.cluster import (
    clustered_bootstrap,
    clustered_wilson,
    design_effect,
    naive_wilson,
    require_actors,
    zero_case_bound,
)
from channels.errors import MissingActorError
from channels.schema import Channel, Provenance, Utterance


def _utt(uid: str, actor: str | None) -> Utterance:
    return Utterance(
        uid=uid,
        corpus="synthetic_fixture",
        channel=Channel.INTER_AGENT_MESSAGE,
        provenance=Provenance.VERBATIM,
        text="SYNTHETIC",
        actor=actor,
    )


def test_missing_actor_raises_rather_than_pooling() -> None:
    with pytest.raises(MissingActorError) as excinfo:
        require_actors([_utt("s:1", "a"), _utt("s:2", None)])
    assert "s:2" in str(excinfo.value)


def test_clustered_interval_wider_than_naive() -> None:
    """The fixture is collusion.wiki's shape: 91% of mass in one cluster."""
    clusters = ["dse"] * 91 + [f"other_{i}" for i in range(9)]
    successes, n = 30, 100
    clustered = clustered_wilson(successes, n, clusters)
    naive = naive_wilson(successes, n)
    assert clustered.n_clusters == 10
    assert clustered.rate == naive.rate
    clustered_width = clustered.ci_high - clustered.ci_low
    naive_width = naive.ci_high - naive.ci_low
    assert clustered_width > naive_width


def test_single_cluster_yields_no_interval() -> None:
    """One trajectory is one cluster. That is 'we cannot say', not a wide interval."""
    result = clustered_wilson(686, 2061, ["mythos_5_incident_1"] * 2061)
    assert result.rate == pytest.approx(686 / 2061)
    assert result.ci_low is None
    assert result.ci_high is None
    assert result.status == "single_cluster_no_interval"


def test_design_effect_grows_with_concentration() -> None:
    balanced = design_effect([10] * 10)
    concentrated = design_effect([91] + [1] * 9)
    assert concentrated > balanced


def test_clustered_bootstrap_resamples_clusters() -> None:
    values = {"a": [1.0] * 50, "b": [0.0] * 50}
    result = clustered_bootstrap(values, lambda v: sum(v) / len(v), seed=11)
    assert result.n_clusters == 2
    assert result.n == 100
    # Resampling whole clusters can draw a+a or b+b, so the interval spans the range.
    assert result.ci_low == pytest.approx(0.0)
    assert result.ci_high == pytest.approx(1.0)


def test_clustered_bootstrap_is_seeded() -> None:
    values = {"a": [1.0, 0.0], "b": [1.0, 1.0], "c": [0.0, 0.0]}
    stat = lambda v: sum(v) / len(v)  # noqa: E731
    assert clustered_bootstrap(values, stat, seed=3) == clustered_bootstrap(
        values, stat, seed=3
    )


def test_zero_case_upper_bound() -> None:
    """Zero events give a bound, never a bare 0.0."""
    bound = zero_case_bound(200)
    assert 0.0 < bound < 0.05
