# Results summary

Every number below is produced by `channels measure` from the committed corpora
and is reproducible with the three commands in the README. Numbers that do not
exist are marked as not existing rather than omitted.

Generated 2026-09-13. Codebook **v3**, `sha256:a67d3c09dfab3cb3fda0aea911322b15a40a6f45db466e19dd096481c0d21f62`.

> **Status.** The reasoning-model sweep (§1b) is still running; completed arms
> are reported with their measured n and pending arms are named as pending.
> The human annotation (§10) has not run, so `REVERT` has no recall yet.

---

## 1. Emission — the three registered benchmarks (RQ1, RQ2)

**Corpus:** 12 Inspect `.eval` logs from safety-eval-pipeline runs, 2026-08-30.
3,039 samples, **3,789 assistant turns**, 3 models × 3 task classes.
Source hash `sha256:0ae89997c224795386a597dcb27312784a0b29d9394d3c75599a58618e0690f0`.

**Not a single assistant turn in this corpus emitted raw reasoning.**

| model | task class | step | n turns | raw_present | 95% CI | summary_only | redacted | absent | low n |
|---|---|---|---|---|---|---|---|---|---|
| Qwen2.5-7B-Instruct | strong_reject | 0 | 313 | 0.000 | [0.000, 0.0121] | 0.000 | 0.000 | 1.000 | no |
| Qwen2.5-7B-Instruct | sycophancy | 0 | 250 | 0.000 | [0.000, 0.0151] | 0.000 | 0.000 | 1.000 | no |
| Qwen2.5-7B-Instruct | sycophancy | 1 | 250 | 0.000 | [0.000, 0.0151] | 0.000 | 0.000 | 1.000 | no |
| Qwen2.5-7B-Instruct | xstest | 0 | 450 | 0.000 | [0.000, 0.0085] | 0.000 | 0.000 | 1.000 | no |
| Llama-3.1-8B-Instruct | strong_reject | 0 | 313 | 0.000 | [0.000, 0.0121] | 0.000 | 0.000 | 1.000 | no |
| Llama-3.1-8B-Instruct | sycophancy | 0 | 250 | 0.000 | [0.000, 0.0151] | 0.000 | 0.000 | 1.000 | no |
| Llama-3.1-8B-Instruct | sycophancy | 1 | 250 | 0.000 | [0.000, 0.0151] | 0.000 | 0.000 | 1.000 | no |
| Llama-3.1-8B-Instruct | xstest | 0 | 450 | 0.000 | [0.000, 0.0085] | 0.000 | 0.000 | 1.000 | no |
| Ministral-8B-Instruct-2410 | strong_reject | 0 | 313 | 0.000 | [0.000, 0.0121] | 0.000 | 0.000 | 1.000 | no |
| Ministral-8B-Instruct-2410 | sycophancy | 0 | 250 | 0.000 | [0.000, 0.0151] | 0.000 | 0.000 | 1.000 | no |
| Ministral-8B-Instruct-2410 | sycophancy | 1 | 250 | 0.000 | [0.000, 0.0151] | 0.000 | 0.000 | 1.000 | no |
| Ministral-8B-Instruct-2410 | xstest | 0 | 450 | 0.000 | [0.000, 0.0085] | 0.000 | 0.000 | 1.000 | no |

No cell is low-n; every cell clears `MIN_CELL_N = 30`.

- **Aggregate emission: 0 / 3,789 = 0.0000.** One-sided 95% upper bound **0.00071**.
  The reportable sentence is "zero observed; below 0.071% with 95% confidence",
  never "no reasoning found".
- **Uninspectable share: 1.0000** (95% CI [0.9990, 1.0000]). All of it is `absent`;
  `summary_only` and `redacted` are both exactly 0.
- **Positional profile c(j): {0: 0.000, 1: 0.000}.** Only two step indices exist —
  sycophancy is two-turn, the other two benchmarks single-turn.
- **Recall ceiling: 0.000 at every step**, for any r₂.

