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
| Local path | `data/german-collusion-wiki/full-wiki-logs/` (gitignored) |
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

## Reuse and attribution

The statistics in `src/channels/_vendored_stats.py` are vendored from
**safety-eval-pipeline** (`https://github.com/Jangulo7/safety-eval-pipeline`, tag
`v1.1.0`), DOI `10.5281/zenodo.22182741`, MIT, same author. The gate contract, the
`unscored`-as-first-class-column discipline (renamed `uninspectable` here) and the
publication-safety machinery are reused as *designs* and reimplemented.
