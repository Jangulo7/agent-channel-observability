"""The command line, exercised on synthetic corpora only.

Every path here runs against an obviously-fake transcript written into `tmp_path`, so
the suite never depends on a real corpus being present on the machine. The behaviours
under test are the ones a CI run depends on: a missing corpus is *named* rather than
silently skipped, a run with nothing to measure refuses rather than emitting an empty
record, and `gate` exits non-zero when it could not evaluate.
"""

import json
from pathlib import Path

import pytest

from channels.cli import main

# One obviously synthetic trajectory in the Mythos transcript's row format: four
# assistant turns, two of which carry in-band <thinking>, giving raw_present = 0.5.
SYNTHETIC_ROWS: list[dict[str, object]] = [
    {
        "record": "metadata",
        "title": "SYNTHETIC TRANSCRIPT — NOT REAL DATA",
        "subtitle": "fixture",
        "notice": "fixture",
        "about": "fixture",
        "modifications": "fixture",
    },
    {
        "record": "message", "index": 1, "role": "Assistant", "type": "TextMessage",
        "timestamp": "2026-01-01T00:00:00Z",
        "content": "<thinking>SYNTHETIC REASONING ONE</thinking>SYNTHETIC OUTPUT",
    },
    {
        "record": "message", "index": 2, "role": "Assistant", "type": "ToolMessage",
        "timestamp": "2026-01-01T00:00:01Z",
        "tool_name": "synthetic_tool", "tool_call": "{}", "tool_result": "SYNTHETIC",
    },
    {
        "record": "message", "index": 3, "role": "Assistant", "type": "TextMessage",
        "timestamp": "2026-01-01T00:00:02Z",
        "content": "<thinking>SYNTHETIC REASONING TWO</thinking>SYNTHETIC OUTPUT",
    },
    {
        "record": "message", "index": 4, "role": "Assistant", "type": "ToolMessage",
        "timestamp": "2026-01-01T00:00:03Z",
        "tool_name": "synthetic_tool", "tool_call": "{}", "tool_result": "SYNTHETIC",
    },
]


@pytest.fixture
def transcript(tmp_path: Path) -> Path:
    """An obviously synthetic transcript in the real row format."""
    path = tmp_path / "synthetic_transcript.jsonl"
    path.write_text(
        "\n".join(json.dumps(row) for row in SYNTHETIC_ROWS) + "\n", encoding="utf-8"
    )
    return path


def args(transcript: Path, *extra: str) -> list[str]:
    """CLI arguments pinned to the synthetic corpus and away from the real one."""
    return [
        "--mythos", str(transcript),
        "--inspect-logs", str(transcript.parent / "no_such_logs_dir"),
        *extra,
    ]


# --- describe ---------------------------------------------------------------------


def test_describe_reports_an_available_corpus(
    transcript: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["describe", *args(transcript)]) == 0
    out = capsys.readouterr().out
    assert "mythos_transcript" in out
    assert "utterances        4" in out


def test_describe_names_the_missing_corpus_and_the_path_checked(
    transcript: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An absent corpus is reported by name with the path, never skipped silently.

    A run that quietly omits a corpus invites the reader to assume it was empty. The
    exact path checked is printed so the gap is actionable rather than mysterious.
    """
    assert main(["describe", *args(transcript)]) == 0
    out = capsys.readouterr().out
    assert "NOT AVAILABLE: inspect_logs" in out
    assert "no_such_logs_dir" in out


def test_describe_carries_the_corpus_caveats(
    transcript: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["describe", *args(transcript)]) == 0
    assert "n=1 trajectory" in capsys.readouterr().out


# --- measure ----------------------------------------------------------------------


def test_measure_writes_a_valid_record_and_both_figures(
    transcript: Path, tmp_path: Path
) -> None:
    results = tmp_path / "results"
    assert main(["measure", *args(transcript, "--results", str(results))]) == 0

    record = json.loads((results / "observability_record.json").read_text())
    assert record["observability_record"]["emission"]["cells"]
    assert (results / "figures" / "figure1_emission_states.png").is_file()
    assert (results / "figures" / "figure2_recall_ceiling.png").is_file()


def test_measured_rate_matches_the_synthetic_trajectory(
    transcript: Path, tmp_path: Path
) -> None:
    """Two of four synthetic assistant turns carry reasoning, so the share is 0.5.

    This pins the whole chain — loader, classifier, cells, record — to a number that
    can be counted by hand in the fixture above.
    """
    results = tmp_path / "results"
    main(["measure", *args(transcript, "--results", str(results))])
    record = json.loads((results / "observability_record.json").read_text())
    assert record["observability_record"]["emission"]["uninspectable_share"] == 0.5


def test_measure_records_the_codebook_hash_as_a_todo_until_it_exists(
    transcript: Path, tmp_path: Path
) -> None:
    """No codebook yet means an explicit TODO in the record, not a blank or a guess."""
    results = tmp_path / "results"
    main(["measure", *args(transcript, "--results", str(results))])
    record = json.loads((results / "observability_record.json").read_text())
    assert record["observability_record"]["codebook_hash"].startswith("TODO(johanna)")


def test_measure_refuses_when_no_corpus_is_available(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nothing to measure exits 2 and writes no record.

    An empty record is worse than no record: it looks like a measurement that found
    nothing, rather than a run that read nothing.
    """
    results = tmp_path / "results"
    code = main([
        "measure",
        "--mythos", str(tmp_path / "no_such_transcript.jsonl"),
        "--inspect-logs", str(tmp_path / "no_such_logs_dir"),
        "--results", str(results),
    ])
    assert code == 2
    assert "no corpus was available" in capsys.readouterr().err
    assert not (results / "observability_record.json").exists()


# --- gate -------------------------------------------------------------------------


def test_gate_exits_non_zero_when_a_gate_fails(
    transcript: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """0.5 coverage against a 0.5 floor still fails, on the unregistered codebook."""
    assert main(["gate", *args(transcript)]) == 1
    assert "codebook_drift" in capsys.readouterr().out


def test_gate_exits_non_zero_when_nothing_could_be_measured(tmp_path: Path) -> None:
    """No cells is UNEVALUABLE, and un-evaluable stops the build.

    This is the CLI end of the rule that an uninspectable sample is a failure and not
    a dropped denominator: a run that measured nothing must not report success.
    """
    code = main([
        "gate",
        "--mythos", str(tmp_path / "no_such_transcript.jsonl"),
        "--inspect-logs", str(tmp_path / "no_such_logs_dir"),
    ])
    assert code == 1


def test_gate_prints_the_worst_stratum(
    transcript: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["gate", *args(transcript)])
    out = capsys.readouterr().out
    assert "worst stratum" in out
    assert "mythos-5/effort=None" in out


# --- error handling ----------------------------------------------------------------


def test_domain_errors_exit_two_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A malformed corpus raises a ChannelsError, which prints plainly and exits 2."""
    path = tmp_path / "wrong_shape.jsonl"
    path.write_text(json.dumps({"record": "not_a_message"}) + "\n", encoding="utf-8")

    assert main(["describe", *args(path)]) == 2
    assert "error:" in capsys.readouterr().err


def test_no_subcommand_is_rejected() -> None:
    with pytest.raises(SystemExit):
        main([])