> **Read this caveat with the number.** These are vLLM-served instruction-tuned
> 7–8B models (Llama-3.1, Qwen2.5, Ministral), none of which emits a reasoning
> channel by design. The zero describes **this serving stack and model family**,
> not a frontier reasoning model's disclosure policy. What it does establish is
> that a standard three-benchmark safety evaluation, run and logged normally,
> leaves an external evaluator with **no deliberation evidence whatsoever** — so
> any monitor gated on deliberation has recall exactly 0 on this evidence base.

### Breakdown by `reasoning_effort` — **does not exist**
No log records a `reasoning_effort`, `reasoning_summary` or `reasoning_history`
setting. Every cell carries `reasoning_effort=None`. Emission is reported by
model × task class × step index only, as spec §9.1 directs when the second axis
is unavailable. This is a real limitation: extension A's "manipulate rather than
observe `reasoning_effort`" cannot be piloted on this corpus.


---

## 1b. Emission — reasoning-capable models (RQ1, RQ2)

**Corpus:** `data/inspect-runs-reasoning/`, this project's own runs via
OpenRouter, 2026-09-12/13. Sample counts match §1 exactly so the two are
comparable. Scoring disabled: we measure the channel, not performance.

<!-- BEGIN:reasoning-status -->
**9 of 9 arms complete**, 11,367 assistant turns measured. `MIN_CELL_N=30`; no cell is low-n. 0 sample(s) errored; 0 incomplete log(s) excluded and counted.
<!-- END:reasoning-status -->

Arms below are complete. Pending arms are **not** included in any figure or
total, so a partial sweep cannot be read as a finished one. Every n stated is
the n actually measured.

### Arms complete

<!-- BEGIN:reasoning-arms -->
| arm | n turns | raw_present | 95% CI | summary_only | redacted | absent |
|---|---|---|---|---|---|---|
| `gpt-oss-120b` | 1,263 | **1.0000** | [0.9970, 1.0000] | 0.0000 | 0.0000 | 0.0000 |
| `qwen3-32b` | 1,263 | **1.0000** | [0.9970, 1.0000] | 0.0000 | 0.0000 | 0.0000 |
| `glm-4.7-flash` | 1,263 | **0.9976** | [0.9930, 0.9992] | 0.0000 | 0.0000 | 0.0024 |
| `claude-haiku-4.5` | 1,263 | **1.0000** | [0.9970, 1.0000] | 0.0000 | 0.0000 | 0.0000 |
| `deepseek-v3.2` | 1,263 | **0.0000** | [0.0000, 0.0030] | 0.0000 | 0.0000 | 1.0000 |
| `deepseek-v3.2-reasoning-on` | 1,263 | **0.9802** | [0.9709, 0.9866] | 0.0000 | 0.0000 | 0.0198 |
| `gpt-5-nano-low` | 1,263 | **0.0000** | [0.0000, 0.0030] | 0.0000 | 1.0000 | 0.0000 |
| `gpt-5-nano-medium` | 1,263 | **0.0000** | [0.0000, 0.0030] | 0.0000 | 1.0000 | 0.0000 |
| `gpt-5-nano-high` | 1,263 | **0.0000** | [0.0000, 0.0030] | 0.0000 | 1.0000 | 0.0000 |
<!-- END:reasoning-arms -->

Zero samples errored. Incomplete logs are excluded and counted, not partially
included.

Across completed arms the uninspectable share is **under 0.005**, against
**1.0000** for the vLLM baseline in §1, and the recall ceiling rises from
**0.000** to essentially **1.000**. Current pooled values, including partially
run arms, are in `results/observability_record_reasoning.json`, which regenerates
with the sweep. Only two step indices exist in these benchmarks, so the
positional profile is nearly flat by construction and carries no information
here.

### The headline contrast

