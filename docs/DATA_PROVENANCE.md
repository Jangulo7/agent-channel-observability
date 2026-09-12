# Data provenance

Every corpus this project reads, what it is, where it came from, what licence it
carries, and the hash of the exact bytes analysed. **No corpus text is committed to
this repository** — only counts, rates, hashes and figures. The `data/` subdirectories
named below are gitignored.

Hashes are SHA-256 of the file as analysed, computed 2026-09-12 during the build.

---

## 1. Mythos 5 incident transcript

| | |
|---|---|
| Source | `https://github.com/anthropics/mythos-5-incident-transcript` |
| Local path | `data/mythos-5-incident-transcript/` (gitignored) |
| File analysed | `transcript.jsonl`, 2,621,187 bytes |
| SHA-256 | `6f2a5a50b53640bd779a198cef8a620f2d6e2bbaaf4a0dea9edac87a69fc3e4b` |
| Licence | Not stated in the repository. Released by Anthropic for study. |
| Rows | 2,065 (1 metadata + 2,064 messages) |

**Caveats that travel with any number derived from it.**
- It carries a canary GUID and a do-not-train notice. The GUID must not appear in any
  published artefact; `tests/test_publication_safety.py` enforces that. No content from
  this corpus is sent to any third-party service.
- Anthropic states four modifications: messages 1–81 redacted, messages after 2145
  redacted, some third-party-server messages redacted, and individual words redacted
  in place as `[redacted-xyz]`. Observed index range is therefore 82–2144, and 19
  assistant text messages are `[redacted]`. Utterances from it are
  `Provenance.REDACTED_PARTIAL`, never `VERBATIM`.
- **n = 1 trajectory.** It is one incident from one model. It supplies a real-incident
  task class, not a sample.

## 2. collusion.wiki frozen export ("german-collusion-wiki")

| | |
|---|---|
| Local path | `data/german-collusion-wiki/` (gitignored) |
| Layout | gzipped, plain, or nested one level deep, depending on how it was unpacked; the loader searches rather than assuming |
| Licence | **Unspecified — research use, cite source.** Counts published, text not. |
| Export generated | `2026-09-03T03:42:36Z` (from `manifest.json`) |
| Cut | `revision.write_date >= 2026-05-01` |

Verified against the publisher's own `SHA256SUMS`, all five files `OK`:

| File | Rows | Spec expects | SHA-256 |
|---|---|---|---|
| `pages.jsonl` | 4,579 | 4,579 ✅ | `92b296170b496b836cdf5ef783bed9465d2d75db7e1a0becec1c36c8b7c42cfd` |
| `revisions.jsonl` | 14,591 | 14,591 ✅ | `60df4a515178230aa952d9f64f6215aea4bd95ab2f05e31e484cf9b887e3f793` |
| `labels.jsonl` | 3,103 | 3,103 ✅ | `d94aecd84baecda46344f5b8726a95a9c81e7e41a1c0969fc89a90c8906f0388` |
| `events.jsonl` | 19,913 | not specified | `588584295f1c4a7c3d90b04075ab151504f165ff069534d935cda08853ec28b1` |
| `manifest.json` | — | — | `b6d53e16b5d9a6a0a98d4577238835ee7a574d7d10a8f1312330b4e626c6ba2b` |

`manifest.json` also records the upstream database hash
`199241bf9e0b38b58764cf1545680de8fec8896db034050bde145e3b6f6ce0bb`.

**Caveats.**
- Actor attribution was inferred by the source authors' filter, recorded in
  `manifest.json`. It is not an authenticated sender field, and nothing in this corpus
  supports authentication — which is why `messages_authenticated` is `null` in the
  observability record rather than absent from it.
- Actor concentration is extreme: the manifest's `per_wiki` block puts 13,403 of 14,591
  revisions on the single wiki `dse` (91.9%). Per-observation independence is false;
  `cluster.py` exists for this.
- Frozen export only. No loader in this repository re-crawls the live site.

### What a revision yields (v2 of the schema onward)

Each revision produces **two** utterances, because it carries two channels:

- the body diff as `Channel.ARTEFACT_EDIT` — addressed to no one, observable to
  peers, and able to express disagreement by action. Body text is **never**
  carried into an `Utterance`.
