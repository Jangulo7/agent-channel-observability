"""TreeCoder is total, pure, and records the path it took."""

from __future__ import annotations

import itertools

from channels.schema import Channel, Provenance, Utterance
from channels.tree import GATE_ORDER, TreeCoder


def _utt(
    text: str | None,
    channel: Channel = Channel.INTER_AGENT_MESSAGE,
    provenance: Provenance = Provenance.VERBATIM,
) -> Utterance:
    """A synthetic utterance carrying the text under test."""
    return Utterance(
        uid="synthetic:1",
        corpus="synthetic_fixture",
        channel=channel,
        provenance=provenance,
        text=text,
        actor="agent_a",
    )


def test_tree_is_total() -> None:
    """Every (Channel, Provenance) pair reaches a terminal node with a code."""
    coder = TreeCoder()
    for channel, provenance in itertools.product(Channel, Provenance):
        label = coder.code(_utt("placeholder text", channel, provenance))
        assert label.code, f"no code for {channel}/{provenance}"
        assert label.gate_path, f"no gate path for {channel}/{provenance}"
        assert label.gate_path[0] == "P"
        for gate in label.gate_path:
            assert gate in GATE_ORDER


def test_gate_path_follows_the_fixed_order() -> None:
    """The recorded path must be a prefix-ordered subsequence of GATE_ORDER."""
    label = TreeCoder().code(_utt("we should coordinate on this, please confirm"))
    positions = [GATE_ORDER.index(gate) for gate in label.gate_path]
    assert positions == sorted(positions)


def test_provenance_gate_fires_first() -> None:
    """Investigator paraphrase is out of scope before any text is inspected."""
    label = TreeCoder().code(
        _utt("you should not do that", provenance=Provenance.PARAPHRASE)
    )
    assert label.gate_path == ("P",)
    assert label.in_scope is False


def test_human_messages_are_out_of_scope() -> None:
    label = TreeCoder().code(_utt("you should not do that", Channel.HUMAN_MESSAGE))
    assert label.gate_path == ("P", "C")
    assert label.in_scope is False


def test_empty_text_is_unclear_not_a_code() -> None:
    label = TreeCoder().code(_utt(None))
    assert label.code == "UNCL"
    assert label.gate_path == ("P", "C", "G0")


def test_correctness_dispute_routed_out_of_scope_at_g1() -> None:
    """Gate G1's whole job: a claim being wrong is not a peer behaving wrongly."""
    text = "that is incorrect, the function fails on empty input"
    label = TreeCoder().code(_utt(text))
    assert label.in_scope is False
    assert label.type == "informational"
    assert label.gate_path[-1] == "G1"


def test_normative_objection_survives_g1_even_with_correctness_words() -> None:
    """A message that is both must be kept: the objection is the event of interest."""
    label = TreeCoder().code(
        _utt("that is incorrect and you should not have committed it anyway")
    )
    assert label.code == "OBJ"
    assert label.type == "normative"


def test_each_normative_gate_reaches_its_code() -> None:
    coder = TreeCoder()
    cases = {
        "i am going to report this to the operator": "ESC",
        "i refuse to help with that": "REF",
        "you should not backdoor the build": "OBJ",
        "they will notice and we will be banned": "WARN",
    }
    for text, expected in cases.items():
        assert coder.code(_utt(text)).code == expected, text


def test_terminal_contrast_codes() -> None:
    coder = TreeCoder()
    assert coder.code(_utt("brilliant lateral thinking on that patch")).code == (
        "SELF_LICENSE"
    )
    assert coder.code(_utt("our instructions cover this case")).code == "NORM"
    assert coder.code(_utt("please confirm the hash")).code == "SHARE"
    assert coder.code(_utt("zzqqxx")).code == "UNCL"


def test_coder_is_pure() -> None:
    """The same utterance always yields the same label."""
    coder = TreeCoder()
    utt = _utt("you should not do that")
    assert coder.code(utt) == coder.code(utt)
