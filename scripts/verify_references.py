"""Check the paper's bibliography: arXiv ids resolve, titles and first authors match.

A paper arguing that unverified numbers make a result uninterpretable should not carry
unverified citations. Every entry with an arXiv id is fetched from the arXiv export API
and compared on two axes: title overlap (Jaccard over lowercased word sets) and first
author surname. A mismatch is reported and exits non-zero.

The bibliography lives inline in the manuscript as a `thebibliography` environment
rather than in a .bib file, so that is what is parsed.

    .venv/bin/python scripts/verify_references.py            # fetches from arXiv
    .venv/bin/python scripts/verify_references.py --offline  # structure only

`--offline` checks that every entry has a key, a parseable first author and either an
arXiv id or a DOI, without touching the network, so CI can run it unconditionally.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

PAPER = Path(".other-experiments/paper/coverage_not_faithfulness/main.tex")
ARXIV_API = "https://export.arxiv.org/api/query?id_list={ids}&max_results=100"
ATOM = {"a": "http://www.w3.org/2005/Atom"}
TITLE_JACCARD_FLOOR = 0.6

#: Entries whose cited author is a corporate or team name, where arXiv lists an
#: individual as first author. Citing the team is correct practice, not an error.
CORPORATE_AUTHORS = {"qwen2025"}


@dataclass(frozen=True)
class Reference:
    """One bibliography entry, as cited."""

    key: str
    first_author: str
    title: str
    arxiv_id: str | None
    doi: str | None


def _clean(text: str) -> str:
    """Strip LaTeX markup and collapse whitespace."""
    text = re.sub(r"\\[a-zA-Z]+\s*\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = text.replace("{", "").replace("}", "").replace("\\", "")
    return re.sub(r"\s+", " ", text).strip()


def parse_bibliography(path: Path) -> list[Reference]:
    """Parse the manuscript's thebibliography environment into Reference rows."""
    text = path.read_text()
    block = re.search(
        r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", text, re.S
    )
    if block is None:
        raise SystemExit(f"no thebibliography environment in {path}")

    references: list[Reference] = []
    for raw in re.split(r"\\bibitem\{", block.group(0))[1:]:
        key, _, body = raw.partition("}")
        body = _clean(body)
        arxiv = re.search(r"arXiv:\s*(\d{4}\.\d{4,5})", body)
        # A PMLR proceedings URL is as durable an identifier as a DOI, and is the
        # archival version of a paper that also exists as an OpenReview submission.
        doi = re.search(r"doi\.org/(\S+)|(proceedings\.mlr\.press/\S+)", body)
        # "Surname, I., Surname, I. (year). Title. ..." - the surname is up to the
        # first comma, and the title is the sentence after the year.
        surname = body.split(",", 1)[0].strip()
        after_year = re.split(r"\(\d{4}[a-z]?\)\.\s*", body, maxsplit=1)
        title = after_year[1].split(".")[0].strip() if len(after_year) > 1 else ""
        references.append(
            Reference(
                key=key.strip(),
                first_author=surname,
                title=title,
                arxiv_id=arxiv.group(1) if arxiv else None,
                doi=(doi.group(1) or doi.group(2)).rstrip(".") if doi else None,
            )
        )
    return references


def _jaccard(left: str, right: str) -> float:
    """Word-set overlap of two titles, lowercased and stripped of punctuation."""
    def words(text: str) -> set[str]:
        return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}

    first, second = words(left), words(right)
    if not first or not second:
        return 0.0
    return len(first & second) / len(first | second)


def fetch(ids: list[str]) -> dict[str, tuple[str, str]]:
    """Return {arxiv_id: (title, first author surname)} from the arXiv export API."""
    url = ARXIV_API.format(ids=",".join(ids))
    # Fixed https host, built from a constant; the ids are matched against
    # r"\d{4}\.\d{4,5}" before they reach here.
    with urllib.request.urlopen(url, timeout=60) as response:
        tree = ET.fromstring(response.read())
    found: dict[str, tuple[str, str]] = {}
    for entry in tree.findall("a:entry", ATOM):
        raw_id = (entry.findtext("a:id", default="", namespaces=ATOM) or "").rsplit(
            "/", 1
        )[-1]
        identifier = raw_id.split("v")[0]
        title = re.sub(
            r"\s+", " ", entry.findtext("a:title", default="", namespaces=ATOM) or ""
        ).strip()
        author = entry.find("a:author/a:name", ATOM)
        name = (author.text or "").strip() if author is not None else ""
        found[identifier] = (title, name.split()[-1] if name else "")
    return found


def check_offline(references: list[Reference]) -> list[str]:
    """Structural checks that need no network."""
    problems: list[str] = []
    seen: set[str] = set()
    for reference in references:
        if reference.key in seen:
            problems.append(f"{reference.key}: duplicate bibliography key")
        seen.add(reference.key)
        if not reference.first_author:
            problems.append(f"{reference.key}: no parseable first author")
        if not reference.arxiv_id and not reference.doi:
            problems.append(f"{reference.key}: neither an arXiv id nor a DOI")
        if reference.arxiv_id and not re.fullmatch(
            r"\d{4}\.\d{4,5}", reference.arxiv_id
        ):
            problems.append(f"{reference.key}: malformed arXiv id")
    return problems


def check_online(references: list[Reference]) -> list[str]:
    """Compare each arXiv entry's title and first author with the arXiv record."""
    with_ids = [r for r in references if r.arxiv_id]
    if not with_ids:
        return []
    remote = fetch([r.arxiv_id for r in with_ids if r.arxiv_id])
    problems: list[str] = []
    for reference in with_ids:
        assert reference.arxiv_id is not None
        if reference.arxiv_id not in remote:
            problems.append(
                f"{reference.key}: arXiv:{reference.arxiv_id} returned no entry"
            )
            continue
        title, surname = remote[reference.arxiv_id]
        overlap = _jaccard(reference.title, title)
        if overlap < TITLE_JACCARD_FLOOR:
            problems.append(
                f"{reference.key}: title overlap {overlap:.2f} below "
                f"{TITLE_JACCARD_FLOOR}\n    cited:  {reference.title}\n"
                f"    arXiv:  {title}"
            )
        if (
            reference.key not in CORPORATE_AUTHORS
            and surname
            and surname.lower() != reference.first_author.lower()
        ):
            problems.append(
                f"{reference.key}: first author {reference.first_author!r} "
                f"but arXiv says {surname!r}"
            )
    return problems


def main() -> int:
    """Check the bibliography; --offline skips the network."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline", action="store_true", help="structure only; no network"
    )
    parser.add_argument("--paper", type=Path, default=PAPER)
    args = parser.parse_args()

    if not args.paper.exists():
        print(f"manuscript not found at {args.paper}; nothing to check")
        return 0

    references = parse_bibliography(args.paper)
    with_ids = sum(1 for r in references if r.arxiv_id)
    print(f"{len(references)} bibliography entries, {with_ids} with an arXiv id")

    problems = check_offline(references)
    if not args.offline:
        try:
            problems.extend(check_online(references))
        except OSError as error:
            print(f"arXiv lookup failed ({error}); rerun with --offline to skip it")
            return 2

    if problems:
        print(f"\n{len(problems)} problem(s):")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print("every entry checks out" if not args.offline else "structure is sound")
    return 0


if __name__ == "__main__":
    sys.exit(main())
