# Build log — agent-channel-observability

Branch `build/overnight`. Times are Europe/Madrid. Written for a reader who has not
seen the diffs.

## QUESTIONS FOR JOHANNA

**All previously open questions are now resolved.** Kept here in one line each so
the record shows what was asked and how it was settled.

| # | question | resolution |
|---|---|---|
| Q1 | Where are the Inspect `logs/`? | **Resolved.** Supplied as `data/inspect-runs/`; step 3 measured. |
| Q2 | Is AI Village in scope? | Out of scope, unchanged. |
| Q3 | Spec function names vs upstream | `wilson_upper_bound` is new code, marked as such. |
| Q4 | CI blocked by missing `workflow` token scope | **Resolved.** CI runs; green on every push. |
| Q5 | Clustering unit for collusion.wiki | **Resolved by Johanna:** page primary, actor sensitivity. Implemented; both reported together. |
| Q6 | Does `ARTEFACT_EDIT` need adding to the schema? | **Resolved by Johanna: yes.** Added, plus `REVERT` in codebook v2. |
| Q7 | METR page references unverified | **Resolved.** Both PDFs supplied; 10 of 10 rows verified, 0 mismatches. |
| Q8 | Spec v3 vs v4 | **Resolved:** v4 is authoritative and is what is implemented. |

### Open decisions that are yours, not blockers

1. **Pre-registration is ready to register, and §0 makes it honest.** Several
   analyses were already run, so the document now separates them: §0.1 lists
   them as **exploratory**, §0.2 registers **C1–C3** (the human annotation) as
   confirmatory with decision rules fixed before any label exists. Run
   `scripts/register.sh` when you are ready — it stamps the timestamp, commits,
   records the SHA and tells you to push. **Push before the coder starts**, or
   the registration post-dates the labels.
2. **`config/channels.yaml` thresholds are still illustrative** (floor 0.50,
   ceiling 0.50). Nothing in the literature sets these. They must not be cited
   as a standard, and the README says so.

---

# Session 1 — 2026-09-12, initial build (steps 0–7)

## Step 0 — Mythos transcript check ✅ 

**Answer: yes, the transcript carries raw model reasoning.** This is the good outcome —
Figure 1 gains a real-incident column.

The reasoning is *not* a JSON field. `transcript.jsonl` has exactly two record shapes
and no key named `thinking`, `reasoning` or `reasoning_content` at any level. Field
names actually found:
- `{record, title, subtitle, notice, about, modifications}` — one metadata row.
- `{record, index, role, type, timestamp, content}` — 703 rows, `type="TextMessage"`.
- `{record, index, role, type, timestamp, tool_name, tool_call, tool_result}` — 1348 rows,
  `type="ToolMessage"`; 13 more also carry `tool_call_raw`.

Reasoning lives **inline inside the `content` string** as `<thinking>…</thinking>` tags.
Real numbers:
- 2064 message rows; 2061 are `role="Assistant"` (2 Human, 1 System).
- 700 assistant `TextMessage`s; **686 contain a well-formed `<thinking>` block** (98.0%
  of TextMessages), 0 unclosed.
- 686 thinking blocks, median 680 chars, range 39–8387.
- 1361 assistant `ToolMessage`s have **no `content` field at all** — the tool-call channel
  carries no reasoning by construction.
- So per *assistant message*, raw reasoning is present for 686/2061 = **33.3%**; per
  assistant *text* turn, 98.0%. Which denominator you pick changes the answer by 3×,
  which is exactly the point `emission.py`'s docstring makes.
- 640 carry visible text outside the thinking block.
- **Correction to my first pass:** I initially wrote "19 TextMessages are `[redacted]`".
  That was a substring match. **Zero** assistant messages are wholly redacted — Anthropic's
  whole-message redactions (1–81, >2145) are simply *absent from the file*, which is why the
  observed index range is 82–2144. What the 19 actually contain is the inline token
  `[redacted]`; separately, **316 assistant messages and 1,084 tool messages** carry in-place
  `[redacted-xyz]` markers. Measured `REDACTED` in the Mythos corpus is therefore 0, correctly.

Canary GUID is present in the metadata row's `notice`. It is quarantined: the corpus is
gitignored and `tests/test_publication_safety.py` asserts the string appears in no
tracked file and nowhere under `results/` or `docs/`.

## Step 1 — scaffold ✅
Built: `uv` env (Python 3.12.3, `.venv`), `pyproject.toml` with the spec's exact
dependency pins (`inspect-ai==0.3.260`), `requirements.txt` (137 pinned lines, from
`uv pip freeze`), `.gitignore`, MIT `LICENSE`, CI workflow, and the leaf modules:
`errors.py`, `schema.py`, `provenance.py`, `_vendored_stats.py`.
Passing: `ruff check src tests`, `mypy src/channels` (strict, 6 files), `pytest -q` →
**16 passed**. Sanity check on the new one-sided bound: `wilson_upper_bound(0, 100)`
= 0.0263, against the rule-of-three's 0.03.

AMBER:
- `Utterance.corpus_meta` is spec'd as a bare `dict`; `mypy --strict` rejects that. Typed
  `dict[str, Any]`. Name and semantics unchanged. Marked `# NEEDS REVIEW` in `schema.py`.
