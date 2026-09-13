"""Hand-coding tool for the collusion.wiki corpus.

    uv run python scripts/annotate.py --task revert_validity --coder coder_a
    uv run python scripts/annotate.py --task message_code   --coder coder_a --n 300
    uv run python scripts/annotate.py --kappa revert_validity_n150_seed7

Resumable: stop with Ctrl-C or `q` and re-run the same command to continue.
The coder never sees a detector's prediction, and the saved file holds uids and
codes only - no corpus text - so `results/annotations/` is publishable.
"""

from __future__ import annotations

import argparse
import difflib
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from channels.annotate import (
    ANNOTATION_DIR,
    TASKS,
    AnnotationRecord,
    AnnotationTask,
    Label,
    cohens_kappa,
    draw_sample,
    load_record,
    sample_id_for,
)
from channels.codebook import codebook_hash
from channels.loaders.collusion_wiki import CollusionWikiLoader
from channels.schema import Channel, Utterance

CORPUS_ROOT = Path("data/german-collusion-wiki")
DEFAULT_N = {"revert_validity": 60, "message_code": 200}
DEFAULT_SEED = 7


def _population(task: AnnotationTask, loader: CollusionWikiLoader) -> list[Utterance]:
    """The utterances this task draws from."""
    utterances = list(loader.load())
    if task.name == "revert_validity":
        return [
            utt
            for utt in utterances
            if utt.channel is Channel.ARTEFACT_EDIT and utt.corpus_meta.get("is_revert")
        ]
    return [
        utt
        for utt in utterances
        if utt.channel is Channel.INTER_AGENT_MESSAGE and utt.text
    ]


def _revisions_by_id(loader: CollusionWikiLoader) -> dict[str, dict[str, Any]]:
    """Raw revision rows, needed locally to render a diff for the coder."""
    return {str(row["rev_id"]): row for row in loader._rows("revisions")}


def _context_for_revert(utt: Utterance, rows: dict[str, dict[str, Any]]) -> str:
    """Render what this revert undid, so the coder can judge intent.

    Body text is shown from the LOCAL export and never leaves the machine: the
    rule is publish counts not text, not never look at it.
    """
    rev_id = utt.uid.split(":")[1]
    row = rows.get(rev_id, {})
    page = str(utt.thread_id)
    same_page = sorted(
        (r for r in rows.values() if str(r.get("page_key")) == page),
        key=lambda r: (r.get("seq") or 0, str(r.get("time") or "")),
    )
    index = next(
        (i for i, r in enumerate(same_page) if str(r["rev_id"]) == rev_id), None
    )
    lines = [
        f"  page            {page}",
        f"  rev_id          {rev_id}",
        f"  reverting actor {utt.actor}",
        f"  change summary  {str(row.get('change_summary') or '')!r}",
    ]
    if index is None or index == 0:
        return "\n".join(lines)

    undone = same_page[index - 1]
    lines += [
        f"  undone actor    {undone.get('label')}",
        f"  undone summary  {str(undone.get('change_summary') or '')!r}",
    ]
    diff = difflib.unified_diff(
        str(undone.get("body") or "").splitlines(),
        str(row.get("body") or "").splitlines(),
        lineterm="",
        n=1,
    )
    body = [line for line in diff if not line.startswith(("---", "+++", "@@"))]
    removed = sum(1 for line in body if line.startswith("-"))
    added = sum(1 for line in body if line.startswith("+"))

    # Neutral counts, shown before the diff. These are facts about the edit, not
    # judgements about it: a coder should not have to count 200 lines by eye to
    # see that a whole block was deleted. Nothing here hints at d/h/u.
    lines.insert(
        4, f"  size            {removed} line(s) removed, {added} line(s) restored"
    )
    lines += ["", "  --- what this revert removed (- removed, + restored) ---"]
    # The whole diff, always. Truncating it forced "unclear" on items whose
    # evidence was merely off-screen, and an expand key would have put a display
    # action among the coding choices, as though "show me more" were a third
    # opinion about the item. The terminal scrolls; the judgement should not be
    # shaped by what happened to fit.
    for line in body:
        lines.append(f"  {line[:110]}")
    return "\n".join(lines)


def _context_for_message(utt: Utterance) -> str:
    """The message itself, with no prediction attached."""
    return "\n".join(
        [
            f"  page            {utt.thread_id}",
            f"  actor           {utt.actor}",
            "",
            f'  message         "{utt.text}"',
        ]
    )