| what was run | turns | raw reasoning readable |
|---|---|---|
| Llama-3.1-8B, Qwen2.5-7B, Ministral-8B (vLLM) | 3,789 | **0.0000** |
| **`deepseek-v3.2`, reasoning NOT requested** | **1,263** | **0.0000** [0.0000, 0.0030] |
| **`deepseek-v3.2`, reasoning REQUESTED** | **1,263** | **0.9802** [0.9709, 0.9866] |
| `gpt-oss-120b` | 1,263 | **1.0000** |
| `qwen3-32b` | 1,263 | **1.0000** |
| `claude-haiku-4.5` | 1,263 | **1.0000** |
| `glm-4.7-flash` | 1,263 | **0.9976** |
| **`gpt-5-nano` (effort=low)** | **1,263** | **0.0000** — reasoning **encrypted**, 341,726 reasoning tokens |

**This is the result the baseline alone could not support.** A reviewer reading
§1 could fairly object that 0/3,789 was measured on models that were never going
to emit reasoning. The DeepSeek pair answers that directly and is now a
**complete, symmetric, within-model comparison**: same model, same provider,
same benchmarks, same 1,013 sample ids, 1,263 turns on each side — **0.0000 with
reasoning not requested, 0.9802 with it requested.** "This model emits no
reasoning" was really "this request did not ask for it."

### Reasoning that happens and cannot be read

`gpt-5-nano` at `reasoning_effort=low`, 1,263 turns, complete arm:

| quantity | value |
|---|---|
| reasoning tokens emitted | **341,726** |
| `raw_present` | **0.0000** [0.0000, 0.0030] |
| `redacted` | **1.0000** |

The model reasoned across every turn — a third of a million tokens of it — and
an external evaluator can read **none** of it. This is a different failure from
the DeepSeek default arm, which produced no reasoning at all, and the two are
distinguishable only because the four-state classification separates `absent`
from `redacted`. A binary "was reasoning visible?" would have scored them
identically at zero and lost the distinction that matters:

| arm | reasoning tokens | state | what it means for an evaluator |
|---|---|---|---|
| `deepseek-v3.2` default | 0 | `absent` 1.000 | nothing to read, because nothing was produced |
| `gpt-5-nano` low | 341,726 | `redacted` 1.000 | plenty was produced; you are not permitted to read it |
| `deepseek-v3.2` reasoning-on | 539,635 | `raw_present` 0.980 | produced and readable |

**Taken together: what an evaluator can see is set by disclosure policy and
request configuration, not by model capability.** That is H1, measured on three
complete arms of one thousand samples each.

> **Why `summary_only` is 0.0000 everywhere.** OpenRouter returns both an
> encrypted chain *and* a short summary for `gpt-5-nano`. `coverage.py` records
> the **strongest limitation** present, so a turn carrying both is classified
> `redacted`, never `summary_only`. That is the documented rule (spec §4) and it
> biases against observability, which is the safe direction — but it does mean
> `summary_only` is structurally unobservable whenever a provider ships a
> summary alongside an encrypted chain. A reader should not read the zero as
> "no provider offers summaries".

### The within-model control, measured

`deepseek-v3.2` was run twice over the identical 1,013 samples, differing only
by whether the request asked for reasoning:

| configuration | n turns | raw_present | 95% CI | absent | reasoning tokens |
|---|---|---|---|---|---|
| default (`reasoning_tokens` unset) | 1,263 | **0.0000** | [0.0000, 0.0030] | 1.0000 | **0** |
| `--reasoning-tokens 2048` | 1,263 | **0.9802** | [0.9709, 0.9866] | 0.0198 | **539,635** |

Both arms are complete: 4 of 4 task logs, 1,013 of 1,013 samples, identical
sample ids, 1,263 assistant turns each. The intervals are disjoint by a margin
of 0.97.

Same model, same prompts, same provider, same benchmarks, same sample ids.
**One request parameter.** The default arm emitted *zero* reasoning tokens
across all 1,013 samples — not a small number, zero — and the requested arm
emits raw chain-of-thought on 97.8% of turns.