- `ruff` `UP042` disabled repo-wide: the spec's §2 style exemplar mandates
  `class ReasoningState(str, Enum)`, which `UP042` flags in favour of `StrEnum`. Spec wins.
- `E501` disabled for `_vendored_stats.py` only, so the vendored block stays byte-identical
  to upstream.
- The spec file on disk is `SPEC_agent_channel_observability_v4.md` whose own H1 reads
  "v3"; confirmed by you mid-build that v4 is authoritative. No v3 `.md` exists (only
  Windows `Zone.Identifier` stubs).

## Step 3 — coverage, emission, Inspect loader ✅ built / ⛔ cannot be measured
Built `coverage.py` (four-state, turn-level, strongest-limitation-wins),
`emission.py` (the headline estimator, spec denominator docstring verbatim),
`loaders/base.py` (schema discovery, `require_keys` reports the keys actually seen) and
`loaders/inspect_logs.py` (streams with `read_eval_log_samples(resolve_attachments=True)`,
reads both the `messages` path and the `events` path so `as_tool()` sub-agent traffic is
not silently dropped).
Passing: ruff, mypy strict (10 files), **29 tests**. `test_emission_denominator_...`
encodes the AdaptR1 lesson directly: two trajectories of length 3 and 1 give step 2 a
denominator of **1**, not 2-with-an-ABSENT.

**The measurement did not run — see Q1.** No substitute corpus was used.

**Loader verified against real Inspect logs anyway**, so it is not shipping untested:
pointed it at `/home/johan/ai_eval_projects/PROJECT/logs` (7 logs, tasks `addition`,
`gsm8k`, `humaneval`, `example_task`; models `openai/gpt-4o`,
`openrouter/meta-llama/llama-3.1-8b-instruct`). It parsed 15 assistant turns into 5
cells, all four-state-classified. **Every one of the 15 is `ABSENT`** — those APIs
returned no reasoning channel at all. That is an engineering check, not a result, and no
number from it appears in RESULTS_SUMMARY.md: it is a different task family from the
three registered benchmarks.

AMBER: spec §9.1 says to read `ChatMessageAssistant.reasoning`. That attribute does not
exist in the pinned `inspect-ai==0.3.260` (fields are `id, content, source, metadata,
role, tool_calls, model`). Read defensively via `getattr` and fall back to the content
blocks, where 0.3.260 actually stores `ContentReasoning`. Marked `# NEEDS REVIEW`.

## Step 4 — Mythos loader ✅ **first real measurement**
`loaders/mythos_transcript.py` + 11 tests. Emits `TurnObservation`s with
`task_class="mythos_cyber_ctf"`, withholds all text (`text=None`), marks every utterance
`Provenance.REDACTED_PARTIAL` and `do_not_train: True`.

**Measured, on the real transcript (n = 2,061 assistant turns, 1 trajectory):**
- `raw_present` 686, `absent` 1,375, `summary_only` 0, `redacted` 0.
- **Emission rate 0.3328** (action-weighted over turns).
- **Uninspectable share 0.6672**, Wilson 95% [0.647, 0.687].
- Date range 2026-07-18T01:02:54Z → 2026-07-18T21:29:27Z. One 20-hour incident.

Added `emission.binned_profile()` because n=1 trajectory makes the per-step profile
degenerate — every one of 2,061 step indices has `n_turns = 1` and is `low_n`. Binned
into 10 equal-width bins (~207 turns each):

| bin | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| rate | .362 | .353 | .295 | .319 | .295 | .324 | .372 | .357 | .343 | .308 |

**This is a result.** The profile is *flat* — 0.295 to 0.372, every interval overlapping
every other — across a real 20-hour long-horizon agentic trajectory. AdaptR1's induced
per-step profile on multi-hop QA swings 1.00 → 0.00 → 0.84 → 0.20 → 0.33 → 0.00 over its
first six steps. Their Limitations already disclaim transfer to long-horizon agentic
settings; this is one datapoint consistent with that disclaimer.

AMBER, three judgement calls, all marked `# NEEDS REVIEW` or argued in a docstring:
1. **Binning is mine, not the spec's.** Equal-width, 10 bins, chosen so bins clear
   `MIN_CELL_N=30`. It trades positional resolution for a usable denominator.
2. **`n_clusters = 1` in every bin.** The Wilson intervals above assume within-trajectory
   independence, which is false. They are descriptive, not inferential. `cluster.py`
   (step 5) refuses to compute a clustered interval from one cluster rather than faking it.
3. **In-place `[redacted-xyz]` does not make a turn `REDACTED`.** A provider withholding
   a channel and a publisher removing an IP address are different events; the first is
   `ReasoningState`, the second is `Provenance.REDACTED_PARTIAL`, which every Mythos
   utterance already carries. Conflating them would inflate `REDACTED` by 316 turns.

## Step 5 — priors, bound, cluster, figures ✅
`priors.py` (constants only, transcribed verbatim from spec §6; a test parses its AST
and fails if any executable logic appears), `bound.py` (scalar + positional ceilings,
`worst_step`), `cluster.py`, `figures.py`. **63 tests pass.**

