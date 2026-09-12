"""The published incident record, transcribed into the normalised schema.

These rows are hand-transcribed from published incident reporting. They are the
*only* verbatim or redacted-partial inter-agent strings located in the public
record for these incidents, which is itself the finding: see spec §15 C.

**No rate may be computed from this corpus.** n is single digits and the rows
were selected by investigators for illustration, not sampled. `refuse_rate`
raises to make that structural rather than advisory.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from channels.errors import ChannelsError, SchemaDiscoveryError
from channels.loaders.base import actor_concentration
from channels.schema import Channel, CorpusDescription, Provenance, Utterance

PUBLISHED_RECORD_DIR = Path(__file__).resolve().parents[3] / "data" / "published_record"

#: Every row must carry these. `source_ref` is required because a transcribed row
#: without a citation is indistinguishable from an invented one.
REQUIRED_FIELDS = ("local_id", "channel", "provenance", "text", "source_ref")

#: The convention the incident's agents used to frame protocol strings. Asserted
#: across independently attributed sources by `test_zz_prefix_consistent_...`.
ZZ_PREFIX = "zz"


class RateFromTypologyError(ChannelsError):
    """Raised on any attempt to compute a rate from the qualitative typology."""


@dataclass
class PublishedRecordLoader:
    """Loads the hand-transcribed published-record YAML files."""

    root: Path = PUBLISHED_RECORD_DIR
    name: str = "published_record"

    def available(self) -> bool:
        """Whether any transcription file exists."""
        return bool(self.yaml_paths())

    def yaml_paths(self) -> list[Path]:
        """Every transcription file, sorted for reproducible ordering."""
        return sorted(self.root.glob("*.yaml")) if self.root.is_dir() else []

    def _rows(self) -> Iterator[tuple[Path, dict[str, Any]]]:
        """Parse every row, validating it against the required fields."""
        paths = self.yaml_paths()
        if not paths:
            raise SchemaDiscoveryError(
                f"published_record: no YAML under {self.root}. "
                "Missing transcription is a result, not an empty corpus."
            )
        for path in paths:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(loaded, list):
                raise SchemaDiscoveryError(
                    f"published_record: {path.name} did not parse to a list"
                )
            for row in loaded:
                _validate_row(row, path)
                yield path, row

    def load(self, **kwargs: Any) -> Iterator[Utterance]:
        """Yield one Utterance per transcribed row."""
        for path, row in self._rows():
            yield Utterance(
                uid=f"published_record:{row['local_id']}",
                corpus="published_record",
                channel=Channel(row["channel"]),
                provenance=Provenance(row["provenance"]),
                text=row["text"],
                actor=row.get("actor"),
                addressee=row.get("addressee"),
                source_ref=row["source_ref"],
                corpus_meta={**(row.get("corpus_meta") or {}), "file": path.name},
            )

    def refuse_rate(self) -> float:
        """Always raises. No rate may be computed from a hypothesis-generating set.

        The rows were chosen by investigators to illustrate a point, so their
        relative frequencies are the investigators' editorial choices and not the
        incident's. A method that returns a number here would be inventing one.
        """
        raise RateFromTypologyError(
            "published_record is qualitative and hypothesis-generating "
            f"(n={sum(1 for _ in self._rows())}); no rate may be computed from it"
        )

    def describe(self) -> CorpusDescription:
        """Counts and provenance. Every row is a transcription, none is sampled."""
        utterances = list(self.load())
        unverified = [
            utt.uid for utt in utterances if _needs_verification(utt.source_ref)
        ]
        return CorpusDescription(
            name=self.name,
            n_utterances=len(utterances),
            n_actors=len({utt.actor for utt in utterances if utt.actor}),
            actor_concentration=actor_concentration([u.actor for u in utterances]),
            date_range=None,
            source_hash=_combined_hash(self.yaml_paths()),
            licence="quotations from published reports; cited, not redistributed",
            caveats=(
                "Hypothesis-generating, not a sample. NO rate may be computed; "
                "refuse_rate() raises.",
                f"{len(unverified)} of {len(utterances)} rows carry an unverified "
                "page reference or a TODO(johanna) citation and must be checked "
                "against the source PDF before publication.",
                "These are every verbatim or redacted-partial inter-agent string "
                "located in the public record for these incidents. The scarcity "
                "is itself the evidence-sufficiency finding.",
            ),
        )


def _needs_verification(source_ref: str | None) -> bool:
    """Whether a citation still carries a TODO or an unverified page number."""
    reference = source_ref or ""
    return "TODO(johanna)" in reference or "VERIFY" in reference


def _validate_row(row: Any, path: Path) -> None:
    """Raise naming the offending row and what it was missing."""
    if not isinstance(row, dict):
        raise SchemaDiscoveryError(
            f"published_record: {path.name} has a non-mapping row"
        )
    missing = [field for field in REQUIRED_FIELDS if not row.get(field)]
    if missing:
        raise SchemaDiscoveryError(
            f"published_record: {path.name} row {row.get('local_id', '<no id>')!r} "
            f"is missing {missing}; keys present: {sorted(row)}"
        )
    try:
        Provenance(row["provenance"])
    except ValueError as error:
        raise SchemaDiscoveryError(
            f"published_record: {path.name} row {row['local_id']!r} has provenance "
            f"{row['provenance']!r}, which is not in the Provenance enum: "
            f"{[p.value for p in Provenance]}"
        ) from error
    try:
        Channel(row["channel"])
    except ValueError as error:
        raise SchemaDiscoveryError(
            f"published_record: {path.name} row {row['local_id']!r} has channel "
            f"{row['channel']!r}, which is not in the Channel enum: "
            f"{[c.value for c in Channel]}"
        ) from error


def _combined_hash(paths: Sequence[Path]) -> str:
    """A single hash over every transcription file."""
    import hashlib

    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"
