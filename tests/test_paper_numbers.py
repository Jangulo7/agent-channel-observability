"""Every number the paper reports is derivable from a committed record.

The paper claims its numbers regenerate from the records. This test makes that
property checkable rather than aspirational: it runs the registry's derivations and
compares them with the renderings the paper uses. It needs no manuscript, so it runs
wherever the records do.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "check_paper_numbers",
    Path(__file__).parents[1] / "scripts" / "check_paper_numbers.py",
)
assert _spec and _spec.loader
check_paper_numbers = importlib.util.module_from_spec(_spec)
# The script defines a dataclass, which looks its module up in sys.modules.
sys.modules[_spec.name] = check_paper_numbers
_spec.loader.exec_module(check_paper_numbers)


def test_every_registered_number_matches_its_record() -> None:
    """The whole point: a number in the paper that drifts from its record fails here."""
    problems = check_paper_numbers.self_check()
    assert not problems, "\n".join(problems)


def test_registry_is_not_empty_and_has_no_duplicate_labels() -> None:
    """A registry that silently emptied would make the test above vacuous."""
    entries = check_paper_numbers.registry()
    assert len(entries) >= 60
    labels = [entry.label for entry in entries]
    assert len(labels) == len(set(labels))


def test_registry_covers_every_record_the_findings_rest_on() -> None:
    """No record behind a headline finding may go unrepresented in the registry."""
    records = {entry.record for entry in check_paper_numbers.registry()}
    assert {
        "turn_boundary_followup",
        "monitor_experiment_qwen3",
        "swebench_longhorizon",
        "observability_record",
    } <= records


def test_golden_subset_of_headline_numbers() -> None:
    """The numbers a reader is most likely to quote, pinned individually."""
    by_label = {e.label: e for e in check_paper_numbers.registry()}
    expected = {
        "haiku header off, post-tool n": "661",
        "haiku header on, post-tool readable": "667",
        "nemotron DeepInfra, whole channel n": "625",
        "nemotron Phala, whole channel readable": "421",
        "step-0 CoT visible k/n": "39/42",
        "step-0 CoT dark k/n": "0/38",
        "dark-arm reasoning abstentions": "144/155",
        "sweep token-accounting inconsistencies": "58",
    }
    for label, value in expected.items():
        assert by_label[label].derivation() == value, label


def test_manuscript_check_reports_a_missing_number() -> None:
    """The checker must be able to fail; one that cannot is decorative."""
    paper = Path(__file__).parents[1] / check_paper_numbers.PAPER
    if not paper.exists():
        pytest.skip("manuscript is outside the repository in this checkout")
    missing = check_paper_numbers.check_manuscript(paper)
    assert not missing, "\n".join(missing)
