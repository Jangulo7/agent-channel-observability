"""Check every transcribed row against the source PDF it cites.

The integrity rule this enforces: a transcribed quotation is only as good as the
page it claims to come from, and a page number nobody checked is a number we
invented. Run it whenever `data/published_record/*.yaml` changes.

    uv run --extra verify python scripts/verify_citations.py

Reports, per row: whether the quoted text is findable in the cited PDF, and on
which physical page. Exits non-zero if a row cites a page the text is not on.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from channels.loaders.published_record import PublishedRecordLoader

#: Reports available locally. A row citing anything else cannot be checked here.
SOURCE_PDFS = {
    "HF investigation": Path("data/METR/hugging-face-incident-report-aug-2026.pdf"),
}

#: How many leading characters of a quotation to search for. Protocol strings are
#: broken across lines in the PDF, so whitespace is stripped from both sides.
PROBE_CHARS = 40


def _page_texts(pdf: Path) -> list[str]:
    """Return whitespace-stripped text for every page, 0-indexed."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf))
    texts = []
    for page in reader.pages:
        try:
            raw = page.extract_text() or ""
        except Exception:
            raw = ""
        texts.append(re.sub(r"\s+", "", raw))
    return texts


def _cited_page(source_ref: str) -> int | None:
    """Extract the page number a citation claims, if it states one."""
    match = re.search(r"\bp\.(\d+)", source_ref)
    return int(match.group(1)) if match else None


def main() -> int:
    """Verify each row; return 1 if any checkable row fails."""
    pdf = SOURCE_PDFS["HF investigation"]
    if not pdf.is_file():
        print(f"source PDF absent: {pdf}", file=sys.stderr)
        return 2
    pages = _page_texts(pdf)

    failures = 0
    for utt in PublishedRecordLoader().load():
        ref = utt.source_ref or ""
        if "HF investigation" not in ref:
            print(f"SKIP     {utt.uid}: cites a source not available locally")
            continue
        claimed = _cited_page(ref)
        probe = re.sub(r"\s+", "", (utt.text or ""))[:PROBE_CHARS]
        found = [i + 1 for i, text in enumerate(pages) if probe and probe in text]
        if claimed in found:
            print(f"OK       {utt.uid}: found on p.{claimed}")
        else:
            failures += 1
            where = found or "no page"
            print(f"MISMATCH {utt.uid}: cites p.{claimed}, text found on {where}")
    print(f"\n{failures} mismatch(es)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