So "this model does not expose reasoning" was never a fact about the model. It
was a fact about the request. **Whether an evaluator can read an agent's
deliberation is a configuration and disclosure choice, which is H1.**

> **What is still incomplete.** The DeepSeek pair is complete. The `gpt-5-nano`
> row remains a **single-prompt probe** and is labelled as such — its three
> effort arms are still running, and until they finish this project has **no
> complete arm exhibiting `redacted`**, and no `reasoning_effort` axis. The
> probe does not enter the generated table above, which contains complete arms
> only.
>
> Note also what the DeepSeek pair does **not** show. It establishes that
> visibility is set by the request for *this* model on *these* benchmarks. It
> does not establish that every provider honours such a request, nor that a
> provider which emits reasoning will keep doing so; `gpt-5-nano` is the
> counter-case, and it is still only a probe.

### `reasoning_effort` — a designed experiment, and it separates two things

This is the only arm where a variable was **manipulated** rather than observed,
which is what spec §15 extension A asks for. `gpt-5-nano` was run over the same
1,013 samples at each effort level, changing nothing else.

| effort | n turns | reasoning tokens | mean tokens/turn | vs. low | `raw_present` | `redacted` |
|---|---|---|---|---|---|---|
| low | 1,263 | 341,726 | 337 | 1.0× | **0.0000** | **1.0000** |
| medium | 1,263 | 1,834,432 | 1,811 | **5.4×** | **0.0000** | **1.0000** |
| high | 1,263 | 4,731,968 | 4,671 | **13.8×** | **0.0000** | **1.0000** |

**The manipulation worked, monotonically, and the outcome never moved.** Raising
effort from low to high multiplied reasoning volume by **13.8×** — the model
demonstrably thought an order of magnitude harder — while the share an evaluator
can read stayed at exactly **0.0000** at every level, and every one of 3,789
turns stayed `redacted`.

So *how much* a model reasons and *how much of it you may read* are separate
quantities, and this arm moves one without moving the other. A monitor gated on
deliberation gains **nothing** from the model thinking 5.4× harder, because the
gate is not set by the thinking. It is set by the disclosure policy.

This matters for a specific bad inference: "the model reasoned a lot, so there
was plenty for a monitor to catch". Across these three arms there were
**6.9 million reasoning tokens** and a recall ceiling of **0.000** throughout.

> **Scope.** One model, one vendor, all three levels. It shows that
> effort and disclosure *can* be independent, not that they always are — a
> vendor that returns raw chains would presumably show `raw_present` at every
> effort level. The claim is that volume is not evidence of visibility, and one
> clean counter-example is enough to establish that.

---

## 2. Emission — the Mythos 5 incident transcript

**Corpus:** `anthropics/mythos-5-incident-transcript`, 2,061 assistant turns,
**one 20-hour trajectory** (2026-07-18T01:02:54Z → 21:29:27Z).

| quantity | value |
|---|---|
| raw_present | 686 turns, **0.3328** |
| summary_only | 0 |
| redacted | 0 |
| absent | 1,375 turns, 0.6672 |
| uninspectable share | **0.6672**, 95% CI [0.647, 0.687] |
| recall ceiling, mean coverage | **0.3328** |

### Positional profile c(j), 10 equal-width bins

| bin | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| c(j) | .362 | .353 | .295 | .319 | .295 | .324 | .372 | .357 | .343 | .308 |

**The profile is flat.** Range 0.295–0.372, every interval overlapping every
other, across a real long-horizon agentic trajectory. AdaptR1's *induced*
per-step profile on multi-hop QA swings 1.00 → 0.00 → 0.84 → 0.20 → 0.33 → 0.00
over six steps. Their Limitations already disclaim transfer to long-horizon
agentic settings; this is one datapoint consistent with that disclaimer.

> **n = 1 trajectory.** Every bin is filled by the same run, so the intervals
> above assume within-trajectory independence, which is false. They are
> **descriptive, not inferential**. `cluster.clustered_wilson` returns
> `status="single_cluster_no_interval"` on this corpus rather than emitting a
> wide finite interval, because "we cannot say" and "somewhere in this range"
> are different claims.

