# Results summary

Numbers as produced by the committed code, formatted for pasting into a paper.
Generated from `results/observability_record.json` at commit `89f4de5`, build
`build/overnight`, 2026-09-12.

**Every number below comes from one corpus and one trajectory.** Read §0 before quoting
any of them.

---

## 0. The caveat that travels with every number here

The entire results table rests on the Mythos 5 incident transcript: **one incident, one
model, one trajectory**. `n = 2,061` is a count of assistant *turns*, not of independent
samples. The number of clusters is **1**.

Consequently:

- Every Wilson interval in this document assumes within-trajectory independence, which
  is false. **They are descriptive, not inferential.** They describe the spread of one
  trajectory; they do not support inference to mythos-5 in general.
- `cluster.py` was asked for a clustering-corrected interval on this data and returned
  `status = "single_cluster_no_interval"` rather than a number. With one cluster the
  effective sample size collapses to 1. "We cannot say" and "we can say very little" are
  different claims and the code refuses to conflate them.
- The intended three-model × three-benchmark measurement did not run. See §7.

Reasoning in this corpus is in-band `<thinking>…</thinking>` markup inside a content
string, **not a structured field**. "The transcript contains reasoning" and "the
transcript exposes a reasoning field an evaluator could read programmatically" are
different claims; only the first is true here.

---

## 1. Emission by reasoning-channel state

Denominator: **assistant turns that OCCURRED**. Turns that never happened because a
trajectory ended earlier are not in the denominator and are not counted as absent.

Corpus `mythos_transcript` · model `mythos-5` · task class `mythos_cyber_ctf`
· `n = 2,061` assistant turns · 1 trajectory
· window 2026-07-18T01:02:54Z → 2026-07-18T21:29:27Z (20.4 h)
· SHA-256 `6f2a5a50b53640bd779a198cef8a620f2d6e2bbaaf4a0dea9edac87a69fc3e4b`

| state | count | share | 95% CI (Wilson, descriptive) |
|---|---:|---:|---|
| `raw_present` | 686 | **0.3328** | [0.3128, 0.3535] |
| `summary_only` | 0 | 0.0000 | — |
| `redacted` | 0 | 0.0000 | — |
| `absent` | 1,375 | 0.6672 | [0.6465, 0.6872] |

**Uninspectable share** (`summary_only + redacted + absent`) = **0.6672**,
95% CI [0.6465, 0.6872], n = 2,061.

Clustering-corrected interval: **not available** — `single_cluster_no_interval`, 1
cluster.

Two notes on what is *not* in this table:

- `summary_only = 0` and `redacted = 0` are real zeroes for this corpus, not missing
  data. Anthropic's whole-message redactions are *absent from the file entirely* (the
  observed index range is 82–2144), so they cannot appear as a state. In-place
  `[redacted-xyz]` token substitution affects 316 assistant messages but is a publisher
  removing an identifier, not a provider withholding a channel; conflating the two would
  inflate `redacted` by 316 turns. See BUILD_LOG step 4, AMBER item 3.
- The 0.667 `absent` share is dominated by tool-result messages, which carry no
  `content` field at all (1,361 of them). That is the honest reading: at those turns the
  agent's reasoning was not observable.

### Emission by model × task class × step index

**Reported here as a single aggregate row, because the per-step table is degenerate.**
`build_cells` produced **2,061 cells, one per step index, each with `n_turns = 1`**, and
**all 2,061 are flagged `low_n`** (threshold `MIN_CELL_N = 30`). Every cell is therefore
below the reporting threshold and none is quotable on its own. The full 2,061-row table
is in `results/observability_record.json` under `emission.cells` for completeness; it is
not reproduced here because a table in which every row is marked low-n is not a table.

| model | task class | reasoning effort | step index | n | raw_present | 95% CI | low-n |
|---|---|---|---|---:|---:|---|---|
| mythos-5 | mythos_cyber_ctf | *not available* | pooled | 2,061 | 0.3328 | [0.3128, 0.3535] | no |

**`reasoning_effort` is `null` throughout, and no breakdown by it exists.** The Mythos
transcript rows carry no effort field. Per the build instructions, emission is reported
by task class and step index only; no second axis was invented.

---

## 2. Positional profile

