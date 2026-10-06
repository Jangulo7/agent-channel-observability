"""The four schema invariants from spec §3, one test each, plus schema coverage."""

import ast
import json
from pathlib import Path

import jsonschema
import pytest

from channels.errors import ProvenanceError
from channels.provenance import (
    PRIMARY_ELIGIBLE,
    assert_primary_eligible,
    for_primary,
)
from channels.record import (
    SCHEMA_COVERED_RECORDS,
    SCHEMA_EXEMPT_RECORDS,
    SCHEMA_PATH,
    record_schema,
)
from channels.schema import Channel, Provenance, Utterance

SRC = Path(__file__).resolve().parents[1] / "src" / "channels"
RESULTS = Path(__file__).resolve().parents[1] / "results"


def _utt(uid: str, provenance: Provenance, channel: Channel) -> Utterance:
    """Build a minimal synthetic utterance. Synthetic by design, obviously so."""
    return Utterance(
        uid=uid,
        corpus="synthetic_fixture",
        channel=channel,
        provenance=provenance,
        text="SYNTHETIC FIXTURE TEXT",
        actor="fixture_actor_a",
    )


def test_paraphrase_excluded_from_primary() -> None:
    kept, dropped = for_primary(
        [
            _utt("s:1", Provenance.VERBATIM, Channel.INTER_AGENT_MESSAGE),
            _utt("s:2", Provenance.PARAPHRASE, Channel.INTER_AGENT_MESSAGE),
            _utt("s:3", Provenance.UNCERTAIN_MEANING, Channel.INTER_AGENT_MESSAGE),
            _utt("s:4", Provenance.INVESTIGATOR_SUMMARY, Channel.INTER_AGENT_MESSAGE),
        ]
    )
    assert [u.uid for u in kept] == ["s:1"]
    assert sorted(dropped) == [
        "provenance=investigator_summary",
        "provenance=paraphrase",
        "provenance=uncertain_meaning",
    ]


def test_redacted_partial_stays_eligible() -> None:
    """Redaction markers survive, so the text is still auditable evidence."""
    assert Provenance.REDACTED_PARTIAL in PRIMARY_ELIGIBLE


def test_human_messages_excluded_from_inter_agent_rate() -> None:
    kept, dropped = for_primary(
        [
            _utt("s:1", Provenance.VERBATIM, Channel.INTER_AGENT_MESSAGE),
            _utt("s:2", Provenance.VERBATIM, Channel.HUMAN_MESSAGE),
            _utt("s:3", Provenance.VERBATIM, Channel.SYSTEM_MESSAGE),
        ]
    )
    assert [u.uid for u in kept] == ["s:1"]
    assert set(dropped) == {"channel=human_message", "channel=system_message"}


def test_assert_primary_eligible_names_offenders() -> None:
    bad = _utt("s:9", Provenance.PARAPHRASE, Channel.INTER_AGENT_MESSAGE)
    with pytest.raises(ProvenanceError) as excinfo:
        assert_primary_eligible([bad])
    assert "s:9" in str(excinfo.value)
    assert "paraphrase" in str(excinfo.value)


def test_schema_is_a_leaf_module() -> None:
    """schema.py must not import from loaders/, tree.py or detect.py."""
    tree = ast.parse((SRC / "schema.py").read_text())
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    forbidden = [
        m for m in imported if "loaders" in m or m.endswith(("tree", "detect"))
    ]
    assert forbidden == [], f"schema.py must stay a leaf, but imports {forbidden}"


# --- Schema coverage: no record under results/ may be silently unvalidated. ----------


def test_every_covered_record_validates_against_the_committed_schema() -> None:
    """Schema 4.2's point: all five measurement records, not just the first one.

    Before 4.2 the schema described only the observability record, which left every
    record behind the paper's headline findings - both monitor arms, the header and
    route contrasts, the long-horizon depth arm - unchecked.
    """
    schema = record_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    for name in SCHEMA_COVERED_RECORDS:
        path = RESULTS / name
        assert path.exists(), f"{name} is listed as covered but is missing"
        jsonschema.validate(instance=json.loads(path.read_text()), schema=schema)


def test_no_record_is_neither_covered_nor_exempt() -> None:
    """Every results/*.json is either schema-covered or exempt for a stated reason.

    This is the guard that keeps the 4.2 gap from reopening: a new record cannot be
    added to results/ without either a schema branch or an explicit exemption, so it
    cannot arrive unvalidated by omission.
    """
    accounted = {
        (RESULTS / name).resolve()
        for name in (*SCHEMA_COVERED_RECORDS, *SCHEMA_EXEMPT_RECORDS)
    }
    accounted.add(SCHEMA_PATH.resolve())
    unaccounted = sorted(
        str(path.relative_to(RESULTS))
        for path in RESULTS.rglob("*.json")
        if path.resolve() not in accounted
    )
    assert not unaccounted, (
        f"these records are neither schema-covered nor exempt: {unaccounted}. "
        "Add a schema branch and list them in SCHEMA_COVERED_RECORDS, or list them "
        "in SCHEMA_EXEMPT_RECORDS with the reason."
    )
