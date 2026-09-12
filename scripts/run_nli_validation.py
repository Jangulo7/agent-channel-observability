"""Run NliDetector on WikiTactics and persist its validation record.

Kept as a script rather than a CI step: it needs the cached checkpoint and takes
minutes on CPU. Its output is committed under results/validation/ so the number
in the paper is reproducible without re-running it.
"""

from __future__ import annotations

import sys
from pathlib import Path

from channels.codebook import codebook_hash
from channels.detect import NliDetector, OfflineCheckpointError
from channels.loaders.positive_control import WikiTacticsLoader
from channels.validate import validate_from_result, write_validation

CORPUS = Path("data/wikitactics/wikitactics.json")


def main() -> int:
    """Validate the NLI detector on rung 1 and write the record."""
    loader = WikiTacticsLoader(CORPUS)
    if not loader.available():
        print(f"wikitactics not present at {CORPUS}", file=sys.stderr)
        return 2
    utterances = list(loader.load())
    try:
        result = NliDetector().detect(utterances)
    except OfflineCheckpointError as error:
        print(f"checkpoint unavailable: {error}", file=sys.stderr)
        return 3

    record = validate_from_result(
        result,
        utterances,
        codebook_hash(),
        "wikitactics",
        codes=["OBJ", "REF", "SHARE"],
    )
    path = write_validation(record)
    print(f"n scored {record.n_utterances}, skipped {record.n_skipped}")
    for code, score in record.scores.items():
        recall = f"{score.recall:.3f}" if score.recall is not None else "n/a"
        interval = (
            f"[{score.recall_ci95[0]:.3f}, {score.recall_ci95[1]:.3f}]"
            if score.recall_ci95
            else "n/a"
        )
        print(f"  {code:6s} support={score.support:5d} recall={recall} {interval}")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