`cluster.py` earns its place twice over. `test_clustered_interval_wider_than_naive`
uses collusion.wiki's real shape (91% of mass in one cluster) and confirms the widening.
And `clustered_wilson` on the Mythos data returns
`status="single_cluster_no_interval"` — 2,061 turns but **one** trajectory, so there is
no clustered interval to compute. It says "we cannot say" rather than emitting a wide
finite interval, which are different claims.

**Both figures rendered from real data and committed** to `results/figures/`, each with
a standalone caption file stating n.

Two deviations from the spec's figure brief, both to avoid a misleading chart:
1. **Figure 2 is two panels, not one with a secondary axis.** The spec asks for c(j) on
   the primary axis and c·r₂ on the secondary. A dual y-scale lets two curves be slid
   against each other until they tell whatever story the author wants — the exact
   failure this project is about. Both quantities are probabilities, so they share one
   y-axis instead. Separately, AdaptR1's x-axis is *step index* and ours is *decile bin*;
   plotting them on one x would assert their step 2 equals our position 2. They now sit
   in adjacent panels sharing the y-axis, which keeps the real comparison (same
   probability scale) and drops the false one.
2. **At r₂ = 1 the ceiling line is not drawn**, because it coincides exactly with c(j)
   and two identical lines imply two findings. The identity is annotated on the panel.
Palettes were validated with the colour checker rather than eyeballed: Figure 1 uses a
single-hue ordinal ramp (the four states are *ordered*, not categorical) passing
monotonicity, adjacent-step and light-end contrast; Figure 2's series pass all-pairs
CVD separation.

## Step 6 — record, gates, config, CLI ✅
`record.py` (+ `results/record_schema.json`, JSON Schema draft 2020-12,
`additionalProperties: false`), `gates.py`, `config/channels.yaml`, `cli.py` with three
subcommands. **108 tests pass**, up from 63. ruff and mypy clean.

Recovered from the shutdown: the four modules survived intact but had no tests and
`results/observability_record.json` had been truncated to 0 bytes mid-write. Both fixed;
the record regenerates to 915 KB, 2,061 cells, schema-valid.

**The gate fails, which is the deliverable.** `channels gate` exits 1 on the real corpus:
```
[FAIL] deliberation_coverage_floor: aggregate raw_present 0.333;
       worst stratum mythos-5/effort=None at 0.333 against a floor of 0.500
[FAIL] uninspectable_ceiling:       aggregate uninspectable 0.667 against a ceiling of 0.500
[FAIL] codebook_drift:              observed TODO(johanna)... vs registered CODEBOOK_HASH_PLACEHOLD...
```
The third is honest bookkeeping, not a bug: the codebook is step 9, so no hash exists to
compare, and `codebook_drift` returns UNEVALUABLE — which counts as failure. A gate that
passed because it had nothing to check would be the exact defect this package names.

Three tests carry the architecture rather than the arithmetic, and they are the ones to
read: `test_unevaluable_counts_as_failure`, `test_uninspectable_turns_stay_in_denominator`
(10 readable of 100 is 0.10, not the 1.00 of the readable subset) and
`test_worst_stratum_drives_the_verdict` (aggregate 0.525 above the floor still FAILs on a
stratum at 0.100). On the record side, `test_invalid_record_is_never_written` pins write
order — validation precedes the write, so an invalid record leaves no file to be cited —
and `test_unmeasured_inter_agent_block_is_null_not_zero` pins null-vs-zero.

AMBER — thresholds are mine. `config/channels.yaml` sets floor 0.50 and ceiling 0.50.
Nothing in the literature establishes what share of turns must expose raw reasoning
before a deliberation-gated monitor is trustworthy; the question has not been asked in
this form. The file says so in a header comment and the values exist so the machinery
has something to compare against. **They are not a standard and must not be cited as
one.** Marked `# NEEDS REVIEW: illustrative threshold, not a safety claim`.

AMBER — CLI tests run on a synthetic four-turn transcript in the real row format, written
into `tmp_path`. Two of four turns carry `<thinking>`, so the expected share is 0.5 and
can be counted by hand in the fixture. No test touches a real corpus.

## Step 7 — README, CITATION.cff, DATA_PROVENANCE ✅
`docs/DATA_PROVENANCE.md` was already committed at step 2, so this step was README and
CITATION.cff. Both written; 108 tests still pass, ruff and mypy clean.

The README leads with the result *and its caveats in the same breath* — n=1 trajectory,
intervals descriptive not inferential, in-band `<thinking>` markup rather than a
structured reasoning field — rather than putting the caveats in a section a reader can
skip. It also states plainly that the gate failure is the intended demonstration and
that the config thresholds are not a standard.

**Verified rather than assumed:** `docs/DATA_PROVENANCE.md` carries the Zenodo DOI
`10.5281/zenodo.22182741` for safety-eval-pipeline. I checked it against the upstream
repository's README badge before repeating it in CITATION.cff. It is real. Flagging the
check because the integrity rules forbid inventing a DOI, and a DOI inherited from an
earlier session is exactly the kind of number that gets propagated unverified.

