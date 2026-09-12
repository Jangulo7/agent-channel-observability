"""The transcribed incident record: every row cited, no row a source of a rate."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from channels.errors import SchemaDiscoveryError
from channels.loaders.published_record import (
    PUBLISHED_RECORD_DIR,
    ZZ_PREFIX,
    PublishedRecordLoader,
    RateFromTypologyError,
)
from channels.schema import Channel, Provenance


def test_published_record_yaml_parses() -> None:
    """Every row validates, carries a non-empty source_ref, and uses the enums."""
    utterances = list(PublishedRecordLoader().load())
    assert utterances, "no rows transcribed"
    for utt in utterances:
        assert utt.source_ref, f"{utt.uid} has no source_ref"
        assert isinstance(utt.provenance, Provenance)
        assert isinstance(utt.channel, Channel)
        assert utt.text


def test_every_row_is_agent_prose_not_investigator_summary() -> None:
    """Only the agent's own tokens belong here, verbatim or redacted-partial."""
    for utt in PublishedRecordLoader().load():
        assert utt.provenance in {Provenance.VERBATIM, Provenance.REDACTED_PARTIAL}


def test_zz_prefix_consistent_across_sources() -> None:
    """The zz protocol convention appears in rows attributed to independent sources.

    The ASK/ANSWER strings carry a `zz` prefix. If that convention showed up in
    only one source it could be a transcription artefact of that report; showing
    up under separate attributions is weak evidence it is the agents' own framing.
    """
    zz_rows = [
        utt
        for utt in PublishedRecordLoader().load()
        if (utt.text or "").startswith(ZZ_PREFIX)
    ]
    assert zz_rows, "no zz-prefixed rows transcribed"
    for utt in zz_rows:
        assert utt.source_ref
    # Both halves of a dyad are independently attributed actors, not one speaker.
    actors = {utt.actor for utt in zz_rows}
    assert len(actors) >= 2, f"zz rows come from a single actor: {actors}"


def test_no_rate_may_be_computed_from_the_typology() -> None:
    """n=5 chosen by investigators for illustration is not a denominator."""
    with pytest.raises(RateFromTypologyError, match="hypothesis-generating"):
        PublishedRecordLoader().refuse_rate()


def test_unverified_citations_are_reported_not_hidden() -> None:
    caveats = " ".join(PublishedRecordLoader().describe().caveats)
    assert "unverified page reference" in caveats


def test_row_missing_source_ref_raises(tmp_path: Path) -> None:
    """A row without a citation is indistinguishable from an invented one."""
    (tmp_path / "synthetic.yaml").write_text(
        yaml.safe_dump(
            [
                {
                    "local_id": "synthetic_row",
                    "channel": "inter_agent_message",
                    "provenance": "verbatim",
                    "text": "SYNTHETIC PLACEHOLDER",
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(SchemaDiscoveryError, match="source_ref"):
        list(PublishedRecordLoader(root=tmp_path).load())


def test_row_with_provenance_outside_the_enum_raises(tmp_path: Path) -> None:
    (tmp_path / "synthetic.yaml").write_text(
        yaml.safe_dump(
            [
                {
                    "local_id": "synthetic_row",
                    "channel": "inter_agent_message",
                    "provenance": "hearsay",
                    "text": "SYNTHETIC PLACEHOLDER",
                    "source_ref": "synthetic fixture",
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(SchemaDiscoveryError, match="not in the Provenance enum"):
        list(PublishedRecordLoader(root=tmp_path).load())


def test_missing_transcription_raises_not_empty(tmp_path: Path) -> None:
    loader = PublishedRecordLoader(root=tmp_path / "absent")
    assert loader.available() is False
    with pytest.raises(SchemaDiscoveryError, match="no YAML under"):
        list(loader.load())


def test_committed_files_are_where_the_loader_looks() -> None:
    """Guards against the YAML drifting out from under the default root."""
    assert PUBLISHED_RECORD_DIR.is_dir()
    names = {path.name for path in PUBLISHED_RECORD_DIR.glob("*.yaml")}
    assert "influence_typology.yaml" in names
    assert "metr_hf_2026-08.yaml" in names


def test_zz_convention_spans_independent_agent_pairs() -> None:
    """The zz prefix must appear across DIFFERENT agent pairs, not one exchange.

    Verified 2026-09-12 against the source PDF: zz-prefixed ASK strings appear on
    p.44 (9180 -> LIBRAW42535) and p.33 (PHASEONE[big] -> PHASEONE10841). A
    convention seen in one exchange could be an artefact of how that exchange was
    transcribed; seen across separately-reported pairs it is evidence about the
    agents.
    """
    zz_rows = [
        utt
        for utt in PublishedRecordLoader().load()
        if (utt.text or "").startswith(ZZ_PREFIX)
    ]
    dyads = {str(utt.corpus_meta.get("dyad_id")) for utt in zz_rows}
    assert len(dyads) >= 2, f"zz rows all come from one exchange: {dyads}"


def test_every_citation_is_now_verified() -> None:
    """All ten rows have been checked against a source PDF held in data/METR.

    This asserted "2 of 10 unverified" until Johanna supplied
    risk-report-feb-mar-2026.pdf on 2026-09-12, which let INC-037 be located at
    p.124. If a future row is added without verification, the count moves off
    zero and this fails - which is the point.
    """
    caveats = " ".join(PublishedRecordLoader().describe().caveats)
    assert "0 of 10 rows carry an unverified" in caveats
