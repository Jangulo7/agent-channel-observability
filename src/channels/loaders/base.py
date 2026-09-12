"""The loader protocol, plus the schema-discovery helper every loader uses.

Two of the target corpora have undocumented schemas. Rather than hard-code a guess,
loaders sample the first records, report the key set they actually found, and raise
`SchemaDiscoveryError` naming those keys when a required field is missing. A loader
that silently produced fewer utterances because a field moved would corrupt a
denominator without anyone noticing.
"""

import hashlib
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from channels.errors import SchemaDiscoveryError
from channels.schema import CorpusDescription, Utterance

# How many records to read before deciding what the schema is. 50 is the spec's
# number; it is large enough that an optional field present in a fifth of records
# shows up, and small enough to run on a streamed file.
DISCOVERY_SAMPLE = 50


@runtime_checkable
class Loader(Protocol):
    """Anything that turns a corpus on disk into normalised utterances."""

    name: str

    def available(self) -> bool: ...

    def load(self, **kwargs: Any) -> Iterator[Utterance]: ...

    def describe(self) -> CorpusDescription: ...


def discover_keys(records: Iterable[Mapping[str, Any]]) -> set[str]:
    """Return the union of keys seen across the first DISCOVERY_SAMPLE records."""
    keys: set[str] = set()
    for index, record in enumerate(records):
        if index >= DISCOVERY_SAMPLE:
            break
        keys.update(record.keys())
    return keys


def require_keys(
    observed: set[str], required: Sequence[str], corpus: str
) -> None:
    """Raise SchemaDiscoveryError if a required key is absent, listing what was seen."""
    missing = [key for key in required if key not in observed]
    if missing:
        raise SchemaDiscoveryError(
            f"{corpus}: required field(s) {missing} not found. "
            f"Keys actually observed in the first {DISCOVERY_SAMPLE} records: "
            f"{sorted(observed)}"
        )


def file_hash(path: Path) -> str:
    """SHA-256 of a file, streamed, prefixed so the algorithm travels with the value."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def actor_concentration(actors: Sequence[str | None]) -> float | None:
    """Share of observations belonging to the single most active actor.

    Returned so that `cluster.py`'s necessity is visible in the corpus description
    rather than discovered later in a footnote. None when no actor is recorded.
    """
    named = [actor for actor in actors if actor is not None]
    if not named:
        return None
    counts: dict[str, int] = {}
    for actor in named:
        counts[actor] = counts.get(actor, 0) + 1
    return max(counts.values()) / len(named)
