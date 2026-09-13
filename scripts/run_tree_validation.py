"""Run TreeCoder on WikiTactics and persist its validation record.

Regenerates results/validation/tree_coder_1.0_wikitactics.json (build log step 9)
from data/wikitactics with the package's own loader and `validate`. Every code
in the codebook is scored, because the committed record scores every code:
those with no gold support report `no_support_in_control` with null metrics,
never a measured zero.

    uv run python scripts/run_tree_validation.py [--out DIR]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from channels.codebook import CODES, codebook_hash
from channels.loaders.positive_control import WikiTacticsLoader
from channels.tree import TreeCoder
from channels.validate import (
    VALIDATION_DIR,
    ValidationRecord,
    validate,
    write_validation,
)

CORPUS = Path("data/wikitactics/wikitactics.json")


def print_record(record: ValidationRecord) -> None:
    """Print counts and recalls only; no corpus text leaves the loader."""
    print(f"n scored {record.n_utterances}, skipped {record.n_skipped}")
    for code, score in record.scores.items():
        recall = f"{score.recall:.3f}" if score.recall is not None else "n/a"
        interval = (
            f"[{score.recall_ci95[0]:.3f}, {score.recall_ci95[1]:.3f}]"
            if score.recall_ci95
            else "n/a"
        )
        print(
            f"  {code:12s} support={score.support:5d} predicted={score.predicted:5d} "
            f"recall={recall} {interval} status={score.status}"
        )


def main(argv: list[str] | None = None) -> int:
    """Validate the tree coder on rung 1 and write the record."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=VALIDATION_DIR)
    args = parser.parse_args(argv)
    loader = WikiTacticsLoader(CORPUS)
    if not loader.available():
        print(f"wikitactics not present at {CORPUS}", file=sys.stderr)
        return 2
    record = validate(
        TreeCoder(), list(loader.load()), codebook_hash(), "wikitactics", CODES
    )
    print_record(record)
    print(f"wrote {write_validation(record, args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