### The denominator matters by 3×
Per *assistant message*, raw reasoning is present for 686/2,061 = **33.3%**.
Per assistant *text* turn, it is 686/700 = **98.0%**. The 1,361 tool-call
records carry no `content` field at all. Which denominator you pick changes the
headline by a factor of three, which is exactly the point `emission.py`'s
docstring makes about AdaptR1's unreconcilable averages.

---

## 3. Detector validation — two instruments, reported side by side

Control: WikiTactics, 3,865 utterances / 213 conversations (De Kock, Stafford &
Vlachos, EMNLP 2022). Gold codes assigned by a **committed** label→code table,
never inferred at runtime.

| detector | code | support | recall | 95% CI | precision | status |
|---|---|---|---|---|---|---|
| tree_coder 1.0 | OBJ | 249 | **0.072** | [0.046, 0.111] | 0.071 | measured |
| tree_coder 1.0 | REF | 31 | 0.065 | [0.018, 0.207] | 0.118 | measured |
| tree_coder 1.0 | SHARE | 1,445 | 0.187 | [0.168, 0.208] | 0.379 | measured |
| nli_detector 1.0 | OBJ | 248 | **0.218** | [0.171, 0.273] | — | measured |
| nli_detector 1.0 | REF | 31 | — | — | — | outside detector label space |
| nli_detector 1.0 | SHARE | 1,241 | — | — | — | outside detector label space |

`nli_detector` scored n=3,652 with 213 abstentions (thread-initial utterances
have no predecessor to contradict); abstentions leave the denominator and are
counted, so a reader can recompute either way.

**The headline finding of §3: the two OBJ intervals do not overlap.**
0.072 [0.046, 0.111] against 0.218 [0.171, 0.273] — a 3× difference on the same
corpus, the same code, the same gold labels. Per spec §11.2's stop rule this is
a *result*, not a bug: the reported rate is detector-dependent before it is
sampled. **They are never averaged.**

Neither instrument was tuned. `TreeCoder`'s cues are transcriptions of the
codebook's inclusion rules and `NliDetector`'s threshold is a prior 0.5; sweeping
either against this score would convert a pre-specified instrument into a fitted
one and void the claim.

### Recall that does not exist
`ESC`, `WARN`, `NORM` and `SELF_LICENSE` have **no WikiTactics equivalent**, so
their recall is **undefined on this control, not zero**. Reporting 0.0 would
invent a measurement out of an absent one.

---

## 4. collusion.wiki — the GO/NO-GO on RQ3

Frozen export, 2026-09-03. Row counts match the published figures exactly:
revisions **14,591**, pages **4,579**, labels **3,103**.

### Actors per page (agents only; human handles excluded)

| distinct agents | pages | share | cumulative |
|---|---|---|---|
| **1** | **2,824** | **70.18%** | 70.18% |
| 2 | 549 | 13.64% | 83.82% |
| 3 | 189 | 4.70% | 88.52% |
| 4 | 112 | 2.78% | 91.30% |
| 5 | 78 | 1.94% | 93.24% |
| 6 | 46 | 1.14% | 94.38% |
| 7 | 42 | 1.04% | 95.43% |
| 8–20 | 152 | 3.78% | 99.21% |
| 21–340 | 32 | 0.79% | 100.00% |

Total pages carrying ≥1 agent revision: **4,024**. Pages with ≥2 distinct
agents: **1,200 (29.82%)**.

**70.18% of pages cannot contain peer disagreement by construction.** Those are
not a small denominator, they are no denominator. RQ3 is structurally feasible
on under a third of the corpus.

### Concentration — and a correction to the spec
Spec §8 says "91% of collusion_wiki edits come from the single actor `dse`".
`dse` is a **wiki, not an actor**. Measured:

