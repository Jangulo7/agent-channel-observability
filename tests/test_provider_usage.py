"""Produced is not readable: pairing turns to calls, and carrying the evidence through.

Every object here is a synthetic stand-in; no log is read. The pairing tests exist
because positional pairing is wrong on real logs in two known ways (interleaved
scorer calls, errored first attempts), and a count attributed to the wrong turn
would be a fabricated measurement.
"""

import copy
from pathlib import Path

import jsonschema
import pytest

from channels.coverage import observe_turns
from channels.emission import (
    EmissionCell,
    arm_profiles,
    build_cells,
    evidence_shares,
    state_by_evidence,
)
from channels.errors import InconsistentCountsError, InvalidTokenCountError
from channels.figures import figure_one
from channels.loaders.inspect_logs import PairingTally, usage_caveats
from channels.provider_usage import pair_sample, pair_turns
from channels.record import build_record, validate_record
from channels.schema import (
    CorpusDescription,
    DeliberationEvidence,
    ReasoningState,
    TurnObservation,
    deliberation_evidence,
)

from .fixtures.synthetic import (
    FakeMessage,
    FakeReasoningBlock,
    FakeSample,
    fake_call,
    turns,
)

RAW = ReasoningState.RAW_PRESENT
REDACTED = ReasoningState.REDACTED
ABSENT = ReasoningState.ABSENT
PRODUCED = DeliberationEvidence.PRODUCED
NOT_PRODUCED = DeliberationEvidence.NOT_PRODUCED
UNKNOWN = DeliberationEvidence.UNKNOWN

CORPUS = CorpusDescription(
    name="synthetic_corpus", n_utterances=0, n_actors=1, actor_concentration=None,
    date_range=None, source_hash="sha256:SYNTHETIC", licence="synthetic fixture",
    caveats=("obviously synthetic; not a measurement",),
)


def _assistant(message_id: str | None, content: object = "SYNTHETIC") -> FakeMessage:
    return FakeMessage(role="assistant", content=content, id=message_id)


# --- pairing -------------------------------------------------------------------------


def test_interleaved_scorer_call_is_skipped_not_shifted_onto_a_turn() -> None:
    """A scorer call between two turns must not take the second turn's count."""
    turns_ = [_assistant("SYN-T0"), _assistant("SYN-T1")]
    calls = [
        fake_call("SYN-T0", 40),
        fake_call("SYN-SCORER", 0, model="SYNTHETIC-SCORER"),
        fake_call("SYN-T1", None),
    ]
    pairing = pair_turns(turns_, calls)
    assert pairing.call_for_turn == (0, 2)
    assert pairing.tokens == (40, None)
    assert pairing.unmatched_calls == (1,)
    assert pairing.trailing_calls() == ()
    assert pairing.paired_without_count == 1


def test_trailing_call_with_no_message_is_unmatched_and_trailing() -> None:
    turns_ = [_assistant("SYN-T0")]
    calls = [fake_call("SYN-T0", 0), fake_call("SYN-NEVER-WRITTEN", 12)]
    pairing = pair_turns(turns_, calls)
    assert pairing.tokens == (0,)
    assert pairing.unmatched_calls == (1,)
    assert pairing.trailing_calls() == (1,)
    assert pairing.unpaired_turns == ()


def test_errored_attempt_before_the_real_call_does_not_shift_pairing() -> None:
    turns_ = [_assistant("SYN-T0")]
    calls = [
        fake_call("SYN-FAILED", None, usage=False, error="SYNTHETIC ERROR"),
        fake_call("SYN-T0", 7),
    ]
    pairing = pair_turns(turns_, calls)
    assert pairing.tokens == (7,)
    assert pairing.unmatched_calls == (0,)


def test_turn_without_an_id_or_a_matching_call_is_never_guessed() -> None:
    """Same number of calls and turns, but no id agreement: every count is None."""
    turns_ = [_assistant(None), _assistant("SYN-T1")]
    calls = [fake_call("SYN-X", 30), fake_call("SYN-Y", 0)]
    pairing = pair_turns(turns_, calls)
    assert pairing.tokens == (None, None)
    assert pairing.unpaired_turns == (0, 1)
    assert pairing.unmatched_calls == (0, 1)


def test_shared_message_id_is_ambiguous_and_unknown() -> None:
    turns_ = [_assistant("SYN-T0")]
    calls = [fake_call("SYN-T0", 5), fake_call("SYN-T0", 0)]
    pairing = pair_turns(turns_, calls)
    assert pairing.tokens == (None,)
    assert pairing.ambiguous_turns == (0,)