The per-step profile being degenerate (§1), step indices were binned into **10
equal-width bins** of ~207 turns so each bin clears `MIN_CELL_N = 30`.

**AMBER — the binning is a build decision, not a spec requirement.** It trades
positional resolution for a usable denominator. Bin boundaries are equal-width over step
index, not equal-frequency.

| bin | n | c(j) raw_present | 95% CI (descriptive) | low-n |
|---:|---:|---:|---|---|
| 0 | 207 | 0.3623 | [0.2999, 0.4298] | no |
| 1 | 207 | 0.3527 | [0.2908, 0.4199] | no |
| 2 | 207 | **0.2947** | [0.2368, 0.3601] | no |
| 3 | 207 | 0.3188 | [0.2592, 0.3851] | no |
| 4 | 207 | 0.2947 | [0.2368, 0.3601] | no |
| 5 | 207 | 0.3237 | [0.2636, 0.3901] | no |
| 6 | 207 | **0.3720** | [0.3090, 0.4396] | no |
| 7 | 207 | 0.3575 | [0.2953, 0.4248] | no |
| 8 | 207 | 0.3430 | [0.2817, 0.4100] | no |
| 9 | 198 | 0.3081 | [0.2479, 0.3755] | no |

No bin is low-n. Range **0.2947 – 0.3720**; **every interval overlaps every other
interval**.

**Finding: the profile is flat.** Across a real 20-hour long-horizon agentic trajectory,
reasoning-channel emission shows no detectable positional structure. For contrast,
AdaptR1's induced per-step no-think ratio on multi-hop QA (arXiv:2605.31062, Table 4,
MuSiQue, λ=0.9) swings 1.00 → 0.00 → 0.84 → 0.20 → 0.33 → 0.00 across its first six
steps. That profile is **induced** by an RL reward that pays for first-step no-think and
is manipulable across its full range by the λ term — and their Limitations already
decline to claim transfer to long-horizon agentic settings. This is one datapoint
consistent with that disclaimer. It is one trajectory and does not refute anything.

---

## 3. Recall ceiling

`ceiling = c(j) · r₂`, where `c(j)` is measured positional coverage and `r₂` is the
recall of the second stage. Reported at **r₂ = 1.0**, a perfect second stage, which
makes every figure below an **upper bound on an upper bound**.

| quantity | value |
|---|---:|
| Ceiling at mean coverage | **0.3327** |
| Ceiling at the weakest position (bin 2) | **0.2947** |
| Worst position | bin 2 |

At r₂ = 1 the ceiling equals coverage by construction; the table is stated anyway so the
identity is explicit rather than implied.

**Reading.** A monitor gated on deliberation — one that only fires when it can read the
model's reasoning — cannot exceed **0.333 recall** averaged over this trajectory, and
cannot exceed **0.295 recall** against an action taken at the trajectory's weakest
position, *no matter how good its second stage is*. This bound applies only to
deliberation-gated detectors. METR reports that no-reasoning agents are "not obviously
less monitorable", so action-only evidence can suffice and this is not a bound on
monitoring in general.

Per-bin ceilings at r₂ = 1 are numerically identical to the c(j) column in §2. Full
`ceiling_by_step` is in the record under `bound.ceiling_by_step`.

---

## 4. Validation recalls

**NOT MEASURED — step 9 did not run.**

No detector in this repository has a recorded validated recall, and therefore **no rate
is reported from any corpus by any detector**. That is the first architectural rule
operating as designed, not an omission:

| instrument | rung | recall | status |
|---|---|---|---|
| TreeCoder detector | 1 (WikiTactics) | — | **not built** (step 9) |
| NliDetector | 1 (WikiTactics) | — | **not built** (step 10) |
| Codebook `data/codebook/v1.yaml` | — | — | **not written** (step 9) |

`codebook_hash` in the record reads `TODO(johanna): codebook YAML not written`, and the
`codebook_drift` gate returns `UNEVALUABLE` — which counts as failure. There is nothing
to compare a hash against, so the gate refuses to pass rather than reporting "no drift
detected".

---

## 5. collusion.wiki actors-per-page distribution

**NOT COMPUTED — step 8 did not run.** `loaders/collusion_wiki.py` does not exist, so
there is no tested instrument that produces this distribution, and none was computed
ad hoc for this document.

