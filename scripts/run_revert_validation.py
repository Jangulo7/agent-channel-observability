"""Run RevertDetector on collusion.wiki and persist its validation record.

Regenerates results/validation/revert_detector_1.0_collusion_wiki.json (build log,
"schema decisions") from data/german-collusion-wiki with the package's own loader
and `validate_from_result`. No corpus here carries human revert labels, so both
codes report support 0 and `no_support_in_control`: the record documents how
many reverts were PREDICTED over how many agent edits, and that recall is not
measurable on any control this project holds. Messages are skipped, not scored.

    uv run python scripts/run_revert_validation.py [--out DIR]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from channels.codebook import codebook_hash
from channels.detect import RevertDetector
from channels.loaders.collusion_wiki import CollusionWikiLoader
from channels.validate import VALIDATION_DIR, validate_from_result, write_validation

CORPUS = Path("data/german-collusion-wiki")


def main(argv: list[str] | None = None) -> int:
    """Validate the revert detector and write the record."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=VALIDATION_DIR)
    args = parser.parse_args(argv)
    loader = CollusionWikiLoader(CORPUS)
    if not loader.available():
        print(f"collusion.wiki not present at {CORPUS}", file=sys.stderr)
        return 2
    utterances = list(loader.load())
    detector = RevertDetector()
    record = validate_from_result(
        detector.detect(utterances),
        utterances,
        codebook_hash(),
        "collusion_wiki",
        codes=list(detector.label_space),
    )
    print(f"n scored {record.n_utterances}, skipped {record.n_skipped}")
    for code, score in record.scores.items():
        print(
            f"  {code:6s} support={score.support} predicted={score.predicted} "
            f"recall={score.recall} status={score.status}"
        )
    print(f"wrote {write_validation(record, args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
