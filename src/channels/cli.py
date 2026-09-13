"""`channels` — the command line that produces the record, the figures and the gates."""

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from channels.emission import binned_profile, build_cells
from channels.errors import ChannelsError
from channels.figures import figure_one, figure_two, task_class_spread
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
DEFAULT_REASONING_LOGS = REPO_ROOT / "data" / "inspect-runs-reasoning"
DEFAULT_AGENTIC_LOGS = REPO_ROOT / "data" / "inspect-runs-agentic"
DEFAULT_CTF_LOGS = REPO_ROOT / "data" / "inspect-runs-ctf"

#: Largest within-model spread across task classes that still permits pooling
#: them into one bar. Above this, pooling would hide variation the figure exists
#: to show, which is the reporting-unit failure this package names.
MAX_POOLABLE_SPREAD = 0.05


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
    parser.add_argument(
        "--reasoning-logs", type=Path, default=DEFAULT_REASONING_LOGS
    )
    parser.add_argument(
        "--agentic-logs", type=Path, default=DEFAULT_AGENTIC_LOGS
    )
    parser.add_argument("--ctf-logs", type=Path, default=DEFAULT_CTF_LOGS)


#: Each corpus keeps its own record file. Records are never pooled across corpora:
#: see `_corpora` for why. The key is the corpus name, the value the record filename.
RECORD_FILENAMES = {
    "inspect_logs": "observability_record.json",
    "mythos_transcript": "observability_record_mythos.json",
    "inspect_logs_reasoning": "observability_record_reasoning.json",
    "inspect_logs_agentic": "observability_record_agentic.json",
    "inspect_logs_ctf": "observability_record_ctf.json",
}


def _corpora(
    args: argparse.Namespace,
) -> tuple[list[tuple[CorpusDescription, list[TurnObservation]]], list[str]]:
    """Load each available corpus separately, and name the ones that are not there.

    Corpora are kept apart rather than concatenated because their step indices do
    not mean the same thing. Mythos is one 2,061-turn trajectory whose positions are
    binned into deciles; the Inspect logs are 3,039 independent samples of one or two
    turns each. Pooling them would put a decile bin and a turn ordinal in the same
    `positional_profile` key and produce a c(j) that describes neither — which is the
    undefined-denominator failure this package exists to name. Figure 1 is safe to
    draw across both because each of its bars is a single model x task class.

    An unavailable corpus is returned in the second element rather than skipped in
    silence. A record that does not say which corpora were missing invites the reader
    to assume they were empty.
    """
    groups: list[tuple[CorpusDescription, list[TurnObservation]]] = []
    missing: list[str] = []

    mythos = MythosTranscriptLoader(args.mythos)
    if mythos.available():
        groups.append((mythos.describe(), list(mythos.observations())))
    else:
        missing.append(f"mythos_transcript (looked in {args.mythos})")

    logs = InspectLogLoader(args.inspect_logs)
    if logs.available():
        groups.append((logs.describe(), list(logs.observations())))
    else:
        missing.append(f"inspect_logs (looked in {args.inspect_logs})")

    reasoning = InspectLogLoader(
        getattr(args, "reasoning_logs", DEFAULT_REASONING_LOGS),
        name="inspect_logs_reasoning",
        label_by_directory=True,
        licence=(
            "run artefacts of this project via OpenRouter; "
            "model terms vary by vendor"
        ),
    )
    if reasoning.available():
        groups.append((reasoning.describe(), list(reasoning.observations())))
    else:
        missing.append(
            f"inspect_logs_reasoning (looked in {reasoning.root})"
        )

    agentic = InspectLogLoader(
        getattr(args, "agentic_logs", DEFAULT_AGENTIC_LOGS),
        name="inspect_logs_agentic",
        licence="run artefacts of this project via OpenRouter; model terms vary",
        label_by_directory=True,
    )
    if agentic.available():
        groups.append((agentic.describe(), list(agentic.observations())))
    else:
        missing.append(f"inspect_logs_agentic (looked in {agentic.root})")

    ctf = InspectLogLoader(
        getattr(args, "ctf_logs", DEFAULT_CTF_LOGS),
        name="inspect_logs_ctf",
        licence="run artefacts of this project via OpenRouter; model terms vary",
        label_by_directory=True,
    )
    if ctf.available():
        groups.append((ctf.describe(), list(ctf.observations())))
    else:
        missing.append(f"inspect_logs_ctf (looked in {ctf.root})")

    return groups, missing


