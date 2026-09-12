"""The machine-readable observability record and its JSON Schema.

The record is the artefact. A figure can be redrawn and a README can be rewritten, but
the record is what another researcher reads to check whether a number in the paper is
the number the code produced.
"""

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema

from channels.emission import (
    DENOMINATOR_STATEMENT,
    MIN_CELL_N,
    EmissionCell,
    cell_rate,
    state_shares,
    uninspectable_share,
)
from channels.schema import CorpusDescription, RateWithCI, ReasoningState

SCHEMA_VERSION = "3.0"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "results" / "record_schema.json"


def build_record(
    corpora: Sequence[CorpusDescription],
    cells: Sequence[EmissionCell],
    positional: Mapping[int, RateWithCI],
    codebook_hash: str,
    codebook_version: int = 1,
    preregistration_commit: str | None = None,
    stage2_recall: float = 1.0,
    inter_agent: Mapping[str, Any] | None = None,
    detectors: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble the observability record from measured objects, inventing nothing.

    Every field that has no measurement behind it is emitted as null with its status,
    never as a plausible default. `messages_authenticated` is the clearest case: no
    corpus this project reads supports authentication, and recording that as null is
    the honest form of the adversarial-channel finding.
    """
    uninspectable = uninspectable_share(cells)
    profile = {str(step): rate.rate for step, rate in positional.items()}
    return {
        "observability_record": {
            "schema_version": SCHEMA_VERSION,
            "codebook_version": codebook_version,
            "codebook_hash": codebook_hash,
            "preregistration_commit": preregistration_commit,
            "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "corpora": [_corpus_block(item) for item in corpora],
            "emission": {
                "denominator": DENOMINATOR_STATEMENT,
                "min_cell_n": MIN_CELL_N,
                "cells": [_cell_block(cell) for cell in cells],
                "positional_profile": profile,
                "uninspectable_share": uninspectable.rate,
            },
            "bound": _bound_block(positional, stage2_recall, cells),
            "inter_agent_channel": dict(inter_agent or _empty_inter_agent()),
            "detectors": [dict(item) for item in (detectors or [])],
        }
    }


def _corpus_block(description: CorpusDescription) -> dict[str, Any]:
    """One corpus entry. No corpus is reported without its description."""
    return {
        "name": description.name,
        "n_utterances": description.n_utterances,
        "n_actors": description.n_actors,
        "actor_concentration": description.actor_concentration,
        "source_hash": description.source_hash,
        "licence": description.licence,
        "caveats": list(description.caveats),
    }


def _cell_block(cell: EmissionCell) -> dict[str, Any]:
    """One emission cell, with its four shares, its interval and its low-n flag."""
    rate = cell_rate(cell)
    shares = state_shares(cell)
    return {
        "model": cell.model,
        "task_class": cell.task_class,
        "step_index": cell.step_index,
        "reasoning_effort": cell.reasoning_effort,
        "n_turns": cell.n_turns,
        "raw_present": shares[ReasoningState.RAW_PRESENT],
        "summary_only": shares[ReasoningState.SUMMARY_ONLY],
        "redacted": shares[ReasoningState.REDACTED],
        "absent": shares[ReasoningState.ABSENT],
        "ci95_raw_present": [rate.ci_low, rate.ci_high],
        "n_clusters": cell.n_clusters,
        "low_n": rate.low_n,
    }


def _bound_block(
    positional: Mapping[int, RateWithCI],
    stage2_recall: float,
    cells: Sequence[EmissionCell],
) -> dict[str, Any]:
    """The recall ceiling block, scalar and positional."""
    from channels.bound import recall_ceiling

    models = sorted({cell.model for cell in cells})
    rates = [rate.rate for rate in positional.values() if rate.rate is not None]
    mean_coverage = sum(rates) / len(rates) if rates else None
    return {
        "model": models[0] if len(models) == 1 else models,
        "stage2_recall_assumed": stage2_recall,
        "ceiling_mean_coverage": (
            recall_ceiling(mean_coverage, stage2_recall)
            if mean_coverage is not None
            else None
        ),
        "ceiling_by_step": {
            str(step): (
                recall_ceiling(rate.rate, stage2_recall)
                if rate.rate is not None
                else None
            )
            for step, rate in positional.items()
        },
    }


def _empty_inter_agent() -> dict[str, Any]:
    """The inter-agent block when nothing was measured. Nulls, not zeroes.

    A rate of 0 would claim a measurement was made and came back empty. `null` with
    `rate_status` says no measurement was made at all.
    """
    return {
        "n_messages": 0,
        "n_human_excluded": 0,
        "denominator_code": "SHARE",
        "n_denominator": 0,
        "rate_per_1000": None,
        "rate_status": "no_denominator",
        "zero_case_upper_bound_95": None,
        "codes": {"OBJ": 0, "REF": 0, "ESC": 0, "WARN": 0, "NORM": 0},
        # No corpus this project reads carries an authenticated sender field.
        # Recording that as null rather than omitting it is the finding.
        "messages_authenticated": None,
    }


def record_schema() -> dict[str, Any]:
    """The JSON Schema the record is validated against."""
    loaded = json.loads(SCHEMA_PATH.read_text())
    if not isinstance(loaded, dict):
        raise TypeError(f"{SCHEMA_PATH} did not parse to a JSON object")
    return loaded


def validate_record(record: Mapping[str, Any]) -> None:
    """Raise jsonschema.ValidationError if the record does not match the schema."""
    jsonschema.validate(instance=record, schema=record_schema())


def write_record(record: Mapping[str, Any], path: Path) -> Path:
    """Validate, then write. Validation runs first so an invalid record never ships."""
    validate_record(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=False) + "\n")
    return path
