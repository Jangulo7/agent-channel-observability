"""ARTEFACT_EDIT is a channel of its own, and is scored structurally.

The v1 schema had no code for disagreement-by-action, which silently assumed an
agent that disagrees says so. These tests pin the separation that assumption cost.
"""

from __future__ import annotations

import pytest

from channels.cluster import (
    PRIMARY_CLUSTER_FIELD,
    SENSITIVITY_CLUSTER_FIELD,
    both_clusterings,
    cluster_keys,
)
from channels.codebook import ACTION_CODES, VERBAL_CODES, load_codebook
from channels.detect import RevertDetector
from channels.errors import MissingActorError
from channels.provenance import (
    ACTION_CHANNELS,
    MESSAGE_CHANNELS,
    is_inter_agent,
    is_inter_agent_message,
)
from channels.schema import Channel, Provenance, Utterance
from channels.tree import TreeCoder


def _utt(uid: str, channel: Channel, revert: bool = False, actor: str = "agent_a",
         page: str = "page_1", text: str | None = None) -> Utterance:
    """A synthetic utterance on a chosen channel."""
    return Utterance(
        uid=uid,
        corpus="synthetic_fixture",
        channel=channel,
        provenance=Provenance.REDACTED_PARTIAL,
        text=text,
        actor=actor,
        thread_id=page,
        corpus_meta={"is_revert": revert},
    )


def test_artefact_edit_is_agent_traffic_but_not_a_message() -> None:
    """The distinction the inter-agent denominator depends on."""
    edit = _utt("s:1", Channel.ARTEFACT_EDIT)
    message = _utt("s:2", Channel.INTER_AGENT_MESSAGE, text="placeholder")
    assert is_inter_agent(edit) is True
    assert is_inter_agent_message(edit) is False
    assert is_inter_agent_message(message) is True
    assert Channel.ARTEFACT_EDIT in ACTION_CHANNELS
    assert Channel.ARTEFACT_EDIT not in MESSAGE_CHANNELS


def test_verbal_coder_routes_artefact_edits_out_of_scope() -> None:
    """A body diff has no words, so the verbal codebook must not code it."""
    label = TreeCoder().code(_utt("s:1", Channel.ARTEFACT_EDIT, text="revert"))
    assert label.in_scope is False
    assert label.gate_path == ("P", "C")


def test_revert_detector_scores_only_artefact_edits() -> None:
    """Messages are skipped, not labelled: a summary is not a failed revert."""
    utterances = [
        _utt("s:1", Channel.ARTEFACT_EDIT, revert=True),
        _utt("s:2", Channel.ARTEFACT_EDIT, revert=False),
        _utt("s:3", Channel.INTER_AGENT_MESSAGE, text="placeholder"),
    ]
    result = RevertDetector().detect(utterances)
    assert [label.code for label in result.labels] == ["REVERT", "UNCL"]
    assert result.skipped == ("s:3",)


def test_revert_and_verbal_codes_live_in_disjoint_label_spaces() -> None:
    """A structural detector and a verbal one can never be averaged together."""
    assert "REVERT" in ACTION_CODES
    assert "REVERT" not in VERBAL_CODES
    assert not set(RevertDetector().label_space) & set(TreeCoder().label_space) - {
        "UNCL"
    }


def test_codebook_v2_carries_revert_with_real_examples() -> None:
    """REVERT ships with sourced structural examples, not TODO placeholders."""
    code = load_codebook()["REVERT"]
    assert len(code.positive_examples) >= 2
    for example in code.positive_examples:
        assert example["source_ref"]
        assert not str(example["text"]).startswith("TODO(")


def test_cluster_keys_raise_rather_than_pool() -> None:
    """A missing cluster key silently assumes independence, so it must raise."""
    orphan = Utterance(
        uid="s:1", corpus="synthetic_fixture", channel=Channel.ARTEFACT_EDIT,
        provenance=Provenance.REDACTED_PARTIAL, text=None, actor=None,
        thread_id=None,
    )
    with pytest.raises(MissingActorError):
        cluster_keys([orphan], PRIMARY_CLUSTER_FIELD)
    with pytest.raises(MissingActorError):
        cluster_keys([orphan], SENSITIVITY_CLUSTER_FIELD)


def test_both_clusterings_are_reported_together() -> None:
    """Page is primary and actor is the sensitivity analysis; never one alone."""
    utterances = [
        _utt(f"s:{i}", Channel.ARTEFACT_EDIT, revert=i < 10,
             actor=f"agent_{i % 7}", page=f"page_{i % 20}")
        for i in range(200)
    ]
    result = both_clusterings(10, utterances)
    assert set(result) == {PRIMARY_CLUSTER_FIELD, SENSITIVITY_CLUSTER_FIELD}
    for rate in result.values():
        assert rate.rate == pytest.approx(10 / 200)
        assert rate.n_clusters and rate.n_clusters > 1
