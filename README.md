# agent-channel-observability

**What this does, in one sentence:** it measures how often you can actually *see*
an AI agent's reasoning when you go looking for it — and shows what that ceiling
does to any safety monitor that depends on reading it.

---

## The problem, in plain words

A common way to check whether an AI agent is behaving is to read its reasoning:
the "thinking out loud" it produces before it acts. If the reasoning shows the
agent planning something harmful, you catch it.

That only works if the reasoning is **there to read**. Sometimes the model does
not produce any. Sometimes it produces reasoning but the provider ships you a
short summary instead. Sometimes it ships an encrypted blob you cannot open.
From the outside, all three look similar — and all three break the monitor.

Almost nobody measures how often this happens. This repository does, and it
turns the answer into a hard upper bound on how well such a monitor can work.

## The hypothesis

> **H1.** Whether an evaluator can read an agent's reasoning is mostly decided by
> the *provider's disclosure policy and the request's configuration*, not by
> whether the model is capable of reasoning.
>
> **H2.** Because a monitor that is triggered by reasoning can only fire when
> reasoning is visible, the visible share is a **ceiling** on that monitor's
> recall — a ceiling no improvement to the monitor itself can lift.

H2 is arithmetic, not an empirical claim: a two-stage detector that only runs
its expensive check when a cheap trigger fires has recall at most
`coverage × stage-2 recall`. The contribution is measuring `coverage` honestly,
with a denominator that is stated rather than assumed.

## What we measure

Every assistant turn is put in exactly one of four states:

| state | meaning for an outside evaluator |
|---|---|
| `raw_present` | the actual reasoning is readable |
| `summary_only` | only a provider-written summary is readable |
| `redacted` | reasoning exists but is withheld or encrypted |
| `absent` | no reasoning was produced at all |

**The denominator is assistant turns that actually occurred.** Turns that never
happened — because a run ended early — are not counted as `absent`. Counting
them would make long agent runs look unmonitorable by construction.

## Two rules that are built into the code, not just described

1. **No detector may report a rate without a recorded, validated recall.**
   `require_validation` raises an exception. A number from an uncalibrated
   instrument is not a weak measurement; it is an unknown one.
2. **An unreadable turn is a failure, not a dropped row.** A turn whose reasoning
   was summarised, redacted or absent stays in the denominator and fails the
   gate. Dropping it would measure only the turns that happened to be readable.

## Headline results

### Visibility is a configuration choice, not a capability limit

Identical prompts, identical benchmarks, different models and settings:

| what was run | turns | raw reasoning readable |
|---|---|---|
| Llama-3.1-8B, Qwen2.5-7B, Ministral-8B (via vLLM) | 3,789 | **0.000** |
| `deepseek-v3.2`, reasoning **not requested** | — | **0.000** |
| `deepseek-v3.2`, reasoning **requested** | 763 | **0.978** |
| `gpt-oss-120b` | 1,263 | **1.000** |
| `qwen3-32b` | 313 | **1.000** |
| `gpt-5-nano` | — | reasoning **encrypted**: `redacted`, not readable |

The DeepSeek pair is the cleanest evidence: **the same model, same prompts, same
provider — only a request parameter changed.** So "this model emits no
reasoning" was really "this request did not ask for it". And `gpt-5-nano`
demonstrably reasons, yet ships the chain encrypted, so an evaluator gets
nothing. Visibility tracks *policy and configuration*, which is H1.

For the three vLLM models the recall ceiling is **0.000 at every step, for any
monitor** — zero observed, 95% one-sided upper bound 0.00071.

*The reasoning-model sweep is still running; the table above is updated as arms
complete, and every figure states its own n.*

### A real incident exposes reasoning, but not as a field

On Anthropic's Mythos 5 transcript — the only public incident transcript from a
frontier lab — raw reasoning is readable for **33.3%** of assistant turns
(686/2,061, 95% CI 0.313–0.353). But it is `<thinking>` markup buried inside a
free-text field, not a structured channel, and **66% of assistant records are
tool calls carrying no reasoning at all**. "The transcript contains reasoning"
and "an evaluator can enumerate the reasoning channel" are different claims;
only the first is true.

The positional profile is **flat** (0.295–0.372 across ten deciles) over a real
20-hour agent run — a datapoint against carrying short-task reasoning profiles
into long-horizon settings.

> **n = 1 trajectory.** One model, one incident. Not a sample. The intervals are
> descriptive, not inferential, and `cluster.py` refuses to compute a clustered
> interval from a single cluster rather than emitting one that looks inferential.

### What you can see depends on the vendor, not on the work

We ran 50 multi-step agentic trajectories per model across **three** different
environments — mock tools, a real Linux shell solving puzzles, and a real shell
doing system administration. Same trajectories, same harness.

| model | across the three environments |
|---|---|
| `kimi-k2-thinking` | reasoning readable on **every** step, all three |
| `qwen3-32b` | readable on every step |
| **`claude-haiku-4.5`** | **readable on step 0, then ~0 — on all three** |
| `gpt-5-nano` | never readable, at any step or effort |

`claude-haiku-4.5` is the sharpest case. It explains its first action and then
goes quiet while it keeps working:

| step | agentharm | CTF shell | OS shell |
|---|---|---|---|
| 0 | **1.000** | **1.000** | **1.000** |
| 1 | 0.000 | 0.000 | 0.020 |
| 2 | 0.000 | 0.000 | 0.143 |

