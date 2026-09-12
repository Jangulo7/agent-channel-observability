"""WikiTactics mapping is committed, explicit, and refuses unknown labels."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from channels.errors import SchemaDiscoveryError
from channels.loaders.positive_control import (
    LABEL_TO_CODE,
    UNMEASURABLE_CODES,
    WikiTacticsLoader,
    map_to_codebook,
)

SYNTHETIC_CONVERSATIONS = [
    {
        "conv_id": "synthetic_conv_1",
        "split": "train",
        "escalation_label": 0,
        "utterances": [
            {
                "text": "placeholder coordinating text",
                "username": "synthetic_editor_a",
                "coordination_labels": ["Coordinating edits"],
                "rebuttal_labels": [],
            },
            {
                "text": "placeholder policing text",
                "username": "synthetic_editor_b",
                "coordination_labels": [],
                "rebuttal_labels": ["DH3: Policing the discussion"],
            },
        ],
    }
]


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """An obviously synthetic WikiTactics file in the real format."""
    path = tmp_path / "wikitactics.json"
    path.write_text(json.dumps(SYNTHETIC_CONVERSATIONS), encoding="utf-8")
    return path


def test_missing_corpus_raises_naming_the_path(tmp_path: Path) -> None:
    loader = WikiTacticsLoader(tmp_path / "absent.json")
    assert loader.available() is False
    with pytest.raises(SchemaDiscoveryError, match="no corpus at"):
        list(loader.load())


def test_gold_codes_come_from_the_committed_table(corpus: Path) -> None:
    utterances = list(WikiTacticsLoader(corpus).load())
    assert [u.corpus_meta["gold_code"] for u in utterances] == ["SHARE", "OBJ"]


def test_unknown_label_raises_rather_than_being_dropped() -> None:
    """An unmapped label is a schema surprise, and silence would hide it."""
    with pytest.raises(SchemaDiscoveryError, match="not in the committed mapping"):
        map_to_codebook(("DH9: A label that does not exist",))


def test_normative_code_wins_over_coordination() -> None:
    """An objection embedded in coordination is still an objection."""
    labels = ("Coordinating edits", "DH3: Policing the discussion")
    assert map_to_codebook(labels) == "OBJ"


def test_correctness_labels_map_out_of_scope_not_to_uncl() -> None:
    """DH4-DH7 are argument quality, which is not a codebook category at all."""
    for label in (
        "DH4: Repeated argument",
        "DH5: Counterargument",
        "DH6: Refutation",
        "DH7: Refuting the central point",
    ):
        assert LABEL_TO_CODE[label] is None
        assert map_to_codebook((label,)) is None


def test_four_codes_have_no_equivalent_in_this_control() -> None:
    """Recall for these must be reported undefined, never zero."""
    assert set(UNMEASURABLE_CODES) == {"ESC", "WARN", "NORM", "SELF_LICENSE"}
    mapped = {code for code in LABEL_TO_CODE.values() if code}
    assert not set(UNMEASURABLE_CODES) & mapped