def _prompt(task: AnnotationTask, recap: str = "") -> str:
    """The choice menu. Coding choices only - no display actions belong here."""
    lines = []
    if recap:
        # A long diff pushes the header off-screen, so the identifying facts are
        # repeated next to the question. This is a recap, not a new option.
        lines += [f"  ({recap})", ""]
    lines += [f"  {task.question}", ""]
    for key, meaning in task.choices.items():
        lines.append(f"    [{key}] {meaning}")
    # Skip is Enter and quit is [.] — NEITHER may be a codebook key, or a real
    # code would be swallowed. That bug dropped every SHARE ("s") press in the
    # message task on 2026-09-13; see PREREGISTRATION §11. `_run` asserts no clash.
    lines.append("    [enter] skip for now      [.] save and quit")
    return "\n".join(lines)


def _run(args: argparse.Namespace) -> int:
    """Draw or resume a sample and take labels until it is finished or quit."""
    task = TASKS[args.task]
    reserved = {"", "."} & set(task.choice_keys())
    if reserved:
        raise SystemExit(
            f"task {task.name!r} uses a reserved control key {sorted(reserved)}; "
            "skip is Enter and quit is '.', so no code may use them"
        )
    loader = CollusionWikiLoader(args.corpus)
    if not loader.available():
        print(f"corpus not found under {args.corpus}", file=sys.stderr)
        return 2

    population = _population(task, loader)
    n = args.n or DEFAULT_N[task.name]
    sample = draw_sample(population, task, n, args.seed)
    sample_id = sample_id_for(task, n, args.seed)

    record = AnnotationRecord(
        sample_id=sample_id,
        task=task.name,
        codebook_hash=codebook_hash(),
        coder_id=args.coder,
        n_requested=n,
        seed=args.seed,
    )
    existing = record.path(args.out)
    if existing.is_file():
        record = load_record(existing)
        print(f"resuming {existing.name}: {len(record.labels)}/{n} already coded")

    rows = _revisions_by_id(loader) if task.name == "revert_validity" else {}
    done = record.coded_uids
    remaining = [utt for utt in sample if utt.uid not in done]
    print(f"\ncodebook {codebook_hash()[:26]}...  coder={args.coder}")
    print(f"{len(remaining)} of {n} items left. Population: {len(population)}.\n")

    for position, utt in enumerate(remaining, start=len(done) + 1):
        print("=" * 78)
        print(f"[{position}/{n}]")
        if task.name == "revert_validity":
            print(_context_for_revert(utt, rows))
            recap = f"item {position}/{n} - {utt.thread_id}"
        else:
            print(_context_for_message(utt))
            recap = ""
        print()
        print(_prompt(task, recap))
        started = time.monotonic()
        try:
            choice = input("\n  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\ninterrupted")
            break
        if choice == ".":
            break
        if choice == "":
            continue  # Enter = skip for now; the item stays in `remaining`
        if choice not in task.choice_keys():
            print(f"  '{choice}' is not a valid choice; skipping")
            continue
        record.labels.append(
            Label(
                uid=utt.uid,
                choice=choice,
                seconds=round(time.monotonic() - started, 2),
                utc=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        )
        record.save(args.out)

    path = record.save(args.out)
    print(f"\nsaved {len(record.labels)}/{n} labels to {path}")
    if record.labels:
        median = sorted(label.seconds for label in record.labels)[
            len(record.labels) // 2
        ]
        print(f"median {median:.1f}s per item")
    return 0


def _run_kappa(args: argparse.Namespace) -> int:
    """Report Cohen's kappa across every coder who worked on one sample."""
    files = sorted(args.out.glob(f"{args.kappa}__*.json"))
    if len(files) < 2:
        print(
            f"need two coders for {args.kappa}; found {len(files)} file(s)",
            file=sys.stderr,
        )
        return 2
    records = [load_record(path) for path in files]
    for first_index in range(len(records)):
        for second_index in range(first_index + 1, len(records)):
            first, second = records[first_index], records[second_index]
            if first.codebook_hash != second.codebook_hash:
                print(
                    f"REFUSED {first.coder_id} vs {second.coder_id}: coded against "
                    "different codebook versions; the labels are not comparable"
                )
                continue
            a = {label.uid: label.choice for label in first.labels}
            b = {label.uid: label.choice for label in second.labels}
            kappa, overlap = cohens_kappa(a, b)
            agreed = sum(1 for uid in set(a) & set(b) if a[uid] == b[uid])
            print(
                f"{first.coder_id} vs {second.coder_id}: n={overlap} "
                f"agreement={agreed / overlap:.3f} kappa={kappa:.3f}"
            )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Hand-code collusion.wiki items.")
    parser.add_argument("--task", choices=sorted(TASKS), default="revert_validity")
    parser.add_argument("--coder", default="coder_a", help="coder id, e.g. coder_b")
    parser.add_argument("--n", type=int, default=None)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--corpus", type=Path, default=CORPUS_ROOT)
    parser.add_argument("--out", type=Path, default=ANNOTATION_DIR)
    parser.add_argument("--kappa", default=None, help="sample id to score instead")
    args = parser.parse_args(argv)
    return _run_kappa(args) if args.kappa else _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
