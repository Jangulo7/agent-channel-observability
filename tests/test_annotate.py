"""Annotation samples are reproducible, blind, and text-free."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from channels.annotate import (
    MESSAGE_CODE,
    REVERT_VALIDITY,
    AnnotationRecord,
    Label,
    cohens_kappa,
    draw_sample,
    load_record,
    sample_id_for,
)
from channels.schema import Channel, Provenance, Utterance


def _population(n: int) -> list[Utterance]:
    """Synthetic utterances, deliberately out of uid order."""
    return [
        Utterance(
            uid=f"synthetic:{index:04d}",
            corpus="synthetic_fixture",
            channel=Channel.ARTEFACT_EDIT,
            provenance=Provenance.REDACTED_PARTIAL,
            text=None,
            actor=f"agent_{index % 5}",
            thread_id=f"page_{index % 9}",
        )
        for index in reversed(range(n))
    ]


def test_same_seed_gives_two_coders_the_same_items() -> None:
    """Cohen's kappa needs matched pairs, so the sample must be deterministic."""
    population = _population(500)
    first = draw_sample(population, REVERT_VALIDITY, 50, seed=7)
    second = draw_sample(population, REVERT_VALIDITY, 50, seed=7)
    assert [u.uid for u in first] == [u.uid for u in second]


def test_sample_is_independent_of_population_order() -> None:
    """The corpus arrives in file order; two readers must still agree.

    Without the sort inside draw_sample, shuffling differently-ordered lists from
    the same seed would hand two coders different items while both believed they
    shared a sample.
    """
    population = _population(300)
    shuffled = list(reversed(population))
    assert [u.uid for u in draw_sample(population, MESSAGE_CODE, 40, seed=3)] == [
        u.uid for u in draw_sample(shuffled, MESSAGE_CODE, 40, seed=3)
    ]


def test_different_seeds_give_different_samples() -> None:
    population = _population(500)
    a = {u.uid for u in draw_sample(population, REVERT_VALIDITY, 50, seed=1)}
    b = {u.uid for u in draw_sample(population, REVERT_VALIDITY, 50, seed=2)}
    assert a != b


def test_sample_larger_than_population_raises() -> None:
    with pytest.raises(ValueError, match="exceeds the population"):
        draw_sample(_population(10), REVERT_VALIDITY, 50, seed=1)


def test_saved_record_contains_no_corpus_text(tmp_path: Path) -> None:
    """results/annotations/ is publishable, so no utterance text may reach it."""
    record = AnnotationRecord(
        sample_id=sample_id_for(REVERT_VALIDITY, 2, 7),
        task=REVERT_VALIDITY.name,
        codebook_hash="sha256:synthetic",
        coder_id="coder_a",
        n_requested=2,
        seed=7,
        labels=[Label("synthetic:0001", "d", 4.2, "2026-01-01T00:00:00Z")],
    )
    text = record.save(tmp_path).read_text(encoding="utf-8")
    assert "synthetic:0001" in text
    for field in ("text", "body", "change_summary", "message"):
        assert f'"{field}"' not in text


def test_record_round_trips_and_resumes(tmp_path: Path) -> None:
    record = AnnotationRecord(
        sample_id="s", task=REVERT_VALIDITY.name, codebook_hash="sha256:x",
        coder_id="coder_a", n_requested=3, seed=7,
        labels=[Label("synthetic:0001", "d", 1.0, "2026-01-01T00:00:00Z")],
    )
    loaded = load_record(record.save(tmp_path))
    assert loaded.coded_uids == {"synthetic:0001"}
    assert loaded.labels[0].choice == "d"


def test_kappa_is_zero_when_agreement_is_only_chance() -> None:
    """Percent agreement flatters a skewed task; kappa is the correction."""
    first = {f"u{i}": ("d" if i < 9 else "h") for i in range(10)}
    second = {f"u{i}": "d" for i in range(10)}
    kappa, n = cohens_kappa(first, second)
    assert n == 10
    # Second coder used one category only, so nothing above chance was shown.
    assert kappa == pytest.approx(0.0)


def test_kappa_is_one_on_perfect_agreement_across_two_categories() -> None:
    first = {f"u{i}": ("d" if i % 2 else "h") for i in range(10)}
    kappa, _ = cohens_kappa(first, dict(first))
    assert kappa == pytest.approx(1.0)


def test_kappa_undefined_when_both_used_a_single_category() -> None:
    """Total agreement AND total chance agreement is not perfect reliability."""
    labels = {f"u{i}": "d" for i in range(10)}
    kappa, _ = cohens_kappa(labels, dict(labels))
    assert math.isnan(kappa)


def test_kappa_requires_overlapping_items() -> None:
    with pytest.raises(ValueError, match="share no labelled items"):
        cohens_kappa({"a": "d"}, {"b": "d"})


def test_every_task_offers_an_unclear_option() -> None:
    """A coder with no 'cannot tell' answer is forced to guess."""
    for task in (REVERT_VALIDITY, MESSAGE_CODE):
        assert "u" in task.choices


def test_no_task_uses_a_reserved_control_key() -> None:
    """Skip is Enter ('') and quit is '.'; no codebook key may collide with them.

    Regression for the 2026-09-13 incident: the annotate tool bound skip to 's',
    which is the message task's SHARE code, so every SHARE press was dropped.
    """
    from channels.annotate import TASKS

    reserved = {"", "."}
    for name, task in TASKS.items():
        clash = reserved & set(task.choice_keys())
        assert not clash, f"task {name} uses reserved control key(s) {clash}"