- the `change_summary` as `Channel.INTER_AGENT_MESSAGE` — a short note to other
  editors, present on 12,773 of 14,591 revisions (93.3%). Summary text **is**
  carried, because the verbal codebook needs it to code the message channel at
  all; it is kept out of published artefacts instead.

Coding a revision as a single `INTER_AGENT_MESSAGE`, as v1 did, put acts that
carry no words into the inter-agent message denominator.

**Reverts** are identified by checksum matching: a revision whose body hash
equals an earlier revision's on the same page, where the preceding revision was
by a different actor. 1,275 of 13,661 agent edits (9.33%). Self-reverts (24) are
excluded. This is the canonical definition (Wikimedia `Research:Revert`) and a
known **undercount** — checksum matching finds about 94% of reverts and no
partial revert at all.

**Clustering.** The page is the primary cluster unit and the actor is the
sensitivity analysis, reported together. Note that the spec's justification
("91% of edits come from the single actor `dse`") is wrong on the data: `dse` is
a **wiki**, holding 91.9% of revisions, while the most active individual actor
holds 2.3% across 3,102 actors.

## 3. WikiTactics

| | |
|---|---|
| Source | `https://raw.githubusercontent.com/christinedekock11/wikitactics/main/wikitactics.json` |
| Local path | `data/wikitactics/` (gitignored) |
| File analysed | `wikitactics.json`, 2,206,025 bytes |
| SHA-256 | `edbc8f82cea457568b38dd00e3b34d660bf7303248bed95989d10d360a781bb3` |
| Licence | **No licence file in the source repository.** Cite the publication; publish counts, not utterance text. |
| Citation | De Kock, Stafford & Vlachos, EMNLP 2022. |

**Caveats.**
- Human-authored Wikipedia talk-page disputes. It is the labelled control used to
  measure detector recall — it is *not* agent text, and transfer of an instrument
  validated here to agent protocol strings is unvalidated. That is rung 1 of the
  validation ladder, and the report says so in Limitations.

## 4. Inspect evaluation logs — safety-eval-pipeline

| | |
|---|---|
| Intended source | `logs/` of the `safety-eval-pipeline` runs (sycophancy, xstest, strong_reject) |
| Status | **NOT AVAILABLE to this build.** See `BUILD_LOG.md` Q1. |