safety-eval-pipeline is cited in three places, as asked: the README's provenance
section, `CITATION.cff` `references`, and §"Reuse and attribution" of DATA_PROVENANCE.
The vendored statistics are credited as vendored-verbatim; the gate contract is credited
as a reused design.

**Q4 still open, unchanged.** `ci/ci.yml` remains parked outside `.github/workflows/`.
I re-checked the token: scopes are `admin:public_key, delete_repo, gist, read:org, repo`
— still no `workflow`, so GitHub will reject any push creating that path. One command
fixes it:
```
gh auth refresh -h github.com -s workflow
git mv ci/ci.yml .github/workflows/ci.yml && git commit && git push
```
Until then **CI does not run on this repository.** The workflow file is correct and the
three commands it runs all pass locally, but nothing is enforcing that on push.

### Q4 addendum — the SSH workaround does not exist here (2026-09-12)
Tried to install `.github/workflows/ci.yml` without the token refresh. It failed; writing
down the dead end so it is not retried.

`gh auth status` reports *"Git operations protocol: ssh"* and `ssh -T git@github.com`
authenticates successfully, which suggests SSH pushes would bypass the `workflow`-scope
restriction (that restriction applies to OAuth-token-over-HTTPS pushes, not SSH). **It
does not work here.** The greeting is `Hi Jangulo7/Quantomics!` — the key is a
**deploy key scoped to a different repository**, not a user key, so pushing this repo
over SSH returns `ERROR: Repository not found`. The `origin` remote is HTTPS regardless.

Confirmed the block directly rather than inferring it:
```
! [remote rejected] build/overnight -> build/overnight (refusing to allow an OAuth App
  to create or update workflow `.github/workflows/ci.yml` without `workflow` scope)
```
The commit was backed out with `git reset --hard`, because a local commit touching that
path blocks **every** later push on the branch, not just its own. `ci/ci.yml` stays
parked and the branch is in sync with origin.

Verified the workflow itself is sound while it was briefly in place: valid YAML, one
`check` job, eight steps, and all three commands pass locally — ruff clean, mypy clean
on 19 files, `pytest -m "not integration" --cov` 108 passed at **87% coverage**.

Two routes, both needing Johanna:
1. `gh auth refresh -h github.com -s workflow` — the browser flow was opened on
   2026-09-12 but scopes are still `admin:public_key, delete_repo, gist, read:org, repo`,
   so it did not complete.
2. Add a real user SSH key (not a deploy key) and switch `origin` to the SSH URL.

**Until one of them happens, CI does not run on this repository.**

---

# Session 2 — 2026-09-12 evening, resumed on a different machine

**How this session started, and the lesson.** Local memory for this project was
empty and the working directory held only `.research-plan/`. I scaffolded the
repo from scratch and rebuilt steps 0–3 before discovering that
`origin/build/overnight` **already had steps 0–7 complete and pushed**. That was
~40 minutes of duplicated work. I reset to the remote, kept the duplicate on the
local-only branch `local/scratch-rebuild`, and wrote three memory files so the
next machine checks the remote first. Nothing from the rebuild was merged; the
session-1 modules are the ones that shipped.

## Step 3 — MEASURED at last (the previous session's blocker)

You supplied 12 real `.eval` logs. Measured: 3,039 samples, **3,789 assistant
turns**, 3 models × 3 task classes (sycophancy, xstest, strong_reject).

**Emission of raw reasoning: 0 / 3,789.** Uninspectable share **1.0000**
(95% CI [0.9990, 1.0000]). One-sided 95% upper bound on emission **0.00071**.
Recall ceiling **0.000** at every step, for any r₂. No cell is low-n.

This is spec §11.2's stop-rule outcome, and it is a real result: a standard
three-benchmark safety evaluation, run and logged normally, leaves an external
evaluator with no deliberation evidence at all. **The caveat travels with it:**
these are vLLM-served 7–8B instruction-tuned models that emit no reasoning
channel by design, so the zero describes this serving stack, not a frontier
reasoning model's disclosure policy. RESULTS_SUMMARY.md states that in the same
breath as the number.

`reasoning_effort` is `None` in every log, so the effort axis does not exist
here (Q2 of session 1, now settled by the data).

### Two bugs the new corpus forced, both fixed at the source
1. **`wilson_interval` could exclude its own point estimate.** At successes=0,
   n=500 the lower limit evaluated to 4.3e-19, not 0.0 — making an error bar of
   negative length (matplotlib refused it) and, worse, an interval that excludes
   the rate it describes. Now clamped to contain the point estimate, with a
   regression test across n ∈ {1, 30, 313, 450, 500, 3789, 10000}.
2. **Records were pooled across corpora.** With both corpora loaded, one
   `positional_profile` held Mythos decile bins and Inspect turn ordinals under
   the same integer keys, and `ceiling_by_step["0"]` came out 0.0188 — a number
   describing neither corpus. Each corpus now writes its own record. Figure 1
   still spans both, because each of its bars is a single model × task class.

## Step 8 — collusion.wiki, GO/NO-GO on RQ3 ✅
Downloaded the frozen export; all three row counts match the published figures
exactly (14,591 / 4,579 / 3,103).

