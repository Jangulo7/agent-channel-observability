"""`channels` — the command line that produces the record, the figures and the gates."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from channels.emission import binned_profile, build_cells
from channels.errors import ChannelsError
from channels.figures import figure_one, figure_two
from channels.gates import load_config, run_gates
from channels.loaders.inspect_logs import InspectLogLoader
from channels.loaders.mythos_transcript import MythosTranscriptLoader
from channels.record import build_record, write_record
from channels.schema import CorpusDescription, TurnObservation

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "channels.yaml"
DEFAULT_RESULTS = REPO_ROOT / "results"
DEFAULT_MYTHOS = (
    REPO_ROOT / "data" / "mythos-5-incident-transcript" / "transcript.jsonl"
)
DEFAULT_INSPECT_LOGS = REPO_ROOT / "data" / "inspect_logs"


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a non-zero exit code when a gate fails."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except ChannelsError as error:
        # Domain errors are the point of this package: print them plainly rather than
        # as a traceback, and exit non-zero so a pipeline notices.
        print(f"error: {error}", file=sys.stderr)
        return 2


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser. Three subcommands: describe, measure, gate."""
    parser = argparse.ArgumentParser(
        prog="channels",
        description="Measure how observable a model's reasoning was.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    describe = subparsers.add_parser(
        "describe", help="report what each corpus contains, without analysing it"
    )
    _add_corpus_arguments(describe)
    describe.set_defaults(handler=_run_describe)

    measure = subparsers.add_parser(
        "measure", help="build the observability record and both figures"
    )
    _add_corpus_arguments(measure)
    measure.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    measure.add_argument("--bins", type=int, default=10)
    measure.add_argument("--stage2-recall", type=float, default=1.0)
    measure.set_defaults(handler=_run_measure)

    gate = subparsers.add_parser("gate", help="run the gates and exit non-zero on fail")
    _add_corpus_arguments(gate)
    gate.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    gate.set_defaults(handler=_run_gate)

    return parser


def _add_corpus_arguments(parser: argparse.ArgumentParser) -> None:
    """Corpus paths, shared by every subcommand."""
    parser.add_argument("--mythos", type=Path, default=DEFAULT_MYTHOS)
    parser.add_argument("--inspect-logs", type=Path, default=DEFAULT_INSPECT_LOGS)


def _collect(
    args: argparse.Namespace,
) -> tuple[list[TurnObservation], list[CorpusDescription], list[str]]:
    """Load every available corpus, and report by name the ones that are not.

    An unavailable corpus is returned in the third element rather than skipped in
    silence. A record that does not say which corpora were missing invites the reader
    to assume they were empty.
    """
    observations: list[TurnObservation] = []
    descriptions: list[CorpusDescription] = []
    missing: list[str] = []

    mythos = MythosTranscriptLoader(args.mythos)
    if mythos.available():
        observations.extend(mythos.observations())
        descriptions.append(mythos.describe())
    else:
        missing.append(f"mythos_transcript (looked in {args.mythos})")

    logs = InspectLogLoader(args.inspect_logs)
    if logs.available():
        observations.extend(logs.observations())
        descriptions.append(logs.describe())
    else:
        missing.append(f"inspect_logs (looked in {args.inspect_logs})")

    return observations, descriptions, missing


def _run_describe(args: argparse.Namespace) -> int:
    """Print one description per available corpus, and name the unavailable ones."""
    _, descriptions, missing = _collect(args)
    for description in descriptions:
        print(f"\n{description.name}")
        print(f"  utterances        {description.n_utterances}")
        print(f"  actors            {description.n_actors}")
        print(f"  concentration     {description.actor_concentration}")
        print(f"  source hash       {description.source_hash}")
        print(f"  licence           {description.licence}")
        for caveat in description.caveats:
            print(f"  caveat            {caveat}")
    for name in missing:
        print(f"\nNOT AVAILABLE: {name}")
    return 0


def _run_measure(args: argparse.Namespace) -> int:
    """Build the record and both figures from whatever corpora are present."""
    observations, descriptions, missing = _collect(args)
    if not observations:
        print(
            "error: no corpus was available, so there is nothing to measure. "
            f"Checked: {'; '.join(missing)}",
            file=sys.stderr,
        )
        return 2

    cells = build_cells(observations)
    results = args.results
    figure_one(cells, results / "figures" / "figure1_emission_states.png")

    binned = binned_profile(cells, n_bins=args.bins)
    figure_two(
        binned,
        results / "figures" / "figure2_recall_ceiling.png",
        stage2_recall=args.stage2_recall,
        step_label=f"trajectory position ({args.bins} equal-width bins of step index)",
    )

    record = build_record(
        corpora=descriptions,
        cells=cells,
        positional=binned,
        codebook_hash=_codebook_hash(),
        stage2_recall=args.stage2_recall,
    )
    path = write_record(record, results / "observability_record.json")
    print(f"wrote {path}")
    for name in missing:
        print(f"NOT AVAILABLE: {name}")
    return 0


def _run_gate(args: argparse.Namespace) -> int:
    """Run the gates. Un-evaluable counts as failure, so an empty corpus exits 1."""
    observations, _, missing = _collect(args)
    cells = build_cells(observations)
    config = load_config(args.config)
    results = run_gates(cells, config, _codebook_hash(), _registered_codebook_hash())

    failed = False
    for result in results:
        marker = "FAIL" if result.failed else result.status.value.upper()
        print(f"[{marker:>10}] {result.name}: {result.detail}")
        failed = failed or result.failed
    for name in missing:
        print(f"NOT AVAILABLE: {name}")
    return 1 if failed else 0


def _codebook_hash() -> str:
    """The codebook hash, or an explicit marker when the codebook is not built yet."""
    try:
        from channels.codebook import codebook_hash
    except ImportError:
        return "TODO(johanna): codebook module not built"
    try:
        return str(codebook_hash())
    except FileNotFoundError:
        return "TODO(johanna): codebook YAML not written"


def _registered_codebook_hash() -> str:
    """The codebook hash recorded in the pre-registration, or an empty string."""
    prereg = REPO_ROOT / "docs" / "PREREGISTRATION.md"
    if not prereg.is_file():
        return ""
    for line in prereg.read_text().splitlines():
        if "Codebook SHA-256" in line and "|" in line:
            return line.split("|")[2].strip().strip("`")
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
