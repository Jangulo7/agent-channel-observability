"""Compute C1, C2 and C3 from the coder's labels. One command, no decisions left.

    uv run python scripts/analyse_annotations.py

Every threshold below was fixed in the analysis plan §0.2 (pre-specified, not
independently registered) BEFORE any
label existed. This script applies them; it does not choose them. If a result
falls the wrong side of a line, that is the registration working.
"""

from __future__ import annotations

import sys
from pathlib import Path

from channels._vendored_stats import wilson_interval, wilson_upper_bound
from channels.annotate import ANNOTATION_DIR, cohens_kappa, load_record
from channels.cluster import both_clusterings
from channels.codebook import codebook_hash
from channels.loaders.collusion_wiki import CollusionWikiLoader
from channels.provenance import assert_primary_eligible
from channels.schema import Channel

RESULTS: dict = {}

CORPUS = Path("data/german-collusion-wiki")

#: Pre-specified in the analysis plan §0.2. Not adjustable here, by design.
REVERT_VALIDATED_LOWER_BOUND = 0.50
KAPPA_ADEQUATE = 0.60
KAPPA_UNRELIABLE = 0.40
OBJECTION_CODES = {"o", "r", "e", "w"}

#: Coder ids that are warm-up or smoke-test runs and never enter an endpoint.
#: The practice round in check_setup.sh writes one of these, and it is coded
#: under whatever codebook happened to be current at the time.
EXCLUDED_CODERS = frozenset({"practice", "smoke_test", "smoke_test_b"})

#: The codebook author's coder id. Registration §0.2 fixes two roles that the
#: file-name sort cannot: the BLIND coder is C1's primary, and the AUTHOR is only
#: ever the SECOND coder for the C3 reliability check (never C1's primary, because
#: the author is not blind). This orders records so the author is last; it does not
#: change kappa, which is symmetric.
AUTHOR_CODER_ID = "JAD"


def _records(task: str) -> list:
    """Every saved record for one task, newest coder last."""
    records = []
    for path in sorted(ANNOTATION_DIR.glob("*.json")):
        # Coder records are named `<task>_n<N>_seed<seed>__<coder>.json`; skip anything
        # without the `__coder` marker (e.g. this script's own analysis_results.json,
        # which shares the directory and is not a record).
        if "__" not in path.stem:
            continue
        record = load_record(path)
        if record.task == task and record.coder_id not in EXCLUDED_CODERS:
            records.append(record)
    # Registered roles, not alphabetical order: the author is always last so C1's
    # primary is the blind coder and C3's second coder is the author (§0.2).
    records.sort(key=lambda r: r.coder_id == AUTHOR_CODER_ID)
    return records


def _check_codebook(records: list) -> None:
    """Refuse to analyse labels coded under a different instrument."""
    current = codebook_hash()
    for record in records:
        if record.codebook_hash != current:
            raise SystemExit(
                f"REFUSED: {record.coder_id} coded under {record.codebook_hash}, "
                f"but the codebook is now {current}. The labels are not "
                "comparable with the registered instrument."
            )


def c1_revert_precision() -> None:
    """Of the reverts the detector flags, what share are genuine disagreement?"""
    records = _records("revert_validity")
    if not records:
        print("C1: no revert_validity labels yet\n")
        return
    _check_codebook(records)
    primary = records[0]
    labels = {label.uid: label.choice for label in primary.labels}
    n = len(labels)
    disagreement = sum(1 for c in labels.values() if c == "d")
    unclear = sum(1 for c in labels.values() if c == "u")

    interval = wilson_interval(disagreement, n)
    RESULTS["c1"] = {"coder": primary.coder_id, "n": n, "disagreement": disagreement,
                     "housekeeping": n - disagreement - unclear, "unclear": unclear,
                     "precision": disagreement / n,
                     "naive_ci95": [interval.low, interval.high]}
    print(f"C1 — revert precision   coder={primary.coder_id}  n={n}")
    print(f"  disagreement {disagreement}, housekeeping "
          f"{n - disagreement - unclear}, unclear {unclear}")
    print(f"  precision {disagreement / n:.4f} "
          f"naive 95% CI [{interval.low:.4f}, {interval.high:.4f}]")

    _c1_clustered(disagreement, labels)
    print()