The public repository excludes them by design (`.gitignore:43`, *"Inspect logs are not
committed at all"*). What is public is the derived record
`results/published/results.json` of run `run-20260830-193016`, which establishes the
run's shape but contains no per-turn message content and therefore no reasoning channel:

- 12 cells, 3 benchmarks × 3 models, all `status: ok`.
- Models: `vllm/Qwen/Qwen2.5-7B-Instruct`, `vllm/meta-llama/Llama-3.1-8B-Instruct`,
  `vllm/mistralai/Ministral-8B-Instruct-2410`.
- `inspect_ai 0.3.260`, `inspect_evals 0.18.0`, provider `vllm`, grader
  `openrouter/openai/gpt-4.1-mini`.

No substitute corpus was used in their place. Other Inspect logs exist on the build
machine (`addition`, `gsm8k`, `humaneval`) and were deliberately **not** analysed:
swapping the corpus would answer a different question than the one registered.

---

## 5. Inspect evaluation logs — reasoning-capable models (this project's runs)

| | |
|---|---|
| Local path | `data/inspect-runs-reasoning/<arm>/` (gitignored) |
| Produced by | `scripts/run_reasoning_evals.sh`, 2026-09-12/13 |
| Route | OpenRouter (`openrouter/<vendor>/<model>`) |
| Benchmarks | `strong_reject` (313), `sycophancy` (250 of 4,882, `--sample-shuffle 42`), `xstest` safe (250) and unsafe (200) |
| Licence | Our run artefacts. The underlying models carry each vendor's own terms. |

Sample counts deliberately match the vLLM baseline in §4 exactly, so the two
corpora are comparable. Omitting sycophancy's `--limit 250` runs all 4,882
samples and produces a denominator that is **not** comparable; that mistake was
made and corrected during the build and is recorded in `BUILD_LOG.md`.

**Arms are the unit, not models.** `deepseek-v3.2` appears twice — once with
reasoning requested and once without — and `gpt-5-nano` appears at three
`reasoning_effort` levels. These differ by exactly the variable under study, so
the loader labels observations by the arm directory rather than the model id.
Grouping on the model id would pool them and destroy the comparison.

**Caveats.**
- Scoring is disabled (`--no-score`). We measure the reasoning channel, not
  benchmark performance, so no judge model is involved and no score is reported.
- Requests are bounded (`--timeout 120 --max-retries 3 --fail-on-error 0.05`).
  Samples that error contribute no assistant turn; the shortfall is counted by
  `InspectLogLoader.errored_samples()` and reported in `describe()`.
- Incomplete logs (a run still in progress) are excluded and counted, never
  partially included.

## 6. METR incident reports (source documents, not a corpus)

| | |
|---|---|
| Local path | `data/METR/` (gitignored) |
| `hugging-face-incident-report-aug-2026.pdf` | METR/Redwood, 26 Aug 2026, 91 pp |
| `risk-report-feb-mar-2026.pdf` | METR Frontier Risk Report, published 2026-05-19, 320 pp |

These are **published reports, not data we may redistribute**. They are held
locally only so that quotations transcribed into
`data/published_record/*.yaml` can be checked against their source.

`scripts/verify_citations.py` re-checks every transcribed row against these PDFs
and exits non-zero on a mismatch. As of 2026-09-13: **10 rows, 10 verified, 0
mismatches.** Verified pages: p.14, p.33, p.43, p.44 (HF report) and p.124
(Frontier Risk Report, INC-037, "Google DeepMind — hash-collision").

Verification changed the data. The seeded LIBRAW dyad was cited to p.43 and is
on p.44; both of its strings were **truncated** in the seed and were restored in
full. One codebook example was **withdrawn**: a fragment listed as
uninterpretable proved, in the source, to be an unambiguous request — the
ambiguity was created by the investigators' elision, not present in the
utterance.

## 7. Disclosure to third parties

Two kinds of corpus text leave this machine. Both are recorded here because an
unlicensed corpus does not stop being unlicensed when it is sent to an API.

**To OpenRouter (model vendors).** Only benchmark prompts from `strong_reject`,
`sycophancy` and `xstest`, which are public datasets. **No corpus text from
Mythos, collusion.wiki or WikiTactics is ever sent to any model API.**

**To the human annotator.** collusion.wiki revisions and edit summaries are sent
to one human coder, in the bundle built by `scripts/make_coder_bundle.sh`, for
the coding task only. The bundle carries a `LICENCE_NOTE.md` asking that it not
be redistributed, not be pasted into any chatbot or online tool, and be deleted
afterwards. Labels returned contain **no corpus text** — only an item id, a
one-letter code, a duration and a timestamp — so `results/annotations/` is
publishable.

**Never sent anywhere.** The Mythos transcript carries an explicit do-not-train
request and a canary GUID. `channels.detect.check_do_not_train` raises before
any model is loaded, and `tests/test_publication_safety.py` asserts the GUID
appears in no tracked file and nowhere under `results/` or `docs/`.

## 8. Human annotation outputs

| | |
|---|---|
| Local path | `results/annotations/` (**committed**) |
| Produced by | `scripts/annotate.py`, one file per coder per sample |
| Contents | item id, one-letter code, seconds taken, timestamp, codebook hash |

Committed because it contains no corpus text. Each record is tied to the
codebook hash it was coded under, and `cohens_kappa` refuses to compare records
coded against different codebook versions.

Samples are drawn deterministically from `(population, task, n, seed)` with the
population sorted by uid first, so a second coder provably receives the same
items and agreement is computed on matched pairs.

## Reuse and attribution

The statistics in `src/channels/_vendored_stats.py` are vendored from
**safety-eval-pipeline** (`https://github.com/Jangulo7/safety-eval-pipeline`, tag
`v1.1.0`), DOI `10.5281/zenodo.22182741`, MIT, same author. The gate contract, the
`unscored`-as-first-class-column discipline (renamed `uninspectable` here) and the
publication-safety machinery are reused as *designs* and reimplemented.