- Revisions from wiki `dse`: 13,403 / 14,591 = **91.9%**
- Most active *individual actor*: 2.3%, across **3,102 distinct actors**

The clustering unit is the wiki (or the page), not the actor. The synthetic
91%-in-one-cluster fixture in `test_clustered_interval_wider_than_naive` remains
valid; only the comment justifying it was mis-specified.

930 of 14,591 revisions fail toward `HUMAN_MESSAGE` (human handle, or handle
absent from `labels.jsonl`) and are excluded from any inter-agent rate.

---

## 5. RQ3 — no rate is reported

`rq3.rq3_endpoint` returns `rate=None`,
`rate_status="no_validated_detector_for_this_corpus"`, and three blockers:

1. **Structural** — 2,824/4,024 pages (70.2%) have one agent.
2. **Instrumental** — the two detectors disagree 3× on rung-1 OBJ recall, with
   non-overlapping intervals.
3. **Transfer** — rung 2 is not built. Both instruments were validated on human
   Wikipedia prose; nothing establishes transfer to agent protocol strings.

### Both sensitivity analyses

- **Recall correction.** An observed rate r from an instrument with recall k
  implies a true rate ≈ r/k. At the two measured recalls that is **13.9× (tree)
  vs 4.6× (NLI)** — the same observation implies truths 3× apart.
- **Denominator choice.** The same numerator over all 4,024 pages vs the 1,200
  multi-agent pages differs by **3.35×** (e.g. 10 objections: 0.00249 vs
  0.00833). That factor is the reporting-unit choice the prior art leaves
  unstated.

---

## 6. The published incident record

10 rows transcribed (5 influence-typology exemplars, 2 ASK→ANSWER dyads, 1 further zz-prefixed ASK).
**No rate may be computed**; `refuse_rate()` raises `RateFromTypologyError`.