def test_negative_count_raises_rather_than_being_classified() -> None:
    with pytest.raises(InvalidTokenCountError):
        pair_turns([_assistant("SYN-T0")], [fake_call("SYN-T0", -1)])
    with pytest.raises(InvalidTokenCountError):
        deliberation_evidence(
            TurnObservation("SYNTHETIC", "synthetic_task", 0, ABSENT,
                            provider_reasoning_tokens=-3)
        )


# --- the evidence value --------------------------------------------------------------


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [(None, UNKNOWN), (0, NOT_PRODUCED), (1, PRODUCED), (900, PRODUCED)],
)
def test_deliberation_evidence_from_tokens(
    tokens: int | None, expected: DeliberationEvidence
) -> None:
    observation = TurnObservation(
        "SYNTHETIC", "synthetic_task", 0, ABSENT, provider_reasoning_tokens=tokens
    )
    assert observation.deliberation_evidence is expected


def test_observe_turns_carries_tokens_missing_usage_and_explicit_zero() -> None:
    sample = FakeSample(
        id="SYNTHETIC_SAMPLE_1",
        messages=[
            FakeMessage(role="user", content="SYNTHETIC USER"),
            _assistant("SYN-T0", [FakeReasoningBlock(redacted=True)]),
            FakeMessage(role="tool", content="SYNTHETIC RESULT"),
            _assistant("SYN-T1"),
            _assistant("SYN-T2"),
        ],
        events=[
            fake_call("SYN-T0", 64),
            fake_call("SYN-T1", 0),
            fake_call("SYN-T2", None, usage=False),
        ],
    )
    observed = observe_turns(sample, "SYNTHETIC-MODEL-A", "synthetic_task")
    assert [o.provider_reasoning_tokens for o in observed] == [64, 0, None]
    assert [o.deliberation_evidence for o in observed] == [
        PRODUCED, NOT_PRODUCED, UNKNOWN
    ]
    assert [o.state for o in observed] == [REDACTED, ABSENT, ABSENT]
    assert pair_sample(sample).paired_without_count == 1


def test_sample_without_events_is_all_unknown() -> None:
    sample = FakeSample(id="SYNTHETIC", messages=[_assistant("SYN-T0")])
    (observation,) = observe_turns(sample, "SYNTHETIC-MODEL-A", "synthetic_task")
    assert observation.provider_reasoning_tokens is None
    assert observation.deliberation_evidence is UNKNOWN


# --- cells, shares, record -----------------------------------------------------------


def _observation(
    state: ReasoningState, tokens: int | None, sample_id: str
) -> TurnObservation:
    return TurnObservation(
        "SYNTHETIC-MODEL-A", "synthetic_task", 0, state,
        sample_id=sample_id, provider_reasoning_tokens=tokens,
    )


def _mixed_observations() -> list[TurnObservation]:
    """10 turns: 4 produced (3 raw, 1 redacted), 4 not produced (absent), 2 unknown."""
    specs = [(RAW, 50)] * 3 + [(REDACTED, 20)] + [(ABSENT, 0)] * 4
    specs += [(ABSENT, None)] * 2
    return [
        _observation(state, tokens, f"SYNTHETIC_TRAJ_{index}")
        for index, (state, tokens) in enumerate(specs)
    ]


def test_cell_carries_the_evidence_by_state_cross_tab() -> None:
    (cell,) = build_cells(_mixed_observations())
    table = state_by_evidence(cell)
    assert table[PRODUCED] == {RAW: 3, ReasoningState.SUMMARY_ONLY: 0, REDACTED: 1,
                               ABSENT: 0}
    assert table[NOT_PRODUCED][ABSENT] == 4
    assert table[UNKNOWN][ABSENT] == 2
    assert sum(sum(row.values()) for row in table.values()) == cell.n_turns


def test_arm_shares_separate_produced_from_readable() -> None:
    shares = evidence_shares(build_cells(_mixed_observations()))
    assert shares.produced_share == pytest.approx(0.4)
    assert shares.not_produced_share == pytest.approx(0.4)
    assert shares.unknown_share == pytest.approx(0.2)
    assert shares.readable_given_produced == pytest.approx(0.75)


