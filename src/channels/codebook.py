"""The coding instrument: eight codes, loaded from YAML and hashed.

The hash is what makes pre-registration mean anything. `gates.codebook_drift` compares
it against the hash recorded in `docs/PREREGISTRATION.md`, so editing the codebook after
registration fails the build rather than silently changing what was measured.
"""

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from channels.errors import SchemaDiscoveryError

CODEBOOK_PATH = Path(__file__).resolve().parents[2] / "data" / "codebook" / "v1.yaml"

# SHARE establishes the denominator; the next five are the numerator; UNCL is the
# residual. See `denominator_codes` and `numerator_codes` below.
CODES: tuple[str, ...] = (
    "OBJ", "REF", "ESC", "WARN", "NORM", "SELF_LICENSE", "SHARE", "UNCL", "REVERT",
)

#: Codes scored from TEXT by the verbal instruments (TreeCoder, NliDetector).
VERBAL_CODES: tuple[str, ...] = (
    "OBJ", "REF", "ESC", "WARN", "NORM", "SELF_LICENSE", "SHARE", "UNCL",
)

#: Codes scored from ACTION by a structural detector. Never assigned from text,
#: and never mixed into a verbal detector's recall.
ACTION_CODES: tuple[str, ...] = ("REVERT",)

REQUIRED_FIELDS: tuple[str, ...] = (
    "definition", "inclusion", "exclusion", "positive_examples", "negative_examples",
)


@dataclass(frozen=True)
class Code:
    """One code, with the rules that decide whether an utterance belongs to it."""

    name: str
    definition: str
    inclusion: str
    exclusion: str
    positive_examples: tuple[Mapping[str, Any], ...]
    negative_examples: tuple[Mapping[str, Any], ...]


def load_codebook(path: Path = CODEBOOK_PATH) -> dict[str, Code]:
    """Load and validate the codebook, raising if a code or field is absent."""
    raw = _raw_codebook(path)
    codes = raw.get("codes", {})
    missing = [name for name in CODES if name not in codes]
    if missing:
        raise SchemaDiscoveryError(
            f"codebook {path}: missing code(s) {missing}. "
            f"Codes present: {sorted(codes)}"
        )
    loaded: dict[str, Code] = {}
    for name in CODES:
        entry = codes[name]
        absent = [field for field in REQUIRED_FIELDS if field not in entry]
        if absent:
            raise SchemaDiscoveryError(
                f"codebook {path}: code {name} is missing {absent}. "
                f"Fields present: {sorted(entry)}"
            )
        loaded[name] = Code(
            name=name,
            definition=entry["definition"],
            inclusion=entry["inclusion"],
            exclusion=entry["exclusion"],
            positive_examples=tuple(entry["positive_examples"] or ()),
            negative_examples=tuple(entry["negative_examples"] or ()),
        )
    return loaded


def codebook_hash(path: Path = CODEBOOK_PATH) -> str:
    """SHA-256 over the canonicalised YAML, so formatting changes do not move the hash.

    Canonical form is the parsed structure re-dumped with sorted keys, which means
    reordering entries or reflowing a block comment leaves the hash alone while any
    change to a definition, rule or example moves it.
    """
    canonical = yaml.safe_dump(_raw_codebook(path), sort_keys=True, allow_unicode=True)
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def codebook_version(path: Path = CODEBOOK_PATH) -> int | None:
    """Return the codebook's own integer `version` field, or None when it has none.

    None rather than a default: the file is named v1.yaml but has carried later
    versions, so neither the filename nor a constant can stand in for the field.
    """
    version = _raw_codebook(path).get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        return None
    return version


def denominator_codes() -> tuple[str, ...]:
    """Codes that establish the denominator. SHARE alone: coordination had to occur."""
    return ("SHARE",)


def numerator_codes() -> tuple[str, ...]:
    """Codes that count toward the objection numerator."""
    return ("OBJ", "REF", "ESC", "WARN")


def example_gaps(path: Path = CODEBOOK_PATH) -> dict[str, list[str]]:
    """Report codes whose examples are still TODO, so the gaps are visible not hidden.

    A code with fewer than two real positive examples cannot support a recall claim,
    and the codebook says so out loud rather than shipping an invented example.
    """
    gaps: dict[str, list[str]] = {}
    for name, code in load_codebook(path).items():
        problems = []
        for label, examples in (
            ("positive", code.positive_examples),
            ("negative", code.negative_examples),
        ):
            real = [e for e in examples if not _is_todo(e)]
            if len(real) < 2:
                problems.append(
                    f"{len(real)} real {label}, {len(examples) - len(real)} TODO"
                )
        if problems:
            gaps[name] = problems
    return gaps


def _is_todo(example: Mapping[str, Any]) -> bool:
    """Whether an example is a placeholder awaiting a real, sourced instance."""
    text = str(example.get("text", ""))
    return text.startswith("TODO(") or not example.get("source_ref")


def _raw_codebook(path: Path) -> dict[str, Any]:
    """Parse the codebook YAML, raising if the file is absent or not a mapping."""
    if not path.is_file():
        raise FileNotFoundError(f"codebook not found at {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise SchemaDiscoveryError(f"codebook {path} did not parse to a mapping")
    return loaded


def all_examples(path: Path = CODEBOOK_PATH) -> Sequence[Mapping[str, Any]]:
    """Every example across every code, used by the validation harness."""
    collected: list[Mapping[str, Any]] = []
    for code in load_codebook(path).values():
        collected.extend(code.positive_examples)
        collected.extend(code.negative_examples)
    return collected
