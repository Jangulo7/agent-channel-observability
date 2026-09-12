# Results summary

Every number below is produced by `channels measure` from the committed corpora
and is reproducible with the three commands in the README. Numbers that do not
exist are marked as not existing rather than omitted.

Generated 2026-09-12. Codebook `sha256:2d1077fad571ec02c5bbbef5cfdc5f3541b46305ab9e9004e318bd37ea56af83`.

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

7 rows transcribed (5 influence-typology exemplars, 2 ASK→ANSWER dyad halves).
**No rate may be computed**; `refuse_rate()` raises `RateFromTypologyError`.

5 of 7 rows carry an unverified page reference or a `TODO(johanna)` citation.
The two dyad rows are marked `p.43 [VERIFY page: +/-3]` and **have not been
verified** — I do not have the PDF.

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
| Emission by `reasoning_effort` | **Does not exist.** No log records the setting. |
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
| `results/observability_record.json` | Inspect-logs record, schema-valid, 12 cells |
| `results/observability_record_mythos.json` | Mythos record, schema-valid, 2,061 cells |
| `results/record_schema.json` | JSON Schema draft 2020-12, `additionalProperties: false` |
| `results/figures/figure1_emission_states.png` | + `_caption.txt` |
| `results/figures/figure2_recall_ceiling.png` | Inspect logs, + `_caption.txt` |
| `results/figures/figure2_recall_ceiling_mythos_transcript.png` | Mythos, + `_caption.txt` |
| `results/validation/tree_coder_1.0_wikitactics.json` | measured recall |
| `results/validation/nli_detector_1.0_wikitactics.json` | measured recall |

159 tests pass with no network, 89% coverage; `ruff` and `mypy --strict` clean.