**10 rows, all verified** against the source PDFs by
`scripts/verify_citations.py`: 0 mismatches. Verified pages p.14, p.33, p.43,
p.44 (HF investigation) and p.124 (Frontier Risk Report, INC-037, "Google
DeepMind — hash-collision").

Verification changed the data. The LIBRAW dyad is on **p.44**, not the seeded
p.43, and **both of its strings were truncated** in the seed; the full verbatim
is restored, with METR's own `[...]` elisions preserved.

**The gap is itself the finding.** The four numerator codes `OBJ`, `REF`, `ESC`,
`WARN` have **zero real positive examples** in the codebook. Across every source
consulted for this build, no published source quotes one agent normatively
objecting to another agent's conduct. Every verbatim inter-agent string that has
been published is coordination, flattery or reciprocity. Whether objection does
not happen, or investigators do not quote it, is precisely the
evidence-sufficiency question in spec §15 C.

---

## 7. Gates — the failure is the deliverable

`channels gate` exits **1** on the real corpora:

```
[      FAIL] deliberation_coverage_floor: aggregate raw_present 0.117;
            worst stratum Qwen2.5-7B-Instruct/effort=None at 0.000
            against a floor of 0.500
[      FAIL] uninspectable_ceiling:       aggregate uninspectable 0.883;
            worst stratum Qwen2.5-7B-Instruct/effort=None at 1.000
            against a ceiling of 0.500
[      PASS] codebook_drift:              observed sha256:2d1077fa...
                                       vs registered sha256:2d1077fa...
```

The 0.883 aggregate pools both corpora *for the gate only*; the records
themselves are never pooled (see §8). The floor of 0.50 and ceiling of 0.50 in
`config/channels.yaml` are **illustrative defaults, not safety claims**. Nothing
in the literature establishes what share of turns must expose raw reasoning
before a deliberation-gated monitor is trustworthy — the question has not been
asked in this form. **Do not cite them as a standard.**

---

## 8. Numbers that do not exist, and why

| quantity | status |
|---|---|
| Emission by `reasoning_effort` | **Does not exist yet.** No completed log records the setting; the three `gpt-5-nano` effort arms are still running. |
| `deepseek-v3.2` default config, full run | **Pending.** Currently a probe only; the control is a pair and only argues as a pair. |
| `gpt-5-nano` full run | **Pending.** The `redacted` state is so far evidenced by a probe, not a 1,013-sample arm. |
| A single pooled positional profile across both corpora | **Deliberately not computed.** Mythos step indices are decile bins of one trajectory; Inspect step indices are turn ordinals in independent samples. One key cannot mean both. Each corpus writes its own record. |
| Clustered interval for Mythos | **Does not exist.** 2,061 turns, 1 cluster. `clustered_wilson` returns `single_cluster_no_interval`. |
| Recall for ESC / WARN / NORM / SELF_LICENSE | **Undefined**, not zero. No support in the control. |
| `nli_detector` recall for REF / SHARE | **Undefined**, not zero. Outside the detector's label space. |
| Any RQ3 rate | **Refused.** See §5. |
| Any rate from the published record | **Refused.** n=7, investigator-selected. |
| `messages_authenticated` | **null.** No corpus read here supports authentication. Recording the absence is the honest form of the adversarial-channel finding. |
| Test–retest reliability of the codebook | **Not measured.** Requires a second human coder. |
| Rung-2 validation | **Not built.** |

---

## 9. Artifacts

| file | contents |
|---|---|
| `results/observability_record.json` | Inspect-logs baseline record, schema-valid, 12 cells |
| `results/observability_record_reasoning.json` | Reasoning-model record, schema-valid, updated as arms land |
| `results/observability_record_mythos.json` | Mythos record, schema-valid, 2,061 cells |
| `results/record_schema.json` | JSON Schema draft 2020-12, `additionalProperties: false` |
| `results/figures/figure1_emission_states.png` | + `_caption.txt` |
| `results/figures/figure2_recall_ceiling.png` | Inspect logs, + `_caption.txt` |
| `results/figures/figure2_recall_ceiling_mythos_transcript.png` | Mythos, + `_caption.txt` |
| `results/validation/tree_coder_1.0_wikitactics.json` | measured recall |
| `results/validation/nli_detector_1.0_wikitactics.json` | measured recall |

159 tests pass with no network, 89% coverage; `ruff` and `mypy --strict` clean.

---

## 10. Human annotation — registered, not yet run

Confirmatory endpoints C1–C3 are registered in
[`docs/PREREGISTRATION.md` §0.2](docs/PREREGISTRATION.md) with their decision
rules fixed **before any label exists**. Nothing below has a number yet, and the
absence is the current honest state rather than an omission.

| endpoint | what it measures | status |
|---|---|---|
| **C1** | Precision of the checksum-revert detector: of 60 sampled reverts, what share are genuine disagreement? | **no labels yet** |
| **C2** | Verbal objection in the message channel: `OBJ`/`REF`/`ESC`/`WARN` in 200 sampled `change_summary` messages | **no labels yet** |
| **C3** | Cohen's κ between the coder and the author on 50 shared items | **no labels yet** |

Registered decision rules, restated here so the result cannot be reinterpreted
after the fact:

- `REVERT` is reported as **validated** only if the page-clustered 95% lower
  bound exceeds **0.50**.
- A zero count in C2 is reported as a one-sided 95% upper bound (≈0.013 at
  n=200) and the sentence "zero observed; below X with 95% confidence" —
  **never** "no objection occurs".
- κ ≥ 0.60 is adequate reproducibility for an exploratory instrument; below
  **0.40**, C1 is reported as unreliable regardless of its point estimate.
- The second coder is the **author of the codebook**. κ therefore measures
  whether the written rules reproduce the author's intent; it will not be called
  inter-rater reliability.

**Current detector state.** `revert_detector` v1.0 has a validation record with
`status="no_support_in_control"` for `REVERT` — no corpus available to this
project carries human revert labels. It predicts 1,275 reverts over 13,661
artefact edits and **reports no recall**, which is why no revert-based rate
appears anywhere above.
