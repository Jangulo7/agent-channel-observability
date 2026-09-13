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

from channels.bound import recall_ceiling
from channels.emission import (
    DENOMINATOR_STATEMENT,
    MIN_CELL_N,
    ArmProfile,
    EmissionCell,
    cell_rate,
    state_shares,
    uninspectable_share,
)
from channels.schema import CorpusDescription, ReasoningState

SCHEMA_VERSION = "4.0"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "results" / "record_schema.json"


def build_record(
    corpora: Sequence[CorpusDescription],
    cells: Sequence[EmissionCell],
    profiles: Sequence[ArmProfile],
    codebook_hash: str,
    codebook_version: int | None = None,
    preregistration_commit: str | None = None,
    stage2_recall: float = 1.0,
    inter_agent: Mapping[str, Any] | None = None,
    detectors: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble the observability record from measured objects, inventing nothing.

    Every field that has no measurement behind it is emitted as null with its status,
    never as a plausible default. `messages_authenticated` is the clearest case: no
    corpus this project reads supports authentication, and recording that as null is
    the honest form of the adversarial-channel finding. Provenance fields default
    to null for the same reason.
    """
    uninspectable = uninspectable_share(cells)
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
                "positional_profile": [_profile_block(arm) for arm in profiles],
                "uninspectable_share": uninspectable.rate,
            },
            "bound": [_bound_block(arm, stage2_recall) for arm in profiles],
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


def _arm_identity(arm: ArmProfile) -> dict[str, Any]:
    """The fields that name an arm and say what its profile keys mean."""
    return {
        "model": arm.model,
        "task_class": arm.task_class,
        "reasoning_effort": arm.reasoning_effort,
        "unit": arm.unit,
        "bin_width": arm.bin_width,
    }


def _profile_block(arm: ArmProfile) -> dict[str, Any]:
    """One arm's c(j), keyed by step or bin as `unit` says, every point with its n."""
    return {
        **_arm_identity(arm),
        "n_trajectories": arm.n_trajectories,
        "profile": {
            str(key): {
                "rate": rate.rate,
                "ci95": [rate.ci_low, rate.ci_high],
                "n_turns": rate.n,
                "low_n": rate.low_n,
                "interval_status": rate.status,
            }
            for key, rate in arm.points.items()
        },
    }


def _bound_block(arm: ArmProfile, stage2_recall: float) -> dict[str, Any]:
    """One arm's recall ceiling: action-weighted mean, by step, and at its worst step.

    The mean is the pooled raw_present share over every turn the arm took, not an
    unweighted mean over positions: averaging positions lets a thin late step count as
    much as a step every trajectory reached. The worst step is chosen among powered
    positions only, because the minimum over low-n points is mostly noise.
    """
    coverage = arm.raw_present.rate
    powered = arm.powered()
    worst = min(powered, key=lambda key: (powered[key].rate or 0.0, key), default=None)
    return {
        **_arm_identity(arm),
        "stage2_recall_assumed": stage2_recall,
        "mean_weighting": "action-weighted",
        "ceiling_mean_coverage": _ceiling(coverage, stage2_recall),
        "ceiling_by_step": {
            str(key): _ceiling(rate.rate, stage2_recall)
            for key, rate in arm.points.items()
        },
        "ceiling_at_worst_powered_step": (
            None if worst is None
            else {"step": worst,
                  "value": _ceiling(powered[worst].rate, stage2_recall)}
        ),
    }


def _ceiling(coverage: float | None, stage2_recall: float) -> float | None:
    """The recall ceiling at one coverage, or None where coverage was not measured."""
    return None if coverage is None else recall_ceiling(coverage, stage2_recall)


def _empty_inter_agent() -> dict[str, Any]:
    """The inter-agent block when nothing was measured. Nulls, not zeroes.

    A count of 0 would claim a measurement was made and came back empty, and
    `no_denominator` would claim a denominator was sought and not found. Neither
    happened: `not_measured` with null counts says no measurement was made at all.
    """
    return {
        "n_messages": None,
        "n_human_excluded": None,
        "denominator_code": "SHARE",
        "n_denominator": None,
        "rate_per_1000": None,
        "rate_status": "not_measured",
        "zero_case_upper_bound_95": None,
        "codes": None,
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