def test_shares_are_null_when_every_count_is_unknown() -> None:
    shares = evidence_shares(build_cells(turns([ABSENT, ABSENT])))
    assert shares.produced_share is None
    assert shares.not_produced_share is None
    assert shares.readable_given_produced is None
    assert shares.unknown_share == 1.0
    # Cells built from observations carry token evidence, so a zero is a real count.
    assert shares.token_accounting_inconsistent == 0


def test_inconsistent_cross_tab_is_refused() -> None:
    counts = dict.fromkeys(ReasoningState, 0) | {RAW: 2}
    evidence = {e: dict.fromkeys(ReasoningState, 0) for e in DeliberationEvidence}
    evidence[PRODUCED][RAW] = 1
    with pytest.raises(InconsistentCountsError):
        EmissionCell("SYNTHETIC", "synthetic_task", 0, None, 2, counts,
                     evidence=evidence)
    # Returned content filed as not produced contradicts the evidence hierarchy.
    evidence[PRODUCED][RAW] = 0
    evidence[NOT_PRODUCED][RAW] = 2
    with pytest.raises(InconsistentCountsError):
        EmissionCell("SYNTHETIC", "synthetic_task", 0, None, 2, counts,
                     evidence=evidence)


# --- evidence hierarchy: content outranks the token count ---------------------------


@pytest.mark.parametrize(
    ("state", "tokens"),
    [
        (state, tokens)
        for state in (RAW, REDACTED, ReasoningState.SUMMARY_ONLY)
        for tokens in (None, 0, 30)
        # REDACTED with no count is UNKNOWN; its own test covers that case.
        if not (state is REDACTED and tokens is None)
    ],
)
def test_rule_1_returned_content_is_produced_whatever_the_count(
    state: ReasoningState, tokens: int | None
) -> None:
    """Readable or summary content is PRODUCED at any count; so is REDACTED with one.

    REDACTED with no count is the one exception (UNKNOWN), tested separately in
    test_redaction_without_a_token_count_is_unknown_not_produced.
    """
    observation = TurnObservation(
        "SYNTHETIC", "synthetic_task", 0, state, provider_reasoning_tokens=tokens
    )
    assert observation.deliberation_evidence is PRODUCED
    assert observation.token_accounting_inconsistent is (tokens == 0)


def test_rule_2_absent_turn_falls_back_to_the_count() -> None:
    evidence = [
        TurnObservation("SYNTHETIC", "synthetic_task", 0, ABSENT,
                        provider_reasoning_tokens=tokens).deliberation_evidence
        for tokens in (12, 0, None)
    ]
    assert evidence == [PRODUCED, NOT_PRODUCED, UNKNOWN]


def test_rule_3_content_with_zero_tokens_is_counted_and_surfaced() -> None:
    """Readable reasoning with reasoning_tokens == 0: PRODUCED, and counted apart."""
    observations = [
        _observation(RAW, 0, "SYNTHETIC_TRAJ_A"),
        _observation(RAW, 0, "SYNTHETIC_TRAJ_B"),
        _observation(REDACTED, 0, "SYNTHETIC_TRAJ_C"),
        _observation(RAW, 44, "SYNTHETIC_TRAJ_D"),
        _observation(ABSENT, 0, "SYNTHETIC_TRAJ_E"),
    ]
    (cell,) = build_cells(observations)
    assert cell.token_accounting_inconsistent == 3
    assert state_by_evidence(cell)[PRODUCED][RAW] == 3
    assert state_by_evidence(cell)[NOT_PRODUCED][ABSENT] == 1
    record = build_record(
        corpora=[CORPUS], cells=[cell], profiles=arm_profiles([cell]),
        codebook_hash="sha256:SYNTHETIC",
    )
    validate_record(record)
    inner = record["observability_record"]
    assert inner["emission"]["cells"][0]["token_accounting_inconsistent"] == 3
    assert inner["bound"][0]["token_accounting_inconsistent"] == 3
    assert inner["bound"][0]["readable_given_produced"] == pytest.approx(0.75)
    caveats = " | ".join(usage_caveats(observations, PairingTally()))
    assert "token_accounting_inconsistent: 3 turn(s)" in caveats


def test_cell_without_token_evidence_reports_inconsistency_as_null() -> None:
    counts = dict.fromkeys(ReasoningState, 0) | {RAW: 1, ABSENT: 1}
    cell = EmissionCell("SYNTHETIC", "synthetic_task", 0, None, 2, counts)
    assert evidence_shares([cell]).token_accounting_inconsistent is None
    assert state_by_evidence(cell)[PRODUCED][RAW] == 1
    assert state_by_evidence(cell)[UNKNOWN][ABSENT] == 1