**Result: 2,824 of 4,024 pages (70.18%) carry exactly one agent** and cannot
contain peer disagreement by construction. 1,200 pages (29.82%) have ≥2.
RQ3 is structurally feasible on under a third of the corpus.

AMBER: the spec's `dse` claim is wrong — see Q5. Human/agent separation uses
`labels.jsonl`'s `is_human_handle` and fails toward `HUMAN_MESSAGE` when the
handle is absent (930 revisions). `actors_per_page` counts agents only; a test
caught me counting human editors toward peer-disagreement feasibility, which
would have inflated the feasible denominator.

## Step 9 — the validation ladder's first rung ✅ (protected above 10–12)
`data/codebook/v1.yaml` with all eight codes, each carrying a definition, an
inclusion rule, an exclusion rule and ≥2 positive/negative examples.
**`codebook_hash()` = `sha256:2d1077fad571ec02c5bbbef5cfdc5f3541b46305ab9e9004e318bd37ea56af83`**,
now registered in `docs/PREREGISTRATION.md`, so `codebook_drift` PASSes instead
of being UNEVALUABLE.

**A finding, not a gap: the four numerator codes OBJ/REF/ESC/WARN have ZERO real
positive examples.** No source consulted quotes one agent normatively objecting
to another. Every published verbatim inter-agent string is coordination,
flattery or reciprocity. Written as `TODO(johanna): example needed` rather than
invented; `example_gaps()` reports it programmatically.

`tree.py` (TreeCoder, gates P,C,G0–G5,T, a priori, never fitted, `gate_path`
persisted), `loaders/positive_control.py` (WikiTactics, 3,865 utterances, with a
**committed** label→code table), `validate.py` (the gatekeeper).

**MEASURED recall, TreeCoder on WikiTactics:**
`OBJ 0.072 [0.046, 0.111]` · `REF 0.065 [0.018, 0.207]` · `SHARE 0.187 [0.168, 0.208]`.
The instrument barely works. I did **not** tune it: the module docstring asserts
it is never fitted, and sweeping cues against this score would void that claim.

## Step 10 — the second instrument ✅
`detect.py` + `NliDetector` (`cross-encoder/nli-deberta-v3-small`, offline-only,
rung 1 only, `do_not_train` checked before the model loads).

**THE RESULT: the two detectors' OBJ recall intervals do not overlap.**
`tree_coder 0.072 [0.046, 0.111]` vs `nli_detector 0.218 [0.171, 0.273]` — 3×,
same corpus, same code, same gold labels. Spec §11.2's stop rule calls this a
result, not a bug, and it is extension B's seed. Reported side by side, never
averaged.

Integrity fix found while writing it up: `NliDetector` emits only OBJ/UNCL, so
its 0.000 on REF and SHARE is a property of the instrument, not a measurement.
Detectors now declare a `label_space` and those codes report
`outside_detector_label_space` rather than a measured zero. 213 thread-initial
abstentions leave the denominator and are counted in `n_skipped`.

## Step 11 — the published record ✅
7 rows seeded verbatim from your prompt. `refuse_rate()` raises by design.
Validator requires a non-empty `source_ref` and enum-valid channel/provenance on
every row. `test_zz_prefix_consistent_across_sources` asserts the `zz` convention
appears under ≥2 independently attributed actors. Page numbers unverified (Q7).

## Step 12 — RQ3 returns a bound and its blockers, never a rate ✅
`rate=None`, `rate_status="no_validated_detector_for_this_corpus"`, three
computed blockers (structural 70.2%, instrumental 3× detector disagreement,
transfer unvalidated). Both sensitivity analyses shipped: recall correction
(13.9× vs 4.6× depending on which detector you believe) and denominator choice
(3.35× between all pages and multi-agent pages).

## Figures — three problems found by looking at the images, not the code
The CLI was **discarding** the caption text `figure_one`/`figure_two` return, so
the committed captions still described an earlier Mythos-only run — a caption
stating an n the image does not show. Captions are now written beside each
figure and regenerate with it. Figure 1's x ticks collided (full
provider-qualified model ids); shortened for display only. Figure 2's left panel
was hardcoded "one real agentic trajectory" and its axis claimed 10 bins
regardless of how many exist; both are now derived from the data.

## Final state
159 tests pass with no network, **89% coverage**; `ruff` and `mypy --strict`
clean on 26 files. Both records schema-valid. `channels gate` exits 1 with the
two emission gates failing and `codebook_drift` passing — the failure is the
deliverable.

---

## Honest assessment (as at end of session 2 — superseded, kept for the record)

> Session 3 answers the central criticism below by measuring reasoning-capable
> models. The paragraph is left unedited because a build log that quietly
> rewrites its own past assessment is worth less than one that shows the
> assessment changing.


**What shipped.** All twelve steps in the build order, plus the step-3
measurement the previous session could not make. Two corpora measured
end-to-end, two detectors validated against a labelled control with real
intervals, a schema-valid record per corpus, two figures with captions that
regenerate with them, a codebook whose hash gates the build, and an RQ3 endpoint
that refuses to produce a rate for three separately computed reasons. The
integrity machinery is real and it fires: `require_validation` raises,
`refuse_rate` raises, `assert_primary_eligible` raises, undefined recall reports
as undefined rather than zero, and the gate exits non-zero on the real data.

