"""collusion.wiki — OpenAI agents editing German wikis, as a frozen export.

Source: https://collusion.wiki/explorer/download. **No licence is stated.** Data
is already redacted at source (second half of every IP, all usernames). This
loader publishes counts and never utterance text, and `describe()` says so.

Never re-crawled: the export is hash-pinned and `manifest.json` carries the
source's own provenance, including the attribution filter the authors applied.
Attribution here is *inferred by the source authors*, not observed, and every
rate computed from it inherits that.
"""

from __future__ import annotations

import gzip
import json
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from channels.errors import SchemaDiscoveryError
from channels.loaders.base import actor_concentration, file_hash
from channels.schema import Channel, CorpusDescription, Provenance, Utterance

#: Row counts published by the source. A mismatch means the export moved under us.
EXPECTED_ROWS = {"revisions": 14_591, "pages": 4_579, "labels": 3_103}

REQUIRED_REVISION_KEYS = ("rev_id", "page_key", "label", "wiki", "time")


@dataclass
class CollusionWikiLoader:
    """Loads the frozen collusion.wiki export into normalised utterances."""

    root: Path
    name: str = "collusion_wiki"

    def available(self) -> bool:
        """Whether the three required export files are present."""
        return all(
            self._path(n) is not None for n in ("revisions", "pages", "labels")
        )

    def _path(self, stem: str) -> Path | None:
        """Locate one export file under the root, whatever layout it arrived in.

        The published export ships as `<stem>.jsonl.gz` at the top level. A copy
        that has been through a Windows unzip arrives decompressed, and often
        nested one level deep in a directory that shares the archive's name
        (`revisions.jsonl/revisions.jsonl`). Searching for the file rather than
        assuming a layout stops a corpus that IS present being reported missing —
        which would be a false negative of exactly the kind this package refuses
        to let pass silently.
        """
        for candidate in (
            self.root / f"{stem}.jsonl.gz",
            self.root / f"{stem}.jsonl",
            self.root / f"{stem}.jsonl" / f"{stem}.jsonl",
            self.root / f"{stem}.jsonl.gz" / f"{stem}.jsonl.gz",
        ):
            if candidate.is_file():
                return candidate
        matches = sorted(
            path
            for pattern in (f"{stem}.jsonl", f"{stem}.jsonl.gz")
            for path in self.root.rglob(pattern)
            if path.is_file()
        )
        return matches[0] if matches else None

    def require_available(self) -> None:
        """Raise naming every path checked, because missing data is a result."""
        if self.available():
            return
        checked = [
            f"{self.root / n}.jsonl[.gz]" for n in ("revisions", "pages", "labels")
        ]
        raise SchemaDiscoveryError(
            f"collusion_wiki: export not found. Checked: {checked}. "
            "Download it with the commands in docs/DATA_PROVENANCE.md"
        )

    def _rows(self, stem: str) -> list[dict[str, Any]]:
        """Read one gzipped JSONL file, checking its count against the source's."""
        path = self._path(stem)
        if path is None:
            raise SchemaDiscoveryError(
                f"collusion_wiki: no {stem}.jsonl[.gz] anywhere under {self.root}"
            )
        opener = (
            gzip.open if path.suffix == ".gz" else open
        )
        rows: list[dict[str, Any]] = []
        with opener(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    rows.append(json.loads(stripped))
        expected = EXPECTED_ROWS.get(stem)
        if expected is not None and len(rows) != expected:
            # A warning, not an error: the source may publish a newer export. But it
            # must be visible, because every count downstream shifts with it.
            rows[0].setdefault("_row_count_mismatch", f"{len(rows)} != {expected}")
        return rows

    def _handles(self) -> tuple[set[str], set[str]]:
        """Return (every known handle, the handles the source marked human).

        Spec §13.6: a corpus mixing human and agent authors separates them on the
        sender field and fails toward HUMAN_MESSAGE when undetermined. A revision
        whose handle is absent from labels.jsonl is therefore treated as human.
        """
        known: set[str] = set()
        human: set[str] = set()
        for row in self._rows("labels"):
            label = row.get("label")
            if label is None:
                continue
            known.add(label)
            if row.get("is_human_handle"):
                human.add(label)
        return known, human

    def load(self, **kwargs: Any) -> Iterator[Utterance]:
        """Yield one Utterance per revision. Body text is withheld.

        `text=None` is deliberate and is not a missing value: the corpus has no
        licence, so the text is not publishable, and the four-state accounting
        this package performs does not need it. The utterance still counts.
        """
        self.require_available()
        known, human = self._handles()
        for row in self._rows("revisions"):
            absent = [k for k in REQUIRED_REVISION_KEYS if k not in row]
            if absent:
                raise SchemaDiscoveryError(
                    f"collusion_wiki: revision missing {absent}; "
                    f"keys observed: {sorted(row)}"
                )
            label = row.get("label") or None
            is_human = label is None or label in human or label not in known
            yield Utterance(
                uid=f"collusion_wiki:{row['rev_id']}",
                corpus="collusion_wiki",
                # NEEDS REVIEW: a wiki revision is an artefact edit, not a message.
                # The honest channel would be a new ARTEFACT_EDIT value, but adding
                # one changes the Utterance schema, which spec §15.4 and the build's
                # RED boundary both forbid without asking. INTER_AGENT_MESSAGE is
                # used because a shared page IS the channel these agents coordinate
                # through. See BUILD_LOG.md, QUESTIONS FOR JOHANNA.
                channel=(
                    Channel.HUMAN_MESSAGE
                    if is_human
                    else Channel.INTER_AGENT_MESSAGE
                ),
                provenance=Provenance.REDACTED_PARTIAL,
                text=None,
                actor=label,
                thread_id=str(row.get("page_key")),
                timestamp=row.get("time"),
                seq=row.get("seq"),
                source_ref="collusion.wiki frozen export",
                corpus_meta={
                    "wiki": row.get("wiki"),
                    "page_id": row.get("page_id"),
                    "body_len": row.get("body_len"),
                    "attribution": "inferred by source authors; see manifest.json",
                },
            )

    def actors_per_page(self) -> Counter[int]:
        """Distribution of distinct actors per page.

        This decides whether RQ3 is feasible at all: a page edited by one actor
        cannot contain peer disagreement by construction, so single-actor pages
        are not a small denominator, they are no denominator.

        Human editors are excluded from the count. RQ3 asks whether one AGENT
        objects to another, so a page edited by one agent and one human offers no
        opportunity for peer disagreement either, and counting the human would
        inflate the feasible denominator.
        """
        by_page: defaultdict[str, set[str]] = defaultdict(set)
        for utt in self.load():
            if utt.channel is Channel.HUMAN_MESSAGE:
                continue
            if utt.actor and utt.thread_id:
                by_page[utt.thread_id].add(utt.actor)
        return Counter(len(actors) for actors in by_page.values())

    def describe(self) -> CorpusDescription:
        """Counts, concentration, licence and the hazards, before any rate is read."""
        utterances = list(self.load())
        actors = [utt.actor for utt in utterances]
        wikis = Counter(str(utt.corpus_meta.get("wiki")) for utt in utterances)
        distribution = self.actors_per_page()
        n_pages = sum(distribution.values())
        multi = sum(count for size, count in distribution.items() if size >= 2)
        top_wiki, top_wiki_n = wikis.most_common(1)[0]
        n_human = sum(1 for u in utterances if u.channel is Channel.HUMAN_MESSAGE)
        return CorpusDescription(
            name=self.name,
            n_utterances=len(utterances),
            n_actors=len({a for a in actors if a}),
            actor_concentration=actor_concentration(actors),
            date_range=None,
            source_hash=_hash_or_raise(self._path("revisions")),
            licence="unspecified — research use, cite source",
            caveats=(
                "No licence stated. Counts published; revision text withheld.",
                "Attribution is inferred by the source authors' filter, recorded "
                "in manifest.json, not observed.",
                "Frozen hash-pinned export; never re-crawled at analysis time.",
                f"Clustering unit is the wiki, not the actor: {top_wiki_n} of "
                f"{len(utterances)} revisions "
                f"({top_wiki_n / len(utterances):.1%}) come from the single wiki "
                f"'{top_wiki}', while the most active individual actor holds only "
                f"{actor_concentration(actors) or 0:.1%}.",
                f"{n_pages - multi} of {n_pages} pages "
                f"({(n_pages - multi) / n_pages:.1%}) have exactly one distinct "
                "actor and cannot contain peer disagreement by construction.",
                f"{n_human} revisions fail toward HUMAN_MESSAGE (human handle or "
                "handle absent from labels.jsonl) and are excluded from any "
                "inter-agent rate.",
            ),
        )


def _hash_or_raise(path: Path | None) -> str:
    """Hash the revisions export, or raise rather than report an empty hash."""
    if path is None:
        raise SchemaDiscoveryError("collusion_wiki: revisions export not found")
    return file_hash(path)