**A monitor watching this agent's reasoning sees its opening move and is blind to
everything after** — including every action it takes in response to what the
tools return, which is where an agentic failure would actually develop.

This is not an artefact of our tooling. The provider's own token accounting
reports **5,818 reasoning tokens on step 0 and exactly zero afterwards**;
`scripts/verify_coverage.py` cross-checks every arm against that accounting and
finds no disagreements.

**One result did not replicate, and we report it.** The first long-horizon arm
(`gpt-oss-120b` on one task) declined steadily with depth, which looked like a
general "coverage decays over a trajectory" law. Run on two further
environments, the decline shrinks and then vanishes into noise — and four of six
models show no decay at all. There is no general decay law here; there is a
per-vendor disclosure policy.

### Two instruments, one corpus, two different answers

Measuring normative objection on WikiTactics (3,865 utterances):

| detector | recall for OBJ | 95% CI |
|---|---|---|
| `tree_coder` (rule-based) | 0.072 | [0.046, 0.111] |
| `nli_detector` (NLI model) | 0.218 | [0.171, 0.273] |

**The intervals do not overlap.** A rate from either one alone inherits that
3× spread before it inherits any sampling error. They are reported side by side
and never averaged — which is why this repository reports **no** objection rate
from the agent corpus at all.

## The data

| corpus | what it is | size | licence |
|---|---|---|---|
| Inspect eval logs (baseline) | 3 models × 3 safety benchmarks, run on local vLLM | 3,789 turns | MIT (own runs) |
| Inspect eval logs (reasoning) | 9 arms, 4 vendors, via OpenRouter | 11,367 turns | own runs; vendor terms vary |
| Agentic trajectories | three families — `agentharm_benign`, `gdm_intercode_ctf`, `agent_bench_os` — 50 trajectories per model | growing; 6 model families | own runs; benign splits only |
| Mythos 5 transcript | Anthropic's released incident transcript | 2,061 turns | not stated; **do-not-train, carries a canary** |
| collusion.wiki | AI agents editing a German wiki | 14,591 revisions | **none stated** |
| WikiTactics | human Wikipedia disagreement, labelled | 3,865 utterances | **none stated** |
| Published incident record | quotations hand-transcribed from METR reports | 10 rows | quoted, not redistributed |

**No corpus text is committed to this repository.** Only counts, rates, figures
and the record. Full detail, including how each was obtained and what may be
published from it, is in [`docs/DATA_PROVENANCE.md`](docs/DATA_PROVENANCE.md).

## How the claims are kept honest

- **A frozen codebook.** Eight text codes plus one action code, each with a
  definition, an inclusion rule, an exclusion rule and sourced examples. It is
  hashed; `codebook_drift` fails the build if it changes after registration.
- **Verified citations.** Every quoted row is checked against the source PDF by
  `scripts/verify_citations.py`, which exits non-zero on a mismatch.
- **Missing numbers stay missing.** A code with no examples in the control has
  *undefined* recall, not zero. An errored sample is reported, not quietly
  dropped. `RESULTS_SUMMARY.md` has a table of every number that does **not**
  exist and why.
- **Human labels are the gold standard.** No LLM produces a label used to
  validate anything. See [`coder-kit/`](coder-kit/).

## Reproduce it

```bash
uv sync --extra dev
uv run channels describe    # what each corpus contains, before any analysis
uv run channels measure     # the record and both figures
uv run channels gate        # exits 1 — the failure is the demonstration
```

`channels gate` is **meant** to exit non-zero. The thresholds in
`config/channels.yaml` are **illustrative defaults, not safety claims**: nothing
in the literature says what share of turns must expose reasoning before a
monitor is trustworthy. Do not cite them as a standard.

## What this does not establish

1. **Trajectory length is still limited.** Median 5–8 turns across the three
   agentic families. Genuinely multi-step, but not the hundred-step setting the
   argument ultimately concerns; it narrows the transfer gap rather than closing
   it. The shapes are also *measured, not explained* — nothing here identifies
   why one vendor stops disclosing after the first turn.
2. **No rate is reported for agent-to-agent objection.** The instruments were
   validated on human prose; nothing shows they transfer to agent protocol
   strings. That transfer is unbuilt, and it is why `rq3` returns a bound.
3. **Thresholds are illustrative.** See above.
4. **Coverage is not monitorability.** This bounds monitors that are *gated on
   reasoning*. Evidence from actions may suffice where reasoning does not.
5. **The published incident record is 10 rows**, chosen by investigators to
   illustrate. No rate may be computed from it, and `refuse_rate()` raises.

## Reuse and attribution

The interval estimators in `_vendored_stats.py` are vendored verbatim from
**safety-eval-pipeline** (DOI [10.5281/zenodo.22182741](https://doi.org/10.5281/zenodo.22182741)),
with the origin named in the file header. The gate contract — aggregate plus
per-stratum bound, un-evaluable counts as failure, worst stratum always reported
— is a reused design, reimplemented. The `unscored`-as-first-class-column
discipline is the same idea, renamed `uninspectable`.

## Layout

```
src/channels/        the package: schema, coverage, emission, bound, detectors
coder-kit/           everything a human annotator needs
scripts/             runners, citation verification, the annotation tool
data/codebook/       the frozen codebook
results/             record, figures, validation records  (committed)
docs/                provenance, pre-registration, deviations log
```

## Citation

See [`CITATION.cff`](CITATION.cff). Licence: MIT.
