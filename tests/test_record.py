"""The observability record: what it must contain, and what it must refuse to say.

The record is the artefact another researcher reads to check whether a number in the
paper is the number the code produced. Two of its properties are load-bearing and
tested here rather than assumed: an unmeasured quantity is emitted as null with a
status, never as a plausible zero; and validation runs *before* the write, so an
invalid record never reaches disk to be cited later.
"""

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from channels.emission import DENOMINATOR_STATEMENT, MIN_CELL_N, EmissionCell
from channels.record import (
    SCHEMA_VERSION,
    build_record,
    record_schema,
    validate_record,
    write_record,
)
from channels.schema import CorpusDescription, RateWithCI, ReasoningState

CORPUS = CorpusDescription(
    name="synthetic_corpus",
    n_utterances=100,
    n_actors=3,
    actor_concentration=0.5,
    date_range=("2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"),
    source_hash="sha256:SYNTHETIC",
    licence="synthetic fixture; no licence",
    caveats=("obviously synthetic; not a measurement",),
)


def cell(raw: int, absent: int, step_index: int = 0) -> EmissionCell:
    counts = {
        ReasoningState.RAW_PRESENT: raw,
        ReasoningState.SUMMARY_ONLY: 0,
        ReasoningState.REDACTED: 0,
        ReasoningState.ABSENT: absent,
    }
    return EmissionCell(
        model="SYNTHETIC-MODEL-A",
        task_class="synthetic_task",
        step_index=step_index,
        reasoning_effort=None,
        n_turns=sum(counts.values()),
        counts=counts,
        n_clusters=1,
    )


def rate(value: float, n: int = 100) -> RateWithCI:
    return RateWithCI(
        rate=value, ci_low=None, ci_high=None, n=n, method="synthetic",
        low_n=n < MIN_CELL_N,
    )


@pytest.fixture
def record() -> dict[str, Any]:
    return build_record(
        corpora=[CORPUS],
        cells=[
            cell(raw=40, absent=60, step_index=0),
            cell(raw=10, absent=90, step_index=1),
        ],
        positional={0: rate(0.40), 1: rate(0.10)},
        codebook_hash="sha256:SYNTHETIC",
    )


# --- the record validates and says what it measured -------------------------------


def test_record_validates_against_its_own_schema(record: dict[str, Any]) -> None:
    validate_record(record)  # raises on failure


def test_schema_version_is_recorded(record: dict[str, Any]) -> None:
    assert record["observability_record"]["schema_version"] == SCHEMA_VERSION


def test_denominator_statement_is_carried_verbatim(record: dict[str, Any]) -> None:
    """The denominator ships inside the record, not only in the paper.

    A rate whose denominator has to be looked up elsewhere is a rate a reader cannot
    check, so the statement travels with the numbers it describes.
    """
    assert record["observability_record"]["emission"]["denominator"] == (
        DENOMINATOR_STATEMENT
    )


def test_corpus_caveats_survive_into_the_record(record: dict[str, Any]) -> None:
    """A corpus is never reported without the caveats its loader attached."""
    corpus = record["observability_record"]["corpora"][0]
    assert corpus["caveats"] == ["obviously synthetic; not a measurement"]
    assert corpus["source_hash"] == "sha256:SYNTHETIC"


def test_cell_shares_are_recorded_for_all_four_states(record: dict[str, Any]) -> None:
    """All four states appear, so the reader can see the shape, not just the rate."""
    first = record["observability_record"]["emission"]["cells"][0]
    assert first["raw_present"] == pytest.approx(0.40)
    assert first["absent"] == pytest.approx(0.60)
    assert first["summary_only"] == 0.0
    assert first["redacted"] == 0.0
    assert first["n_turns"] == 100


def test_low_n_cells_are_flagged_not_dropped() -> None:
    """A thin cell is published with `low_n: true` rather than filtered out.

    Dropping thin cells would silently change the denominator of the table; flagging
    them leaves the reader in charge of what to trust.
    """
    built = build_record(
        corpora=[CORPUS],
        cells=[cell(raw=1, absent=1)],
        positional={0: rate(0.5, n=2)},
        codebook_hash="sha256:SYNTHETIC",
    )
    assert built["observability_record"]["emission"]["cells"][0]["low_n"] is True