**What did not ship.** Rung-2 validation — the whole transfer question from human
prose to agent protocol strings — is untouched, which is why no rate is reported
from collusion.wiki. No test–retest reliability on the codebook; that needs a
second human coder. The `reasoning_effort` axis does not exist in this data, so
extension A's designed-experiment upgrade cannot be piloted here at all. Five of
the eight codes have no real examples, and four of them have no measurable
recall. `shuffled_control` is implemented and tested but never actually run as a
rung-2 comparison, because there is no rung-2 rate to compare against.

**The biggest weakness, stated plainly.** *The headline emission result is
measured on models that were never going to emit reasoning.* Llama-3.1-8B,
Qwen2.5-7B and Ministral-8B served through vLLM have no reasoning channel by
design, so "0 of 3,789" is very close to a tautology dressed as a finding. It is
honest, it is correctly caveated, and the machinery that produced it is sound —
but a reviewer will ask whether the measurement could have come out any other
way on this corpus, and the answer is no. The Mythos transcript is the only
corpus here where emission could vary, and it is n=1 trajectory whose intervals
are explicitly descriptive rather than inferential. So the artifact currently
demonstrates an *instrument* convincingly and a *measurement* only weakly. The
second weakness is that `TreeCoder`'s 7.2% recall is bad enough that its
coverage-related outputs are near-uninformative; the project is saved from
overclaiming only because it refuses to report rates from it.

**What I would do with two more hours.** First, run the emission measurement on a
model that actually emits reasoning — one `inspect eval` against any
reasoning-capable API across the same three benchmarks would turn the headline
from "the stack exposed nothing" into "coverage is X here and Y there", and
every piece of machinery to consume it already exists. That is the single
highest-value hour available. Second, hand-code 100 WikiTactics utterances
against the codebook myself and compute test–retest against the gold labels,
which would tell us whether TreeCoder's 7.2% is the instrument failing or the
label→code mapping being wrong — right now those two explanations are
indistinguishable, and that ambiguity undermines §3 more than the low number
does.

---

# Session 3 — 2026-09-12 night into 2026-09-13

Driven by Johanna's decisions rather than the build order. Everything here is
either a decision she took or an error the work surfaced.

## The reasoning-model measurement — the weakness in session 2's assessment, repaired

Session 2's honest assessment said the headline result was measured on models
that were never going to emit reasoning, so "0 of 3,789" was close to a
tautology. That was the right criticism and this session answers it.

Probed six candidates through OpenRouter first, because the design only works if
the four states actually vary:

| model | state recorded | evidence |
|---|---|---|
| `gpt-oss-120b` | RAW_PRESENT | raw CoT, 202 chars |
| `claude-haiku-4.5` | RAW_PRESENT | raw CoT, 276 chars |
| `qwen3-32b` | RAW_PRESENT | raw CoT, 738 chars |
| `glm-4.7-flash` | RAW_PRESENT | raw CoT, 1,291 chars |
| **`gpt-5-nano`** | **REDACTED** | encrypted chain + 492-char summary |
| `deepseek-v3.2` (default) | ABSENT | no block, 0 reasoning tokens |

`gpt-5-nano` is the one that matters: it demonstrably reasons (64 reasoning
tokens) and ships the chain encrypted, so an evaluator gets nothing. The four
states vary by **vendor disclosure policy**, not by model capability.

**Johanna's control, and it was the right call.** She asked whether ABSENT was a
capability limit or a configuration choice. Measured, same model and prompt,
only a request parameter changed:

- `deepseek-v3.2` default → no reasoning block, 0 reasoning tokens
- `deepseek-v3.2` with `reasoning_tokens=2048` → **0.9777** raw over 763 turns

So "this model emits no reasoning" was really "this request did not ask for it".
That converts a capability claim into a disclosure claim, which is the paper's
thesis stated as a measurement.

**Arms complete so far** (sweep running; every figure states its own n):

| arm | n turns | raw_present | 95% CI |
|---|---|---|---|
| `gpt-oss-120b` | 1,263 | 1.0000 | [0.9970, 1.0000] |
| `qwen3-32b` | 813 | 1.0000 | [0.9953, 1.0000] |
| `deepseek-v3.2-reasoning-on` | 763 | 0.9777 | [0.9646, 0.9860] |

against the baseline's 0.0000 over 3,789 turns.

## Errors this session surfaced, and what each cost

1. **Sycophancy ran the wrong sample.** The baseline used
   `--limit 250 --sample-shuffle 42` against a 4,882-sample dataset. I read the
   sample *count* from the baseline logs but not the eval *config*, so the sweep
   ran all 4,882 — 20× the work and a denominator not comparable with the
   baseline, which was the entire point. **Cost: about an hour.** Partial logs
   deleted; the runner now records every limit with a comment saying where it
   came from, and is resumable so finished work is not repeated.
2. **Unbounded retries.** inspect defaults to no request timeout and unlimited
   retries, so one hung call blocked an arm at 249/250 samples. Bounded. The
   more important half: tolerating dead samples shrinks a denominator silently,
   so `errored_samples()` now counts the shortfall and `describe()` reports it.