def _collect(
    args: argparse.Namespace,
) -> tuple[list[TurnObservation], list[CorpusDescription], list[str]]:
    """Every corpus's observations concatenated, for the gates and for Figure 1."""
    groups, missing = _corpora(args)
    observations: list[TurnObservation] = []
    descriptions: list[CorpusDescription] = []
    for description, corpus_observations in groups:
        descriptions.append(description)
        observations.extend(corpus_observations)
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
    observations, _descriptions, missing = _collect(args)
    if not observations:
        print(
            "error: no corpus was available, so there is nothing to measure. "
            f"Checked: {'; '.join(missing)}",
            file=sys.stderr,
        )
        return 2

    results = args.results

    # Figure 1 spans every corpus: each bar is one model x task class, so no bar
    # mixes corpora and the comparison it invites is the intended one.
    # Pooling task classes is justified by measurement, not assumption:
    # task_class_spread is <=0.011 for every model in both corpora, so a bar per
    # model hides no variation. Recomputed here so the justification cannot
    # silently expire when a new corpus arrives.
    cells = build_cells(observations)
    spread = max(task_class_spread(cells).values(), default=0.0)
    by_task = spread > MAX_POOLABLE_SPREAD
    _write_figure_caption(
        *figure_one(
            cells,
            results / "figures" / "figure1_emission_states.png",
            by_task=by_task,
        )
    )
    if not by_task:
        print(
            f"figure 1: task classes pooled (max within-model spread "
            f"{spread:.4f} <= {MAX_POOLABLE_SPREAD})"
        )

    groups, _ = _corpora(args)
    for description, corpus_observations in groups:
        _measure_one_corpus(args, description, corpus_observations)

    for name in missing:
        print(f"NOT AVAILABLE: {name}")
    return 0


def _write_figure_caption(figure_path: Path, caption: str) -> None:
    """Write a figure's caption next to it, so the two can never drift apart.

    A committed figure whose caption describes an earlier run is worse than no
    caption: it states an n that the image does not show.
    """
    figure_path.with_name(f"{figure_path.stem}_caption.txt").write_text(
        caption + "\n", encoding="utf-8"
    )


def _slug(name: str) -> str:
    """Filesystem-safe form of an arm label, for per-arm figure filenames."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")


def _measure_one_corpus(
    args: argparse.Namespace,
    description: CorpusDescription,
    observations: Sequence[TurnObservation],
) -> None:
    """Write one corpus's positional figure and its own record."""
    cells = build_cells(observations)
    binned = binned_profile(cells, n_bins=args.bins)
    results = args.results
    suffix = "" if description.name == "inspect_logs" else f"_{description.name}"

    # One positional figure PER ARM, not per corpus. c(j) is a profile, and
    # averaging a raw-emitting arm with a fully-redacted one produces a curve
    # that describes neither: the agentic corpus pooled to "lowest at position 2
    # (0.490)", a number belonging to no arm that was run. Corpora with a single
    # arm are unaffected and keep their existing filename.
    arms = sorted({obs.model for obs in observations})
    for arm in arms:
        arm_obs = [obs for obs in observations if obs.model == arm]
        arm_binned = binned_profile(build_cells(arm_obs), n_bins=args.bins)
        arm_suffix = suffix if len(arms) == 1 else f"{suffix}_{_slug(arm)}"
        n_traj = len({obs.sample_id for obs in arm_obs})
        _write_figure_caption(
            *figure_two(
                arm_binned,
                results / "figures" / f"figure2_recall_ceiling{arm_suffix}.png",
                stage2_recall=args.stage2_recall,
                step_label=(
                    f"trajectory position "
                    f"({len(arm_binned)} equal-width bins of step index)"
                ),
                panel_title=(
                    f"Measured: {arm} — {len(arm_obs)} turns over "
                    f"{n_traj} trajector" + ("y" if n_traj == 1 else "ies")
                ),
            )
        )

    record = build_record(
        corpora=[description],
        cells=cells,
        positional=binned,
        codebook_hash=_codebook_hash(),
        stage2_recall=args.stage2_recall,
    )
    filename = RECORD_FILENAMES.get(
        description.name, f"observability_record_{description.name}.json"
    )
    path = write_record(record, results / filename)
    print(f"wrote {path}  [{description.name}: {description.n_utterances} turns]")


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