def test_uninspectable_share_is_reported_alongside_the_rate(
    record: dict[str, Any],
) -> None:
    emission = record["observability_record"]["emission"]
    assert emission["uninspectable_share"] == pytest.approx(0.75)


def test_ceiling_is_derived_at_every_recorded_step(record: dict[str, Any]) -> None:
    """With a perfect second stage the ceiling equals coverage at each step."""
    bound = record["observability_record"]["bound"]
    assert bound["stage2_recall_assumed"] == 1.0
    assert bound["ceiling_by_step"]["1"] == pytest.approx(0.10)


# --- nulls, not plausible defaults -------------------------------------------------


def test_unmeasured_inter_agent_block_is_null_not_zero(record: dict[str, Any]) -> None:
    """No measurement gives `rate_per_1000: null` plus a status, never `0`.

    A rate of 0 claims a measurement was made and came back empty. Null with
    `rate_status` says no measurement was made at all. They are different findings and
    the record must not conflate them.
    """
    block = record["observability_record"]["inter_agent_channel"]
    assert block["rate_per_1000"] is None
    assert block["rate_status"] == "no_denominator"
    assert block["zero_case_upper_bound_95"] is None


def test_messages_authenticated_is_null_because_no_corpus_carries_it(
    record: dict[str, Any],
) -> None:
    """Null here is the adversarial-channel finding, not a missing field.

    No corpus this project reads has an authenticated sender, so the field is emitted
    as null rather than omitted — omitting it would hide the gap.
    """
    block = record["observability_record"]["inter_agent_channel"]
    assert "messages_authenticated" in block
    assert block["messages_authenticated"] is None


def test_absent_preregistration_commit_is_null(record: dict[str, Any]) -> None:
    assert record["observability_record"]["preregistration_commit"] is None


def test_detectors_default_to_empty_not_to_a_placeholder(
    record: dict[str, Any],
) -> None:
    """No detector has been validated here, so the list is empty.

    An empty list is checkable; a placeholder entry would be a detector claiming a
    recall nobody measured, which rule one of the project forbids.
    """
    assert record["observability_record"]["detectors"] == []


# --- the schema refuses malformed records ------------------------------------------


def test_schema_rejects_a_record_missing_a_required_block(
    record: dict[str, Any],
) -> None:
    broken = copy.deepcopy(record)
    del broken["observability_record"]["emission"]
    with pytest.raises(jsonschema.ValidationError):
        validate_record(broken)


def test_schema_rejects_an_unknown_top_level_key(record: dict[str, Any]) -> None:
    """additionalProperties is false, so a stray key is caught rather than carried."""
    broken = copy.deepcopy(record)
    broken["observability_record"]["extra_finding"] = "unreviewed"
    with pytest.raises(jsonschema.ValidationError):
        validate_record(broken)


def test_schema_rejects_a_rate_outside_zero_to_one(record: dict[str, Any]) -> None:
    broken = copy.deepcopy(record)
    broken["observability_record"]["emission"]["cells"][0]["raw_present"] = 1.5
    with pytest.raises(jsonschema.ValidationError):
        validate_record(broken)


def test_shipped_schema_is_itself_a_valid_json_schema() -> None:
    schema = record_schema()
    jsonschema.Draft202012Validator.check_schema(schema)


# --- writing ------------------------------------------------------------------------


def test_write_record_round_trips(record: dict[str, Any], tmp_path: Path) -> None:
    path = write_record(record, tmp_path / "nested" / "record.json")
    assert json.loads(path.read_text()) == record


def test_invalid_record_is_never_written(tmp_path: Path) -> None:
    """Validation runs before the write, so a bad record leaves no file behind.

    Order matters: a record written and then found invalid can still be read, copied
    and cited. One that was never written cannot.
    """
    path = tmp_path / "record.json"
    with pytest.raises(jsonschema.ValidationError):
        write_record({"observability_record": {"schema_version": "3.0"}}, path)
    assert not path.exists()