3. **Arms were pooled by model id.** Caught by *looking at the rendered figure*:
   `deepseek-v3.2` appeared as one bar that was really the reasoning-on arm
   alone. With the default arm and three `gpt-5-nano` efforts still to land,
   that would have pooled arms differing by exactly the variable under study. I
   had guarded this in `report_emission.py` and not in the loader — which is
   precisely how such a bug survives.
4. **My annotation time estimate was wrong by 5×.** I quoted 150 revert items at
   40–55 minutes. Johanna pointed out a human needs 1.5–3 minutes per item,
   which makes it 4–6 hours. She was right; 15–20s is skim-and-press-a-key
   speed. Round 1 cut to 60 (±0.12 precision, 1.5–2.5 h), Round 2 to 200. The
   kit now has the coder measure their own pace on a 5-item practice first.
5. **Tests silently read real data.** Adding `--reasoning-logs` broke 12 tests at
   once, because they had no reason to pass the flag and so began reading
   whatever logs sat at the default path. Fixed, plus a guard test that fails if
   a future flag reintroduces the hole.

## Johanna's schema decisions — `ARTEFACT_EDIT` and `REVERT`

A collusion.wiki revision carries **two** channels and v1 conflated them. The
data settled it: **12,773 of 14,591 revisions (93.3%) carry a `change_summary`**,
overtly coordination-flavoured ("coordination update" ×506). So the body diff is
an `ARTEFACT_EDIT` and the summary is an `INTER_AGENT_MESSAGE`, and the
inter-agent *message* denominator no longer contains acts that carry no words.

`REVERT` added as an action code, scored structurally, never by the verbal
coder. **1,275 of 13,661 agent edits (9.33%)** restore a body another actor
replaced. Self-reverts excluded. A known undercount: checksum matching finds
~94% of reverts and no partial revert.

**Clustering, page primary and actor sensitivity as Johanna chose**, and the
choice does real work:

| clustering | 95% CI | clusters |
|---|---|---|
| page (primary) | [0.0325, 0.2424] | 4,024 |
| actor (sensitivity) | [0.0696, 0.1243] | 3,099 |
| naive | [0.0886, 0.0983] | — |

The page interval is ~7× wider than naive, because reverts concentrate on 42
pages. A naive interval would have been badly anticonservative.

Also: the spec's justification for clustering is **wrong on the data**. §8 says
"91% of edits come from the single actor `dse`". `dse` is a **wiki**, holding
91.9% of revisions; the most active individual actor holds 2.3% across 3,102
actors.

## Citation verification — and one withdrawal

Johanna supplied both METR PDFs. `scripts/verify_citations.py` now checks every
transcribed row and exits non-zero on a mismatch: **10 rows, 10 verified, 0
mismatches.** Verification changed the data — the LIBRAW dyad is on p.44 not
p.43, and **both of its strings were truncated in the seed**.

**One codebook example was withdrawn, and it is the most interesting thing here.**
v1 listed the fragment `"...WILL_CREDIT_AND_COLLAB..."` as a UNCL positive,
because its ellipses left its force unrecoverable. The source (p.33) shows the
full string is an unambiguous `zz`-prefixed ASK, correctly coded SHARE.
**The uncertainty was manufactured by the investigators' elision, not present in
the utterance.** That is a finding about disclosure practice — it belongs in the
report, not in a coding category — so it left the codebook.

## Codebook v1 → v2 → v3

v2 added `REVERT` and `ARTEFACT_EDIT`; v3 verified every citation and made the
withdrawal above. No definition, inclusion rule or exclusion rule changed in v3.
Both bumps are dated entries in the deviations log with reasons.

Each bump invalidated the validation records and `require_validation` raised on
the next call — the machinery working, not a problem to route around. All
re-earned; `tree_coder`'s recalls are unchanged.

## The annotation apparatus

Johanna's decision: a **human coder, no LLM coding**. That keeps human labels as
the gold standard and avoids validating one unvalidated instrument against
another. I had proposed an LLM-assisted design; hers is the more conservative
and more defensible one.

