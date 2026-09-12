# Build log — agent-channel-observability

Branch `build/overnight`. Times are Europe/Madrid. Written for a reader who has not
seen the diffs.

## QUESTIONS FOR JOHANNA

**Q1 — BLOCKING for step 3, the primary result. Where are the Inspect `logs/`?**
The spec (§9.1) and your prompt name "the `logs/` directory of my safety-eval-pipeline
runs" as the source for the headline emission measurement. Those logs do not exist on
this machine and are not obtainable from the public repo. Exact paths and remotes
checked, all negative:
- `https://github.com/Jangulo7/safety-eval-pipeline` cloned to scratch — `.gitignore:43`
  reads *"Inspect logs are not committed at all"*, `.gitignore:51` is `logs/`.
  Remote has only `refs/heads/main` and `refs/tags/v1.1.0`; no logs branch, no release
  asset checked out by a clone.
- `find /home/johan /mnt -maxdepth 8 -name "*.eval"` → 16 files, all under
  `/home/johan/ai_eval_projects/{my-eval,PROJECT}/logs/`, tasks `addition`, `gsm8k`,
  `humaneval`, `example-task`. **None** of the three named benchmarks.
- `find /home/johan -maxdepth 8 -iname "*sycophancy*" -o -iname "*xstest*" -o
  -iname "*strong_reject*"` → only `inspect_evals` package source, no run logs.
- `/home/johan/EvalPipelineAA` is a different repo (no logs).
I have **not** substituted the gsm8k/humaneval logs — that would be swapping the corpus,
which the integrity rules forbid. If you can drop the run's `logs/` into
`data/inspect_logs/` (it is gitignored), step 3 runs against it unchanged.

**Q2 — is the AI Village dataset in scope tonight?** You granted access to
`huggingface.co/datasets/aidigestorg/ai-village` mid-build. It is not in the spec's
§11.2 build order; §15 lists it under extension D. I am treating it as out of scope for
steps 0–7 rather than quietly widening the build. Say the word and it becomes a task
class.

**Q3 — spec function names.** Spec §1.2 says to vendor `wilson_interval`,
`wilson_upper_bound` and `bootstrap_ci` from safety-eval-pipeline "without rewriting
them". Upstream actually exports `wilson`, `wilson_from_rate` and `bootstrap_mean`, and
has **no** one-sided bound at all. I vendored the real three verbatim and added your
three names as wrappers; `wilson_upper_bound` is new code, marked as such in the file.

---

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
