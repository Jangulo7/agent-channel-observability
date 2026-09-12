"""collusion.wiki loader: hazards encoded, text withheld, humans separated."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from channels.errors import SchemaDiscoveryError
from channels.loaders.collusion_wiki import CollusionWikiLoader
from channels.schema import Channel, Provenance

SYNTHETIC_REVISIONS = [
    # page_a: two distinct agent actors -> can contain peer disagreement.
    {"rev_id": 1, "page_key": "page_a", "label": "SyntheticAgentOne",
     "wiki": "synthetic_wiki", "time": "2026-01-01T00:00:00Z", "seq": 0,
     "body": "SYNTHETIC BODY TEXT", "body_len": 19,
     "change_summary": "SYNTHETIC SUMMARY"},
    {"rev_id": 2, "page_key": "page_a", "label": "SyntheticAgentTwo",
     "wiki": "synthetic_wiki", "time": "2026-01-01T00:01:00Z", "seq": 1,
     "body": "SYNTHETIC BODY TEXT", "body_len": 19,
     "change_summary": "SYNTHETIC SUMMARY"},
    # page_b: one actor only -> cannot contain peer disagreement.
    {"rev_id": 3, "page_key": "page_b", "label": "SyntheticAgentOne",
     "wiki": "synthetic_wiki", "time": "2026-01-01T00:02:00Z", "seq": 0,
     "body": "SYNTHETIC BODY TEXT", "body_len": 19,
     "change_summary": "SYNTHETIC SUMMARY"},
    # a human handle, and an unknown handle that must fail toward human.
    {"rev_id": 4, "page_key": "page_c", "label": "SyntheticHuman",
     "wiki": "synthetic_wiki", "time": "2026-01-01T00:03:00Z", "seq": 0,
     "body": "SYNTHETIC BODY TEXT", "body_len": 19,
     "change_summary": "SYNTHETIC SUMMARY"},
    {"rev_id": 5, "page_key": "page_c", "label": "NeverSeenInLabels",
     "wiki": "synthetic_wiki", "time": "2026-01-01T00:04:00Z", "seq": 1,
     "body": "SYNTHETIC BODY TEXT", "body_len": 19,
     "change_summary": "SYNTHETIC SUMMARY"},
]

SYNTHETIC_LABELS = [
    {"label": "SyntheticAgentOne", "is_human_handle": False},
    {"label": "SyntheticAgentTwo", "is_human_handle": False},
    {"label": "SyntheticHuman", "is_human_handle": True},
]

SYNTHETIC_PAGES = [
    {"page_key": "page_a", "n_revs": 2},
    {"page_key": "page_b", "n_revs": 1},
    {"page_key": "page_c", "n_revs": 2},
]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    """Write an obviously synthetic gzipped JSONL export file."""
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


@pytest.fixture
def export(tmp_path: Path) -> Path:
    """A tiny synthetic export in the real file layout."""
    _write(tmp_path / "revisions.jsonl.gz", SYNTHETIC_REVISIONS)
    _write(tmp_path / "labels.jsonl.gz", SYNTHETIC_LABELS)
    _write(tmp_path / "pages.jsonl.gz", SYNTHETIC_PAGES)
    return tmp_path


def test_missing_export_raises_naming_every_path(tmp_path: Path) -> None:
    loader = CollusionWikiLoader(tmp_path / "absent")
    assert loader.available() is False
    with pytest.raises(SchemaDiscoveryError, match="export not found"):
        list(loader.load())


def test_revision_body_text_is_never_carried(export: Path) -> None:
    """Body text never enters an Utterance; the corpus has no licence.

    The change_summary DOES, because the verbal codebook needs it to code the
    message channel at all. It is withheld from published artefacts instead, by
    the publication-safety tests — a different control for a different risk.
    """
    for utt in CollusionWikiLoader(export).load():
        assert utt.provenance is Provenance.REDACTED_PARTIAL
        if utt.channel is Channel.ARTEFACT_EDIT:
            assert utt.text is None, "body diff text must never be carried"


def test_unknown_handle_fails_toward_human(export: Path) -> None:
    """Spec §13.6: undetermined sender fails toward HUMAN_MESSAGE."""
    by_uid = {u.uid: u for u in CollusionWikiLoader(export).load()}
    assert by_uid["collusion_wiki:4:edit"].channel is Channel.HUMAN_MESSAGE
    assert by_uid["collusion_wiki:5:edit"].channel is Channel.HUMAN_MESSAGE
    assert by_uid["collusion_wiki:1:edit"].channel is Channel.ARTEFACT_EDIT


def test_a_revision_emits_an_edit_and_a_message_not_one_utterance(
    export: Path,
) -> None:
    """The two channels a revision carries must not be collapsed into one.

    The body diff is an ARTEFACT_EDIT addressed to no one; the change_summary is
    an INTER_AGENT_MESSAGE addressed to other editors. Coding the revision as a
    single INTER_AGENT_MESSAGE, as this loader used to, put acts that carry no
    words into the inter-agent message denominator.
    """
    utterances = list(CollusionWikiLoader(export).load())
    edits = [u for u in utterances if u.channel is Channel.ARTEFACT_EDIT]
    messages = [u for u in utterances if u.channel is Channel.INTER_AGENT_MESSAGE]
    assert edits, "no artefact edits emitted"
    assert messages, "no change_summary messages emitted"
    # The edit never carries body text; the message carries its summary.
    assert all(u.text is None for u in edits)
    assert all(u.text for u in messages)


def test_revert_is_cross_actor_only(export: Path) -> None:
    """A self-revert is revision, not disagreement, and must not be flagged."""
    reverts = CollusionWikiLoader(export)._revert_rev_ids()
    assert "3" not in reverts  # page_b: single actor, no cross-actor revert


def test_actors_per_page_counts_agents_only(export: Path) -> None:
    """A one-agent page is no denominator, not a small one — and humans do not count.

    page_a has two agents, page_b one agent, page_c only human handles. RQ3 asks
    whether one AGENT objects to another, so page_c offers no opportunity at all
    and must not appear in the distribution.
    """
    distribution = CollusionWikiLoader(export).actors_per_page()
    assert distribution[2] == 1  # page_a
    assert distribution[1] == 1  # page_b
    assert sum(distribution.values()) == 2  # page_c contributes nothing


def test_missing_required_key_raises_with_keys_observed(tmp_path: Path) -> None:
    _write(tmp_path / "revisions.jsonl.gz", [{"rev_id": 1, "page_key": "p"}])
    _write(tmp_path / "labels.jsonl.gz", SYNTHETIC_LABELS)
    _write(tmp_path / "pages.jsonl.gz", SYNTHETIC_PAGES)
    with pytest.raises(SchemaDiscoveryError, match="keys observed"):
        list(CollusionWikiLoader(tmp_path).load())


def test_describe_reports_the_single_actor_page_share(export: Path) -> None:
    """The GO/NO-GO number for RQ3 must be in describe(), not only in a notebook."""
    caveats = " ".join(CollusionWikiLoader(export).describe().caveats)
    assert "cannot contain peer disagreement by construction" in caveats
    assert "No licence stated" in caveats
