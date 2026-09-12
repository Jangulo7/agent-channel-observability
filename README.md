# agent-channel-observability

Measures, from Inspect evaluation logs, **how often a model's reasoning is actually
observable to an external evaluator** — and derives the recall ceiling that observability
imposes on any monitor gated on deliberation.

The thesis is that a measurement is untrustworthy when you cannot see how it was
produced. Two rules are therefore architectural rather than stylistic, and the tests
that pin them are the ones worth reading first:

1. **No detector reports a rate without a recorded validated recall.** A number with no
   measured instrument behind it is not a finding.
2. **An uninspectable sample is a failure, not a dropped denominator.** A turn whose
   reasoning was summarised, redacted or absent stays in the denominator and fails the
   gate. Dropping it would compute a rate over the turns that happened to be observable
   — a measurement of the observable subset, not of the agent.

## The result

On the Mythos 5 incident transcript — the only public incident transcript a frontier lab
has released — **raw reasoning is readable for 33.3% of assistant turns**
(686 / 2,061; Wilson 95% CI 0.313–0.353). The uninspectable share is **0.667**
[0.647, 0.687].

With a *perfect* second stage (r₂ = 1), that caps a deliberation-gated monitor at
**0.333 recall** averaged over the trajectory, and at **0.295 against an action taken at
the trajectory's weakest position**.

The positional profile is **flat** — 0.295 to 0.372 across ten decile bins, every
interval overlapping every other — across a real 20-hour long-horizon agentic
trajectory. This is a datapoint against transferring the sharply-varying per-step
profiles reported on short multi-hop QA to agentic settings, which those papers'
own Limitations sections already decline to claim.

**Read these caveats before citing any of the above.** n = 1 trajectory, one model, one
incident. It is not a sample. The Wilson intervals assume within-trajectory
independence, which is false; they are descriptive, not inferential. `cluster.py`
refuses to compute a clustered interval from a single cluster rather than emitting a
finite one that would look inferential.

Reasoning in this corpus is in-band `<thinking>…</thinking>` markup inside a content
string, not a structured field. "The transcript contains reasoning" and "the transcript
exposes a reasoning field an evaluator could read programmatically" are different
claims, and only the first is true.

## Status

Steps 0–7 of the build order are the paper and have shipped. Steps 8–12 — the
inter-agent channel arm, the validation ladder, the detectors and the published incident
record — are the secondary arm and are **not built**. `BUILD_LOG.md` is the honest
account, including what did not run and why; `RESULTS_SUMMARY.md` has the numbers in
citable form.

The emission table is currently **one row**. The three-benchmark × three-model
measurement it was designed around needs Inspect `.eval` logs that are not on this
machine; see `BUILD_LOG.md`, Q1.

## Install

```bash
uv venv && uv pip install -e ".[dev]"
```

Python ≥ 3.11. `inspect-ai` is pinned to `0.3.260` to match the run that produced the
logs. Corpora are **not** committed — `data/` subdirectories are gitignored, and only
counts, rates, hashes and figures ever reach the repository. See
`docs/DATA_PROVENANCE.md` for what each corpus is and the SHA-256 of the exact bytes
analysed.

## Use

```bash
channels describe   # what each corpus contains, without analysing it
channels measure    # writes results/observability_record.json and both figures
channels gate       # runs the three gates; exits non-zero on failure
```

`describe` names every corpus it could **not** find, with the path it checked. A run
that quietly omits a corpus invites the reader to assume it was empty.

`gate` currently fails on the committed data, which is the intended demonstration:

```
[FAIL] deliberation_coverage_floor: aggregate raw_present 0.333;
       worst stratum mythos-5/effort=None at 0.333 against a floor of 0.500
[FAIL] uninspectable_ceiling:       aggregate uninspectable 0.667 against a ceiling of 0.500
[FAIL] codebook_drift:              no codebook hash recorded in the pre-registration
```

The third is not a bug. The codebook is step 9 and does not exist, so there is nothing
to compare against, and the gate returns `UNEVALUABLE` — which counts as failure. A gate
that passed because it had nothing to check would be the exact defect this package
exists to name.

> **The thresholds in `config/channels.yaml` (floor 0.50, ceiling 0.50) are illustrative
> defaults, not safety standards.** Nothing in the literature establishes what share of
> an agent's turns must expose raw reasoning before a deliberation-gated monitor is
> trustworthy, because the question has not been asked in this form. They exist so the
> gate machinery has something to compare against. Citing them as a standard would
> reproduce exactly the unprovenanced-number problem this project criticises.

## Layout

| path | what it is |
|---|---|
| `src/channels/coverage.py` | classifies one turn into the four reasoning-channel states |
| `src/channels/emission.py` | rates by model × task class × step index; **read its denominator docstring** |
| `src/channels/bound.py` | recall ceiling, scalar and positional |
| `src/channels/cluster.py` | clustered intervals; refuses when there is one cluster |
| `src/channels/priors.py` | published constants, each with its source and its caveats. Constants only — a test parses the AST and fails if executable logic appears |
| `src/channels/gates.py` | the three gates; un-evaluable counts as failure |
| `src/channels/record.py` | the machine-readable record; validates before writing |
| `results/observability_record.json` | the artefact another researcher checks the paper against |
| `docs/PREREGISTRATION.md` | what was specified before the data was seen |

## Tests

```bash
pytest -q          # 108 tests
ruff check src tests
mypy src/channels
```

Test fixtures are synthetic by design and obviously so — every fixture string is
recognisable as fake at a glance. No test reads a real corpus. Analysis inputs are real
or absent; there is no third option in this repository.

`tests/test_publication_safety.py` enforces that no canary GUID and no corpus text
reaches a published artefact.

## Provenance and credit

The statistics helpers in `src/channels/_vendored_stats.py` are vendored verbatim from
**[safety-eval-pipeline](https://github.com/Jangulo7/safety-eval-pipeline)** (Johanna
Angulo), which also supplies this project's gate contract — an aggregate bound plus a
per-stratum bound, the worst stratum always reported, a marginal annotation when the
interval crosses the threshold, and un-evaluable counting as failure rather than being
dropped. They are vendored rather than reimplemented so the claim that this is the same
code, with the same tested edge cases, holds literally.

Corpora, their licences and their hashes: `docs/DATA_PROVENANCE.md`. The Mythos
transcript carries a canary GUID and a do-not-train notice; no content from it is sent
to any third-party service.

## Citation

See `CITATION.cff`.

## Licence

MIT. The licence covers the code. It does not extend to any corpus the code reads —
see `docs/DATA_PROVENANCE.md` for each corpus's own terms.