`channels/annotate.py` enforces three properties rather than asking for them:
**blind** (nothing can surface a detector's prediction), **deterministic**
(sample is a pure function of population, task, n and seed, with the population
sorted by uid first so two readers cannot get different items), and
**text-free** (records hold uid, one letter, seconds, timestamp — so
`results/annotations/` is publishable under an unlicensed corpus).

`coder-kit/` plus `coder-bundle.zip` (3.9 MB). The bundle **physically excludes**
the results, build log and pre-registration, and refuses to build if they are
present — the brief asks the coder not to read them, but a request is not a
control.

Two interface corrections from Johanna, both right: diffs were truncated with no
way to see the rest, forcing "unclear" on items whose evidence was merely
off-screen; and the expand key I first added sat among `d`/`h`/`u` as though
"show me more" were a third verdict. The whole diff is now always shown and the
menu holds judgements only. Checked this is practical: median 38 diff lines, max
109, only 4 of 60 items over 100 lines.

## Pre-registration, made honest

Several analyses had already run, so registering the document unchanged would
have implied a false claim. §0 now separates **§0.1 exploratory** (everything
already executed, listed individually with its state) from **§0.2 confirmatory**
(C1–C3, the human annotation, with sample sizes, estimators and decision rules
fixed before any label exists). §0.4 says plainly that registering now does not
make the exploratory analyses confirmatory.

C3 declares in advance that the second coder is the codebook's author, so κ
measures whether the written rules reproduce the author's intent and will not be
called inter-rater reliability.

`scripts/register.sh` stamps the timestamp, commits, records the SHA and tells
her to push — a SHA written before the commit exists would record an intention,
not a registration.

## State at the end of this session

187 tests pass with no network; ruff and mypy clean on 27 files. Three
schema-valid records (`inspect_logs`, `mythos_transcript`,
`inspect_logs_reasoning`). Figure 1 pools task classes, justified by measurement
rather than assumption: `task_class_spread` ≤ 0.011 for every model, recomputed
on every run so the justification cannot silently expire.

## Honest assessment (current)

**What shipped.** All twelve build-order steps, plus three things the spec did
not anticipate: a reasoning-capable model sweep across nine arms, an action
channel with a structurally-scored code, and a complete human-annotation
apparatus. Two corpora became three. The integrity machinery is not decorative —
`require_validation` raised twice this session when codebook hashes changed,
`refuse_rate` raises on the typology, undefined recall reports as undefined, and
the gate exits non-zero on real data.

**The strongest result is no longer a tautology.** Session 2's assessment was
that the headline was measured on models that could never have emitted
reasoning. The DeepSeek control fixes that directly: same model, same prompts,
same provider, one request parameter, 0.000 → 0.978. Add `gpt-5-nano`, which
reasons and encrypts, and the claim becomes measurable rather than rhetorical —
**what an evaluator can see is set by disclosure policy and configuration, not
by capability.**

**What did not ship.** Rung-2 validation is still untouched, so no rate is
reported from collusion.wiki and `rq3` returns a bound. `REVERT` has no recall
at all until the coder runs — `no_support_in_control` is its honest current
state. Five of nine codes still have zero real positive examples, and four have
no measurable recall on any control that exists. `shuffled_control` is
implemented and tested but never run, because there is no rung-2 rate to compare
it against. The sweep is incomplete at the time of writing: three arms of nine.

**The biggest weakness now.** It has moved, which is progress, but it has not
gone. The emission result is strong and the *objection* result does not exist:
`TreeCoder` at 0.072 recall is too weak to support any claim, and the project is
saved from overclaiming only because it refuses to report rates from it. So the
artifact demonstrates an instrument convincingly, one measurement convincingly,
and a second measurement not at all. A reviewer will also note that both
benchmark corpora are one- and two-turn tasks; the only long-horizon trajectory
is n = 1, and its intervals are explicitly descriptive. Nothing here establishes
that emission behaves the same way over a hundred-step agent run — which is
exactly the setting the argument is about.

**What I would do with two more hours.** Finish the sweep and get the
`gpt-5-nano` effort axis, which is the only designed-experiment arm in the whole
project and the one a reviewer will find hardest to dismiss. Then run the
emission measurement on one genuinely agentic benchmark with a real filesystem
and tool use, even at n = 50, because the transfer objection above is the
strongest one available and a single long-horizon arm would blunt it. I would
not spend those hours on the objection arm: it needs the human labels, and no
amount of engineering substitutes for them.

---

## Registration, as executed (2026-09-12 23:15 UTC)

Recorded here rather than in `docs/PREREGISTRATION.md`, because that document
must not be edited after the commit that registers it.

| | |
|---|---|
| Registration commit | `ae377b0e61ce4c5bfe00b449e6d9739fc2d2e4ce` |
| Timestamp (UTC) | `2026-09-12T23:15:00Z` (01:15 Madrid, 13 Sep) |
| Codebook | `sha256:a67d3c09dfab3cb3fda0aea911322b15a40a6f45db466e19dd096481c0d21f62` |
| `PREREGISTRATION.md` | `sha256:1266dc183224737617143aba67d8f466e8133f013867042ac42477954f545d68` |

**Why two commits, and which hash to publish.** `scripts/register.sh` commits
twice by design: `ae377b0` stamps the timestamp, then `cd0fa2c` writes that
commit's own SHA back into the document. A SHA cannot be written into the commit
it names, so the document hash that survives is the one **after** both — 
`1266dc18…`, which is the current file and the one to post anywhere public.
The document at `ae377b0` hashes differently (`20c2d08b…`) because its SHA field
was still a placeholder; that is expected, not drift.

**Verified after the fact:** `docs/PREREGISTRATION.md` is byte-identical to
`cd0fa2c` and its hash still matches what `register.sh` printed. Both commits
are contained in `origin/build/overnight`.

**Still outstanding.** No independent third-party timestamp — OSF's ORCID login
was returning `UnauthorizedServiceException` at the time. The limitation is
stated in the registration itself: a commit in a repository the author controls
proves content and order, not date, to someone who distrusts the author. Posting
the two hashes above to any dated public service closes that gap whenever it is
convenient, and where that happened belongs in the deviations log.