def _record() -> dict:
    cells = build_cells(_mixed_observations())
    return build_record(
        corpora=[CORPUS], cells=cells, profiles=arm_profiles(cells),
        codebook_hash="sha256:SYNTHETIC",
    )


def test_record_carries_cross_tab_and_arm_shares_and_validates() -> None:
    record = _record()
    validate_record(record)
    inner = record["observability_record"]
    assert inner["schema_version"] == "4.1"
    (cell,) = inner["emission"]["cells"]
    assert cell["deliberation_evidence"] == {
        "produced": 4, "not_produced": 4, "unknown": 2
    }
    assert cell["state_by_evidence"]["produced"] == {
        "raw_present": 3, "summary_only": 0, "redacted": 1, "absent": 0
    }
    assert cell["state_by_evidence"]["not_produced"]["absent"] == 4
    (bound,) = inner["bound"]
    assert bound["produced_share"] == pytest.approx(0.4)
    assert bound["readable_given_produced"] == pytest.approx(0.75)
    assert bound["not_produced_share"] == pytest.approx(0.4)
    assert bound["unknown_share"] == pytest.approx(0.2)


def test_schema_requires_and_bounds_the_new_fields() -> None:
    record = _record()
    for mutate in (
        lambda r: r["emission"]["cells"][0].pop("state_by_evidence"),
        lambda r: r["emission"]["cells"][0]["deliberation_evidence"].pop("unknown"),
        lambda r: r["emission"]["cells"][0]["state_by_evidence"]["produced"].update(
            {"hidden": 1}
        ),
        lambda r: r["bound"][0].update({"produced_share": 1.5}),
        lambda r: r["bound"][0].pop("unknown_share"),
    ):
        broken = copy.deepcopy(record)
        mutate(broken["observability_record"])
        with pytest.raises(jsonschema.ValidationError):
            validate_record(broken)


def test_schema_accepts_null_shares_when_all_unknown() -> None:
    cells = build_cells(turns([ABSENT, ABSENT], sample_id="S1") +
                        turns([ABSENT], sample_id="S2"))
    record = build_record(
        corpora=[CORPUS], cells=cells, profiles=arm_profiles(cells),
        codebook_hash="sha256:SYNTHETIC",
    )
    validate_record(record)
    (bound,) = record["observability_record"]["bound"]
    assert bound["produced_share"] is None
    assert bound["unknown_share"] == 1.0


# --- describe() and Figure 1 ---------------------------------------------------------


def test_usage_caveats_count_each_evidence_value_and_unpaired_turns() -> None:
    tally = PairingTally(unpaired_turns=2, ambiguous_turns=1, paired_without_count=0,
                         unmatched_calls=3, errored_unmatched_calls=1)
    caveats = " | ".join(usage_caveats(_mixed_observations(), tally))
    assert "PRODUCED 4, NOT_PRODUCED 4, UNKNOWN 2" in caveats
    assert "2 turn(s) could not be paired" in caveats
    assert "3 model call(s) produced no assistant turn" in caveats


def test_figure_one_caption_states_produced_shares(tmp_path: Path) -> None:
    observations = _mixed_observations() * 3
    observations = [
        TurnObservation(o.model, o.task_class, o.step_index, o.state,
                        sample_id=f"{o.sample_id}_{i}",
                        provider_reasoning_tokens=o.provider_reasoning_tokens)
        for i, o in enumerate(observations)
    ]
    _, caption = figure_one(build_cells(observations), tmp_path / "fig1.png")
    assert "produced 0.400, not produced 0.400, unknown 0.200" in caption
    assert "Readable is not produced" in caption


def test_redaction_without_a_token_count_is_unknown_not_produced() -> None:
    """A publisher's redaction marker is no evidence that reasoning existed."""
    from channels.schema import DeliberationEvidence, ReasoningState, TurnObservation

    def obs(state: ReasoningState, tokens: int | None) -> TurnObservation:
        return TurnObservation(
            "SYNTHETIC-MODEL", "synthetic_task", 0, state,
            provider_reasoning_tokens=tokens,
        )

    assert obs(ReasoningState.REDACTED, None).deliberation_evidence is (
        DeliberationEvidence.UNKNOWN
    )
    assert obs(ReasoningState.REDACTED, 120).deliberation_evidence is (
        DeliberationEvidence.PRODUCED
    )
    assert obs(ReasoningState.RAW_PRESENT, None).deliberation_evidence is (
        DeliberationEvidence.PRODUCED
    )