What *is* established, from the publisher's own `manifest.json` verified against its
`SHA256SUMS` at step 2 (all five files `OK`):

| quantity | value | source |
|---|---:|---|
| Pages (write-date cut ≥ 2026-05-01) | 4,579 | `manifest.counts.pages` |
| Revisions | 14,591 | `manifest.counts.revisions` |
| Labels | 3,103 | `manifest.counts.labels` |
| Revisions on the single wiki `dse` | 13,403 (**91.9%**) | `manifest.per_wiki.dse` |
| Pages on `dse` | 3,908 (85.3%) | `manifest.per_wiki.dse` |

That 91.9% concentration is **revisions per wiki, not actors per page** — a different
quantity, reported here only so the number is not mistaken for the missing one. It does
establish that per-observation independence is false for this corpus, which is why
`cluster.py` exists.

The RQ3 GO/NO-GO decision this step was meant to produce **has not been made**.

---

## 6. Gate status

`channels gate` exits **1** on the committed data. This is the intended demonstration.

| gate | threshold | observed | worst stratum | status |
|---|---:|---:|---|---|
| `deliberation_coverage_floor` | ≥ 0.50 | 0.333 | `mythos-5/effort=None` @ 0.333 | **FAIL** |
| `uninspectable_ceiling` | ≤ 0.50 | 0.667 | `mythos-5/effort=None` @ 0.667 | **FAIL** |
| `codebook_drift` | hash match | — | — | **UNEVALUABLE → FAIL** |

> **The 0.50 floor and 0.50 ceiling are illustrative defaults, not safety standards.**
> Nothing in the literature establishes what share of an agent's turns must expose raw
> reasoning before a deliberation-gated monitor is trustworthy, because the question has
> not been asked in this form. They exist so the gate machinery has something to compare
> against. **Do not cite them as a threshold.**

---

## 7. Numbers that do not exist, and why

Stated explicitly rather than omitted.

| intended result | status | reason |
|---|---|---|
| Emission across 3 models × 3 benchmarks | **not measured** | The Inspect `.eval` logs are not on the build machine. `results/published/results.json` from run `run-20260830-193016` is public but is pre-aggregated — 12 cells of rates and CIs, zero occurrences of `messages`, `content`, `reasoning` or `output`. A per-turn channel state cannot be recovered from a per-cell rate. No substitute corpus was used; `addition`/`gsm8k`/`humaneval` logs on the machine were deliberately not analysed. |
| Emission by `reasoning_effort` | **not measured** | No effort field in the corpus. No second axis invented. |
| Clustering-corrected interval | **refused** | 1 cluster. `single_cluster_no_interval`. |
| Detector recalls (TreeCoder, NLI) | **not measured** | Steps 9–10 did not run. |
| Inter-agent channel rate | **not measured** | Step 8 did not run. Recorded in the JSON as `rate_per_1000: null` with `rate_status: "no_denominator"` — null, not 0. A 0 would claim a measurement was made and came back empty. |
| `messages_authenticated` | **null by finding** | No corpus this project reads carries an authenticated sender field. The null is the adversarial-channel result, not a gap. |
| collusion.wiki actors-per-page | **not computed** | Step 8 did not run. |
| Published incident record rows | **not transcribed** | Step 11 did not run. |

---

## 8. Figures

Both in `results/figures/`, committed, each with a standalone caption file stating n.

- `figure1_emission_states.png` — four-state distribution, n = 2,061, Wilson error bars.
- `figure2_recall_ceiling.png` — measured c(j) and the ceiling it imposes, n = 2,061
  across 10 positions, with AdaptR1's induced profile in a separate panel on its own
  step axis. Two panels rather than one dual-axis chart: a secondary y-axis lets two
  curves be slid against each other until they tell whatever story the author wants,
  which is the failure this project is about.

## 9. Reproducing

```bash
channels measure   # regenerates results/observability_record.json and both figures
channels gate      # exits 1
pytest -q          # 108 tests
```

Corpus hashes: `docs/DATA_PROVENANCE.md`. Pre-registration: `docs/PREREGISTRATION.md`.
Full build narrative including every AMBER judgement call: `BUILD_LOG.md`.
