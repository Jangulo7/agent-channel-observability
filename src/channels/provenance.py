"""Which utterances may enter a confirmatory endpoint, and which may not.

The rule is that any text a human or a model rewrote is evidence about the rewriter.
A paraphrase of an agent message tells you what an investigator understood, which is
a different quantity from what the agent said, and mixing the two produces a rate
whose denominator nobody can state.
"""

from collections.abc import Iterable

from channels.errors import ProvenanceError
from channels.schema import Channel, Provenance, Utterance

# Only these two survive contact with a human writer well enough to count.
# REDACTED_PARTIAL keeps its markers (§13.4) and so remains auditable.
PRIMARY_ELIGIBLE: frozenset[Provenance] = frozenset(
    {Provenance.VERBATIM, Provenance.REDACTED_PARTIAL}
)

# Channels that carry human or investigator authorship. They never enter a rate
# whose denominator is described as inter-agent.
NON_AGENT_CHANNELS: frozenset[Channel] = frozenset(
    {Channel.HUMAN_MESSAGE, Channel.SYSTEM_MESSAGE}
)

#: Channels that carry a message FROM one agent TO another. This, not "everything
#: an agent did", is the denominator for an inter-agent message rate. An artefact
#: edit is agent-authored and peer-observable but is addressed to no one, so
#: counting it here would inflate the denominator with acts that could not have
#: carried an objection in words.
MESSAGE_CHANNELS: frozenset[Channel] = frozenset({Channel.INTER_AGENT_MESSAGE})

#: Channels that express a stance through action rather than text. Scored by a
#: different instrument (revert detection), never by the verbal codebook.
ACTION_CHANNELS: frozenset[Channel] = frozenset({Channel.ARTEFACT_EDIT})


def for_primary(
    utts: Iterable[Utterance],
) -> tuple[list[Utterance], dict[str, list[str]]]:
    """Split utterances into those eligible for a confirmatory endpoint and the rest.

    Returns:
        `(kept, dropped_by_reason)` where the second maps a reason string to the uids
        dropped for it. The reasons are returned rather than logged because the count
        of exclusions is itself a reportable number.
    """
    kept: list[Utterance] = []
    dropped: dict[str, list[str]] = {}
    for utt in utts:
        reason = _ineligibility_reason(utt)
        if reason is None:
            kept.append(utt)
        else:
            dropped.setdefault(reason, []).append(utt.uid)
    return kept, dropped


def assert_primary_eligible(utts: Iterable[Utterance]) -> None:
    """Raise ProvenanceError listing offenders if any utterance is ineligible.

    Every confirmatory endpoint calls this first. It raises rather than filtering so
    that an endpoint cannot silently shrink its own denominator.
    """
    offenders = [
        f"{utt.uid} ({_ineligibility_reason(utt)})"
        for utt in utts
        if _ineligibility_reason(utt) is not None
    ]
    if offenders:
        shown = ", ".join(offenders[:10])
        more = "" if len(offenders) <= 10 else f", and {len(offenders) - 10} more"
        raise ProvenanceError(
            f"{len(offenders)} utterance(s) are not eligible for a confirmatory "
            f"endpoint: {shown}{more}. Expected provenance in "
            f"{sorted(p.value for p in PRIMARY_ELIGIBLE)} and an agent channel."
        )


def is_inter_agent(utt: Utterance) -> bool:
    """Whether this utterance may count toward an inter-agent rate."""
    return utt.channel not in NON_AGENT_CHANNELS


def is_inter_agent_message(utt: Utterance) -> bool:
    """Whether this utterance is a MESSAGE from one agent to another.

    Stricter than `is_inter_agent`: an artefact edit passes that test and fails
    this one. The codebook's verbal codes are defined over messages, so this is
    the predicate that gates them.
    """
    return utt.channel in MESSAGE_CHANNELS


def _ineligibility_reason(utt: Utterance) -> str | None:
    """Return why this utterance is barred from a confirmatory endpoint, or None."""
    if utt.provenance not in PRIMARY_ELIGIBLE:
        return f"provenance={utt.provenance.value}"
    if utt.channel in NON_AGENT_CHANNELS:
        return f"channel={utt.channel.value}"
    return None