def _c1_clustered(disagreement: int, labels: dict[str, str]) -> None:
    """Clustered by page (primary) and actor (sensitivity), as registered."""
    n = len(labels)
    utts = {
        u.uid: u
        for u in CollusionWikiLoader(CORPUS).load()
        if u.channel is Channel.ARTEFACT_EDIT
    }
    coded = [utts[uid] for uid in labels if uid in utts]
    # These utterances are the C1 denominator, so they are where the provenance
    # guard belongs. It raises rather than filtering, so a paraphrased or
    # investigator-written edit cannot quietly shrink the denominator.
    assert_primary_eligible(coded)
    if len(coded) == n:
        for field, rate in both_clusterings(disagreement, coded).items():
            low = f"{rate.ci_low:.4f}" if rate.ci_low is not None else "n/a"
            high = f"{rate.ci_high:.4f}" if rate.ci_high is not None else "n/a"
            RESULTS.setdefault("c1", {}).setdefault("clustered", {})[field] = {
                "ci95": [rate.ci_low, rate.ci_high], "n_clusters": rate.n_clusters}
            print(f"  clustered by {field:6s} [{low}, {high}] "
                  f"n_clusters={rate.n_clusters}")
            if field == "page":
                verdict = (
                    "VALIDATED" if rate.ci_low is not None
                    and rate.ci_low > REVERT_VALIDATED_LOWER_BOUND
                    else "NOT validated"
                )
                RESULTS["c1"]["verdict"] = verdict
                print(f"  -> REVERT is {verdict} "
                      f"(registered rule: page-clustered lower bound > "
                      f"{REVERT_VALIDATED_LOWER_BOUND})")


def c2_message_objection() -> None:
    """Does the inter-agent message channel carry verbal objection at all?"""
    records = _records("message_code")
    if not records:
        print("C2: no message_code labels yet\n")
        return
    _check_codebook(records)
    primary = records[0]
    labels = [label.choice for label in primary.labels]
    n = len(labels)
    objections = sum(1 for c in labels if c in OBJECTION_CODES)
    RESULTS["c2"] = {"coder": primary.coder_id, "n": n, "objections": objections}
    print(f"C2 — verbal objection   coder={primary.coder_id}  n={n}")
    print(f"  OBJ/REF/ESC/WARN: {objections}")
    if objections == 0:
        bound = wilson_upper_bound(0, n)
        RESULTS["c2"]["zero_upper_bound_95"] = bound
        print(f"  -> zero observed; rate below {bound:.4f} with 95% confidence")
        print("     (registered wording: never 'no objection occurs')")
    else:
        interval = wilson_interval(objections, n)
        print(f"  -> rate {objections / n:.4f} "
              f"[{interval.low:.4f}, {interval.high:.4f}]")
        print("     transfer of the instrument to this channel is UNVALIDATED")
    print()


def c3_reliability() -> None:
    """Agreement between the coder and the author on shared items."""
    records = _records("revert_validity")
    if len(records) < 2:
        print(f"C3: needs two coders, found {len(records)}\n")
        return
    _check_codebook(records)
    first, second = records[0], records[1]
    a = {label.uid: label.choice for label in first.labels}
    b = {label.uid: label.choice for label in second.labels}
    kappa, overlap = cohens_kappa(a, b)
    agreed = sum(1 for uid in set(a) & set(b) if a[uid] == b[uid])
    reliable = "unreliable" if kappa < KAPPA_UNRELIABLE else (
        "adequate" if kappa >= KAPPA_ADEQUATE else "marginal")
    RESULTS["c3"] = {"coder": first.coder_id, "author": second.coder_id,
                     "n": overlap, "percent_agreement": agreed / overlap,
                     "kappa": kappa, "verdict": reliable}
    print(f"C3 — reliability   {first.coder_id} vs {second.coder_id}  n={overlap}")
    print(f"  percent agreement {agreed / overlap:.4f}   kappa {kappa:.4f}")
    if kappa >= KAPPA_ADEQUATE:
        print("  -> adequate reproducibility for an exploratory instrument")
    elif kappa < KAPPA_UNRELIABLE:
        print("  -> BELOW 0.40: C1 is reported as unreliable regardless of its "
              "point estimate")
    else:
        print("  -> between 0.40 and 0.60: report as marginal")
    print("  NOTE: the second coder wrote the codebook. This measures whether "
          "the written\n        rules reproduce the author's intent, NOT "
          "inter-rater reliability.")
    print()


def main() -> int:
    """Run all three registered endpoints."""
    if not ANNOTATION_DIR.is_dir() or not list(ANNOTATION_DIR.glob("*.json")):
        print(f"no annotation records under {ANNOTATION_DIR}", file=sys.stderr)
        return 2
    print(f"codebook {codebook_hash()}\n")
    c1_revert_precision()
    c2_message_objection()
    c3_reliability()
    import json
    out = ANNOTATION_DIR / "analysis_results.json"
    out.write_text(json.dumps(
        {"codebook_hash": codebook_hash(),
         "decision_rules": {
             "revert_validated_lower_bound": REVERT_VALIDATED_LOWER_BOUND,
             "kappa_adequate": KAPPA_ADEQUATE,
             "kappa_unreliable": KAPPA_UNRELIABLE,
         },
         "endpoints": RESULTS}, indent=2) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
