"""Read the Mythos 5 incident transcript into turn observations.

This is the only public incident transcript a frontier lab has released, and step 0 of
the build established that it *does* expose a reasoning channel — as inline
`<thinking>...</thinking>` tags inside the `content` string, not as a structured field.
That is worth stating precisely, because "the transcript contains reasoning" and "the
transcript exposes a reasoning field an evaluator could read programmatically" are
different claims, and only the first is true.

Deliberately minimal per spec §11.1: read, assign `step_index`, classify
`reasoning_state`, emit observations. Safety constraints from §13 are not optional here:
the corpus carries a canary GUID and a do-not-train notice, so nothing from it is sent
to any third-party service and every utterance is marked `do_not_train`.
"""

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from channels.errors import CorpusUnavailableError, SchemaDiscoveryError
from channels.loaders.base import discover_keys, file_hash, require_keys
from channels.schema import (
    Channel,
    CorpusDescription,
    Provenance,
    ReasoningState,
    TurnObservation,
    Utterance,
)

CORPUS = "mythos_transcript"
TASK_CLASS = "mythos_cyber_ctf"

# Anthropic's release names the model in its own title; the transcript rows do not
# carry a model field, so it is recorded here rather than inferred per row.
MODEL = "mythos-5"

# Reasoning is delimited in-band. A single regex is the whole parser, which is why
# `SchemaDiscoveryError` below checks the record keys rather than trusting this.
_THINKING = re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL)

# Anthropic redacted whole messages and individual words; both markers must survive.
_REDACTED_WHOLE = "[redacted]"
_REDACTED_PARTIAL_MARKER = "[redacted-"

REQUIRED_MESSAGE_KEYS = ("record", "index", "role", "type", "timestamp")


class MythosTranscriptLoader:
    """Loads `transcript.jsonl` from the Mythos 5 incident release."""

    name = CORPUS

    def __init__(self, path: Path) -> None:
        self.path = path

    def available(self) -> bool:
        """Whether the transcript file is present."""
        return self.path.is_file()

    def require_available(self) -> Path:
        """Return the transcript path, or raise naming the path that was checked."""
        if not self.available():
            raise CorpusUnavailableError(
                f"Mythos transcript not found at {self.path.resolve()}. "
                "Clone https://github.com/anthropics/mythos-5-incident-transcript."
            )
        return self.path

    def records(self) -> Iterator[dict[str, Any]]:
        """Yield every JSON record in the transcript, metadata row included."""
        path = self.require_available()
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)

    def messages(self) -> Iterator[dict[str, Any]]:
        """Yield message records only, after checking the schema is the expected one."""
        records = list(self.records())
        message_records = [r for r in records if r.get("record") == "message"]
        if not message_records:
            raise SchemaDiscoveryError(
                f"{CORPUS}: no rows with record='message'. "
                f"Keys observed: {sorted(discover_keys(records))}"
            )
        require_keys(discover_keys(message_records), REQUIRED_MESSAGE_KEYS, CORPUS)
        yield from message_records

    def observations(self) -> Iterator[TurnObservation]:
        """Yield one TurnObservation per assistant message in the transcript.

        Every assistant message counts, tool messages included. A tool-result message
        carries no `content` field at all, so its reasoning state is ABSENT — which is
        the honest reading: at that turn the agent's reasoning was not observable.
        """
        step_index = 0
        for record in self.messages():
            if record.get("role") != "Assistant":
                continue
            yield TurnObservation(
                model=MODEL,
                task_class=TASK_CLASS,
                step_index=step_index,
                state=classify_record(record),
                reasoning_effort=None,
                sample_id="mythos_5_incident_1",
            )
            step_index += 1

    def load(self, **kwargs: Any) -> Iterator[Utterance]:
        """Yield reasoning and tool-call utterances, with text withheld.

        `text` is None throughout. The reasoning content is do-not-train material and
        publishing it is barred by §13; withholding it still counts the utterance,
        which is the whole point of the uninspectable-is-not-dropped rule.
        """
        for position, record in enumerate(self.messages()):
            if record.get("role") != "Assistant":
                continue
            channel = (
                Channel.TOOL_CALL
                if record.get("type") == "ToolMessage"
                else Channel.REASONING
            )
            yield Utterance(
                uid=f"{CORPUS}:{record.get('index', position)}",
                corpus=CORPUS,
                channel=channel,
                provenance=Provenance.REDACTED_PARTIAL,
                text=None,
                actor=MODEL,
                thread_id="mythos_5_incident_1",
                timestamp=str(record.get("timestamp")),
                seq=position,
                model=MODEL,
                task_class=TASK_CLASS,
                reasoning_state=classify_record(record),
                source_ref="anthropics/mythos-5-incident-transcript, transcript.jsonl",
                corpus_meta={
                    "do_not_train": True,
                    "tool_name": record.get("tool_name"),
                },
            )

    def describe(self) -> CorpusDescription:
        """Summarise the transcript. n=1 trajectory, and the caveats say so."""
        observations = list(self.observations())
        return CorpusDescription(
            name=CORPUS,
            n_utterances=len(observations),
            n_actors=1,
            actor_concentration=1.0,
            date_range=self._date_range(),
            source_hash=file_hash(self.require_available()),
            licence="not stated; released by Anthropic for study",
            caveats=(
                "n=1 trajectory; one incident, one model, not a sample",
                "carries a canary GUID and a do-not-train notice",
                "Anthropic redacted messages 1-81, messages after 2145, some "
                "third-party-server messages, and individual words in place",
                "reasoning is in-band <thinking> markup, not a structured field",
            ),
        )

    def _date_range(self) -> tuple[str, str] | None:
        """First and last message timestamps, or None if the field is absent."""
        stamps = sorted(
            str(r["timestamp"]) for r in self.messages() if r.get("timestamp")
        )
        return (stamps[0], stamps[-1]) if stamps else None


def classify_record(record: dict[str, Any]) -> ReasoningState:
    """Classify one transcript record into the four-state scheme.

    A tool-result record has no `content` key, so there is nothing to read: ABSENT.
    A wholly redacted message is REDACTED. A message with a `<thinking>` block is
    RAW_PRESENT. Anything else is visible output with no reasoning: ABSENT.

    Note the asymmetry with `coverage.classify_reasoning`: there, REDACTED outranks
    RAW_PRESENT within a turn. Here a message can be redacted *or* carry thinking but
    not both, because Anthropic redacted whole messages rather than parts of them.
    """
    content = record.get("content")
    if content is None:
        return ReasoningState.ABSENT
    if content.strip() == _REDACTED_WHOLE:
        return ReasoningState.REDACTED
    if _THINKING.search(content):
        return ReasoningState.RAW_PRESENT
    return ReasoningState.ABSENT


def thinking_block_lengths(record: dict[str, Any]) -> list[int]:
    """Character lengths of the `<thinking>` blocks in one record.

    Lengths rather than text: a length is a count, and counts are publishable where
    the content is not.
    """
    content = record.get("content")
    if not isinstance(content, str):
        return []
    return [len(match.strip()) for match in _THINKING.findall(content)]


def has_partial_redaction(record: dict[str, Any]) -> bool:
    """Whether this record carries an in-place `[redacted-xyz]` marker."""
    content = record.get("content")
    return isinstance(content, str) and _REDACTED_PARTIAL_MARKER in content
