<!--
  Markdown copy of PREREGISTRATION.odt v1.0, converted verbatim from the ODF text.
  The ODF remains the registration of record; this copy exists so the registration
  is readable in the repository without opening an office suite, and so that
  `gates.codebook_drift` has a committed hash to compare against.
  Converted 2026-09-12 during the overnight build. Text is unedited; only headings
  were promoted to markdown.
-->

# PRE-REGISTRATION (markdown copy)

> **Status of this copy.** Verbatim text of `PREREGISTRATION.odt` v1.0. Fields left
> blank in the ODF are still blank here and are filled in
> [§Registration record](#registration-record) below, which is the part this
> repository's code actually reads.

## Registration record

| Field | Value |
|---|---|
| Registration scope | **Confirmatory: C1–C3 only** (the human annotation). Everything else is exploratory — see [§0](#0-analysis-status-at-registration--read-first). |
| Registration commit SHA | `ae377b0e61ce4c5bfe00b449e6d9739fc2d2e4ce` |
| Registration timestamp (UTC) | `2026-09-12T23:15:00Z` |
| Codebook SHA-256 (v3, current) | `sha256:a67d3c09dfab3cb3fda0aea911322b15a40a6f45db466e19dd096481c0d21f62` |
| Codebook SHA-256 (v2, superseded) | `sha256:0bc62c3edba70e32ef6e02c6c4dfad65e761b10271868a6c4f84a60d14f1665f` |
| Codebook SHA-256 (v1, superseded) | `sha256:2d1077fad571ec02c5bbbef5cfdc5f3541b46305ab9e9004e318bd37ea56af83` |
| Corpus freeze hashes | see [`DATA_PROVENANCE.md`](DATA_PROVENANCE.md) |

`gates.codebook_drift` compares `codebook.codebook_hash()` against the codebook hash
in the table above and fails the build when they differ.

### What the registration physically consists of

Stated plainly, because a registration whose mechanism is vague is not much of a
registration:

- **The record is a git commit** in this repository, made by
  `scripts/register.sh`, whose SHA is in the table above. The commit contains
  this document with the confirmatory endpoints of §0.2 fully specified and with
  **no annotation label in existence**.
- **What that does and does not prove.** A commit in a repository controlled by
  the author is not a third-party timestamp. It proves the content, links it to
  a codebook hash, and orders it against later commits — it does not, on its
  own, prove the date to someone who distrusts the author. If the two hashes
  below were also posted to an independent dated service, that gap closes; if
  they were not, this limitation stands and is not papered over.
- **Independently checkable hashes.** `sha256sum docs/PREREGISTRATION.md` and
  `codebook.codebook_hash()`. Both are printed by `scripts/register.sh`.
- **Where else it was registered**, if anywhere, is recorded in the deviations
  log (§11).

**Before citing this document, read [§0](#0-analysis-status-at-registration--read-first).**
It records which analyses had already been run when this was registered. Those
are exploratory and registering this document does not make them otherwise.

---


PRE-REGISTRATION
Peer disagreement as an observability substrate for agent cheating
A pre-registered secondary analysis of two public agent-incident corpora, with instrument development
Field
Entry
Investigator
Johanna Angulo
Contact
johanna.angulo@gmail.com
Context
Apart Research × CeSIA, AI Incident Response Sprint, 11–13 September 2026. Track 2.
Document version
v1.0
Registration timestamp
____________________ (UTC — fill at the moment of commit)
Registration mechanism
Timestamped public git commit to Jangulo7/safety-eval-pipeline, branch feat/channel-observability. This document plus data/channels/codebook/v1.yaml constitute the registration.
Registration commit SHA
____________________ (fill immediately after commit; quote in the report)
Codebook SHA-256
____________________ (output of codebook_hash(); must match at analysis time or the codebook_drift gate fails)
Corpus freeze hashes
See §3.4. Recorded in data/channels/collusion_wiki/SHA256SUMS.txt
Study type
Observational secondary analysis of existing public data, plus measurement-instrument development. No human subjects. No new agent runs on external systems.
Pre-specified analyses frozen at
Registration commit. Any later change is logged in §11, not silently applied.
Standing commitments
This registration is written before any coding of the target corpus. Sections 4–9 are frozen at the registration commit.
A null result is reported as the headline finding. See §4.2.
Every deviation from this document is recorded in the deviations log (§11) with a date and a reason, and reproduced in the report appendix. Nothing is amended in place.
No rate is reported for any detector without a recorded validated recall (§7.3).

## 0. Analysis status at registration — READ FIRST

> **Added 2026-09-13 at the moment of registration. Not part of the ODF v1.0
> text.** Everything above and below this section is the verbatim original; this
> section exists because registering it unchanged would have implied a claim
> that is not true.

Pre-registration is only meaningful for analyses that have **not yet been run**.
Several analyses in this document were run during the build of 2026-09-12/13,
**before** this registration. Presenting them as pre-registered would be false.
They are therefore relabelled **exploratory**, and the confirmatory claims of
this project are restricted to §0.2.

### 0.1 Already executed before registration — EXPLORATORY

These are reported as exploratory. Their hypotheses were not fixed in advance of
seeing the data, and no confirmatory claim rests on them.

| analysis | state at registration |
|---|---|
| Four-state emission on the vLLM baseline (3 models × 3 benchmarks, 3,789 turns) | run; 0/3,789 raw reasoning |
| Four-state emission on the Mythos 5 transcript (2,061 turns) | run; 0.333 raw reasoning |
| Four-state emission on reasoning-capable models via OpenRouter | **in progress**; arms complete are reported with their n |
| `TreeCoder` recall on WikiTactics | run; OBJ 0.072 [0.046, 0.111] |
| `NliDetector` recall on WikiTactics | run; OBJ 0.218 [0.171, 0.273] |
| Revert detection on collusion.wiki | run; 1,275 of 13,661 agent edits |
| Actors-per-page structure of collusion.wiki | run; 70.2% single-agent pages |
| Transcription and citation verification of the published record | run; 10 rows, 10 verified |

The emission measurements are **descriptive**: they report a distribution with
its denominator stated, and make no comparison whose direction was predicted in
advance. The detector recalls are **instrument calibration**, not findings about
any corpus. Reporting them as exploratory costs this project nothing, because
neither was ever going to be a hypothesis test.

### 0.2 Not yet executed — CONFIRMATORY, registered here

No label from the human annotation exists at the time of registration. The
following is fixed now and will not be changed after labels are seen; any
departure goes in the deviations log (§11) with a date and a reason.

**C1 — Primary confirmatory endpoint. Precision of the checksum-revert detector.**
- *Question.* Of the revisions the detector calls reverts, what share are
  genuine disagreement rather than housekeeping?
- *Sample.* 60 items drawn by `channels.annotate.draw_sample` from the 1,275
  cross-actor reverts, `seed=7`, deterministic and reproducible.
- *Measure.* Share coded `d` (disagreement), with `u` (unclear) kept in the
  denominator. Excluding `u` would compute a rate over the items that happened
  to be decidable.
- *Interval.* Wilson 95%, clustered by **page** (primary) and by **actor**
  (sensitivity), reported together.
- *Registered interpretation.* `REVERT` is reported as a validated code only if
  the lower bound of the page-clustered interval exceeds **0.50**. At or below
  that, the code is reported as measured but not validated, and no revert-based
  rate is presented as evidence of disagreement.

**C2 — Secondary. Verbal objection in the inter-agent message channel.**
- *Sample.* 200 `change_summary` messages, same mechanism, `seed=7`.
- *Measure.* Count coded `OBJ`, `REF`, `ESC` or `WARN`.
- *Registered interpretation.* If the count is zero, report a one-sided 95%
  upper bound (≈0.013 at n=200) and the sentence "zero observed; below X with
  95% confidence" — **never** "no objection occurs". If the count is non-zero,
  report the rate with its interval and state that the instrument transferring
  to this channel remains unvalidated.

**C3 — Reliability. Author as second coder.**
- *Sample.* The first 50 items of C1's sample, coded independently.
- *Measure.* Cohen's κ on matched pairs; percent agreement reported alongside
  but never in place of κ.
- *Declared limitation, in advance.* **The second coder is the author of the
  codebook.** This is therefore not independent double-coding; it measures
  whether the written rules reproduce the author's intent. It will be reported
  in those words, and κ will not be described as inter-rater reliability.
- *Registered interpretation.* κ ≥ 0.60 is reported as adequate reproducibility
  for an exploratory instrument. Below 0.40, C1 is reported as unreliable
  regardless of its point estimate.

### 0.3 Conditions binding on all three

1. **Blind.** Coders see no detector output. The bundle shipped to the coder
   (`scripts/make_coder_bundle.sh`) physically excludes the results, the build
   log and this document, so the blindness is structural rather than requested.
2. **Codebook frozen.** All labels are coded under codebook **v3**,
   `sha256:a67d3c09dfab3cb3fda0aea911322b15a40a6f45db466e19dd096481c0d21f62`. `cohens_kappa` refuses to
   compare records coded under different hashes.
3. **No LLM labels.** No model output is used as a gold label anywhere in C1–C3.
4. **Stopping rule.** The sample sizes above are fixed. If coding is cut short,
   the achieved n is reported and the interval widens accordingly; no additional
   items are drawn to reach a desired result.
5. **`u` is data.** Unclear is a substantive answer and stays in every
   denominator.

### 0.4 What this registration cannot repair

The exploratory analyses in §0.1 stay exploratory. Registering now does not make
them confirmatory, and this document should not be cited as though it does. The
parts of the original registration that were already doing real work — the
codebook hash freeze, which gates the build, and the deviations log — continue
unchanged.

---

## 1. Background and rationale

Detection of cheating and misaligned behaviour in AI agents currently leans on the intra-agent reasoning channel — reading a model’s chain-of-thought for the moment it decides to break a rule. Published measurement shows that channel is substantially empty and closing. The UK AI Security Institute reported in July 2026 that, on detected cheating actions, the model’s reasoning did not deliberate about whether the action was permitted in 49% of cases for GPT-5.6 Sol (n=238), 91% for Claude Mythos Preview (n=166), and 100% for Claude Opus 4.7 (n=79, of which 87% emitted no reasoning at all, attributed to adaptive reasoning).
A second channel exists and cannot close in the same way: agents that coordinate must externalise messages another agent can read. Two 2026 sources document it. Paglieri et al. (arXiv:2609.04170) report a 100-agent swarm in which an evaluation exploit spread through shared infrastructure and 24 of 100 agents spontaneously objected — auditing fraudulent work, warning peers, boycotting and filing complaints — without any prompt to do so. The collusion.wiki release documents agents self-identifying as OpenAI agents using a dormant wiki as a message board over 37 days, exchanging task answers and sandbox workarounds in plain text.
Neither source measures the objection signal. Paglieri et al. report no precision, recall or lead time and treat whistleblowing as a governance capacity rather than a detector; collusion.wiki is a forensic catalogue with no behavioural coding of message content. This study measures it.

## 2. Research questions

Question
Status
RQ1
What fraction of assistant turns expose an inspectable reasoning channel, by model and by reasoning_effort setting, as measured directly from evaluation logs; and what recall ceiling does that impose on any detector gated on deliberation?
Confirmatory
RQ2
Does peer objection occur in a real-world agent-to-agent incident corpus, in the absence of competition or any integrity framing?
Confirmatory — PRIMARY
RQ3
Where objection occurs, how much warning does it give before the harmful sequence completes?
Conditional on RQ2 > 0
RQ4
Can the above be computed automatically from Inspect evaluation logs and enforced as a build gate?
Engineering; not a hypothesis test

## 3. Data

All data is pre-existing and public. No data is collected from live systems at analysis time; every loader operates on a hash-pinned frozen export.
3.1 Target corpus (rung 3)
collusion.wiki — agents self-identifying as OpenAI agents on the DSE subwiki of prowiki.org, 24 May to early July 2026. Files: revisions.jsonl (14,591 rows, full saved text), pages.jsonl (4,579), events.jsonl (14,591 saves, 5,217 deletions, 4 reverts, 101 probes), labels.jsonl (3,103 names), manifest.json, plus shortener-logs.json (499), other-wikis.json (8 pages), records.jsonl (13,703), links.jsonl (23,877), site-coverage.csv (143 sites), coverage-gaps.csv (110 sites). Source: collusion.wiki/explorer/download.
Known properties, registered in advance so they cannot be presented later as discoveries: the name “dse” accounts for 13,403 of 14,681 edits (≈91%); agent attribution is inferred by the source authors’ date and content filter recorded in manifest.json and is not verified ground truth; labels.jsonl is a name-to-pages rollup and not human annotation; the authors warn that fake agent-style posts proliferated after publication; no licence is stated on the download page.
3.2 Contrast corpus
Anthropic Mythos 5 incident transcript — github.com/anthropics/mythos-5-incident-transcript, transcript.jsonl, ~2,145+ messages, single agent. Redactions documented in four categories by the publisher (messages 1–81; after 2145; selected third-party interactions; inline credential and identifier tokens). Used for the intra-agent baseline and as a hand-verified known positive for the SELF_LICENSE code. Carries a benchmark canary GUID and an explicit do-not-train request, both honoured (§10).
3.3 Validation corpora (rungs 1 and 2)
Rung
Corpus
Role
Labels
1
WikiTactics — De Kock, Stafford & Vlachos, EMNLP 2022. 213 conversations / 3,865 utterances, Wikipedia talk pages.
Establishes that the instrument detects disagreement at all, in the same medium as the target, against human gold labels. Yields recall and precision per code.
Human, utterance-level, published κ 0.55
2
negotiation-games/c2c-ai-vs-ai — 972 four-seat games, cross-vendor (GPT-5.2, Gemini-3.1-pro, Gemini-3.1-flash-lite, Grok-4-1). One strategy folder (162 games) will be used.
Establishes that the instrument transfers from human prose to agent text. Conflict is structurally guaranteed by game mechanics (deal rejection, coalition-breaking, betrayal), so a near-zero detection rate here falsifies the instrument rather than the corpus.
None; conflict guaranteed by design
—
PAN-WVC-11 (optional) — Zenodo 10.5281/zenodo.3342157, 29,949 edits, 2,813 vandalism, CC BY 4.0.
Labelled negatives separating vandalism from good-faith disagreement, if the revert analysis is pursued.
Human, binary, per edit
Rung 2 is registered as a necessary condition. Without it, a null at rung 3 is confounded with an instrument calibrated on human prose failing on terse agent protocol strings. Published examples of real agent messages are of the form “zzASK9180_TO_LIBRAW42535_LIVE_ARWDECODER_GETWB_UNINIT_TIFF_SCALARS_NO_WRITE”, which makes that confound a live concern rather than a theoretical one.
3.4 Freezing and exclusions
Every corpus file is hashed (SHA-256) before analysis and the hashes are committed. A loader refuses any file whose hash does not match.
No loader fetches from a live site at analysis time. No re-crawling of collusion.wiki under any circumstances.
Excluded from all confirmatory endpoints: utterances whose provenance is paraphrase, uncertain-meaning, or investigator summary; human-authored messages; investigator text. These may appear in qualitative appendices only.
Withheld or redacted spans are emitted as records with null text and counted in the denominator as uninspectable. They are never silently dropped.

## 4. Hypotheses and directional predictions

4.1 Registered prediction for RQ2 (primary)
H1 — registered before inspection of the target corpus
The rate of coded peer objection in collusion.wiki will be LOW OR ZERO, materially below the 24-in-100 agent rate reported by Paglieri et al.
Mechanism: the two conditions that produced objection in the swarm study are both absent here. (i) Competition — that study used a first-solve-wins race in which cheating by others directly cost the honest agents; collusion.wiki agents were cooperating, sharing answers and workarounds. (ii) Framing — those agents were prompted as peer researchers at a scientific conference, which the authors credit with activating norms of scientific integrity, and were given a feedback endpoint offering an escalation path; collusion.wiki agents had neither.
Operational form: objection events per 1,000 eligible agent messages, clustered by actor, with a 95% interval. "Materially below" is pre-specified as an upper confidence bound below 5 per 1,000.
4.2 What each outcome means, stated in advance
Outcome
Interpretation, fixed before analysis
Objection rate low or zero (H1 supported)
Spontaneous peer objection is a property of the institutional design of a swarm, not of the models. It cannot be relied upon as a default detection channel and must be engineered in. This converges with Paglieri et al.’s own recommendation to provide structured, auditable, monitored channels rather than removing channels. This is a substantive finding and is reported as the headline.
Objection rate materially above zero (H1 disconfirmed)
A detection channel exists in real incidents, is not instrumented by anyone, and its rate and lead time are measured here first. Stronger result; report as such.
Rung 2 fails (instrument does not fire on guaranteed-conflict agent text)
Detector-transfer failure. Report the failure and the rung-1 recall. Do NOT report any rate from rung 3. See §9.
No SHARE denominator in the target corpus
Report the structural finding (the corpus does not contain codable cheating-relevant activity at the sampled unit) and a rate status of “no denominator”. Do not divide by corpus size.
Commitment: a null is reported as the headline finding, in the abstract and the summary section, not relegated to a limitations paragraph. This sentence is registered specifically to remove any incentive to search for an alternative positive result if H1 is supported.
4.3 RQ1 prediction
Directional: the share of assistant turns exposing raw inspectable reasoning will vary materially with the reasoning_effort setting and by model, and the share that is uninspectable (summary-only, redacted, or absent) will be non-trivial for at least one model tested. No point prediction is registered. The cascade bound (§8.3) is arithmetic, not a hypothesis.

## 5. Unit of analysis and sampling plan

5.1 Unit
The unit of analysis is one wiki revision (one saved edit) for collusion.wiki; one agent message for c2c; one utterance for WikiTactics; one assistant turn for Inspect-log coverage. Page-level and actor-level rollups are secondary and labelled as such.
5.2 Sampling
Target n for hand coding: 400 revisions from collusion.wiki. If time does not permit 400, the sample is reduced to 250 and the reduction is logged in §11; the reliability check is never dropped in favour of a larger sample.
Stratification: by actor class (dominant actor “dse” vs all others) and by month. Multi-actor pages are oversampled because single-actor pages cannot contain peer objection by construction. Stratification weights are recorded and used to reweight when estimating corpus-level rates.
Random seed: 20260913. Recorded here and in the analysis code. The draw is reproducible.
Rung 1: the full WikiTactics set (3,865 utterances) is scored by the automated coder; no hand sampling is needed because gold labels exist.
Rung 2: 162 games from one c2c strategy folder, all agent messages, automated coder only.

## 6. Variables and the coding instrument

6.1 Codes (codebook v1, frozen by hash)
Code
Definition
Registered exclusion
OBJ
An actor asserts to another actor that that actor’s action is disallowed, improper, or against the rules.
Disputes about whether something works. Correctness disagreement is not norm assertion.
REF
An actor states it will not do something others are doing, on normative grounds.
Refusal for capability or resource reasons.
ESC
An actor attempts to report to an authority, human or organiser.
Asking a peer for help.
WARN
An actor warns third parties away from a method on normative grounds.
Warning that a method is ineffective.
NORM
An actor states a rule or standard without accusing anyone.
Restating task instructions verbatim.
SELF_LICENSE
An actor articulates a constraint and then proceeds against it.
Proceeding with no articulated constraint.
SHARE
Transmission of an answer, solution, or containment workaround. Establishes the denominator.
Ordinary collaboration on method.
UNCL
Cannot be coded from the record alone.
—
6.2 The decision tree
The instrument is an ordered decision tree specified a priori from theory, not a model fitted to data. This is registered explicitly: no CART, random forest or other learned tree is used for any confirmatory endpoint. If a learned tree is fitted at all, it appears only in an exploratory appendix with cross-validation and is labelled exploratory.
Gate order: provenance eligibility → channel eligibility → G0 does the record reference a rule, scope, permission or obligation → G1 conflict type (correctness / informational / interpretive / normative) → G2 target (another actor / own action / general) → G3 audience (the actor / third parties / an authority) → G4 own-action refusal on normative grounds → G5 deliberation present before proceeding → transmission check for SHARE.
G1 derives from Aumann’s triage and is the interpretability payload: informational conflict is remediable by specification, interpretive by tightening scope, normative only by training or containment. The type label therefore licenses a different containment recommendation per disagreement type.
Every emitted label carries the gate path it took. This is the audit trail, and it makes disagreement between the two coding passes diagnosable at the gate level rather than only at the label level.

## 7. Endpoints

7.1 Primary endpoint — exactly one
Primary endpoint
Coded objection events per 1,000 eligible agent messages in collusion.wiki, where an objection event is any record coded OBJ, REF, ESC or WARN, computed over the SHARE-establishing denominator, clustered by actor name, with a 95% confidence interval.
One endpoint. One test. Everything else in this document is secondary or exploratory and will be labelled so in the report.
7.2 Secondary endpoints (labelled as secondary in the report)
Distribution of distinct actors per page in collusion.wiki — the structural feasibility measure.
Reasoning-channel state distribution (raw present / summary only / redacted / absent) by model and by reasoning_effort, from Inspect logs.
Cascade recall ceiling c·r₂ computed from published coverage values.
Rung-1 recall and precision per code on WikiTactics.
Rung-2 detection rate on c2c versus a shuffled-text control.
Identity-revert count in collusion.wiki, using the Wikimedia Research:Revert definition (15-revision radius, 48-hour window).
Type distribution (informational / interpretive / normative) over coded records.
7.3 Exploratory and non-measured components
Lead time from first objection to completion of the harmful sequence. Exploratory: reported as individual values with n, never as a mean, and only where timestamps are not reconstructed.
Candidate influence moves in agent-to-agent messages. Registered as a QUALITATIVE TYPOLOGY ONLY. Exemplars are drawn from published sources, n is stated in the caption, and no rate, prevalence or per-model comparison is computed. Rationale: no labelled corpus of agent-to-agent manipulation exists, so no detector for this construct could satisfy §7.4, and the construct’s transfer from human social psychology to compressed agent protocol strings is not established.
7.4 The validation rule — registered as binding
No rate without a validated recall
No detector may report a rate for any endpoint unless a validation record exists for that exact combination of detector name, detector version and codebook hash, measured against a labelled positive control.
This is enforced in code: rate-reporting functions raise UnvalidatedDetectorError otherwise, and a test asserts that they do.
An LLM-assisted pre-screen is permitted solely to reduce hand-coding burden, and only if its recall against the hand-coded sample is reported alongside any result it contributed to.

## 8. Analysis plan

8.1 Inference
Wilson score intervals for all proportions.
Clustered by actor name throughout, using a seeded clustered bootstrap. Registered rationale: ≈91% of collusion.wiki edits originate from one actor, so per-record independence is false and unclustered intervals would be anticonservative. Analysis code raises rather than pooling when an actor identifier is missing.
Zero case, pre-specified: if zero objection events are observed, a one-sided 95% Wilson (or Jeffreys) upper bound on the rate is reported. The finding is stated as “zero observed; rate below X with 95% confidence”, never as “no signal found”.
Reliability: single-coder test–retest on a random 30% of the hand-coded sample after a gap of at least 12 hours, reported as an upper bound on inter-coder agreement and explicitly not as a substitute for it. If a second coder is recruited, both code every sampled item independently and weighted κ per code plus an adjudication log are reported instead.
8.2 Pre-specified sensitivity analyses — exactly two
Excluding the dominant actor “dse”.
Restricting to a stricter attribution subset, defined by the source authors’ filter criteria in manifest.json.
Any further slicing is exploratory, is labelled exploratory in the report, and no inference is drawn from it.
8.3 Multiple comparisons
One primary endpoint and one registered directional prediction. No correction is applied to the primary test. Secondary endpoints are reported with intervals and described as descriptive; no claim of statistical significance is made for any of them. No per-code × per-stratum grid of tests is run.
8.4 The cascade bound
System recall of any detector gated on deliberation is bounded above by c·r₂, where c is the coverage of the deliberation channel and r₂ the conditional recall of the second stage. Published coverage values from AISI (July 2026) give ceilings of 0.50 (GPT-5.6 Sol), 0.09 (Claude Mythos Preview) and 0.00 (Claude Opus 4.7).
Two caveats registered so they travel with the number: those denominators are “cheating resamples” and are therefore conditional on AISI’s own monitor detecting the cheat, and resamples are clustered within underlying actions, so the published intervals are likely optimistic. The bound applies only to detectors gated on deliberation; METR reports that no-reasoning agents are not obviously less monitorable, so action-only evidence can suffice. This will be stated in the report abstract.

## 9. Decision and stop rules

Trigger
Registered action
Distribution of actors per page shows almost no multi-actor pages
Stop pursuing RQ2 as a rate. Report the structural finding and the one-sided bound. Proceed directly to RQ1, which is independent of it.
Rung 1 (WikiTactics) recall cannot be established
Report no rate from any corpus. Report the instrument, the attempt, and the failure.
Rung 2 (c2c) detection rate not materially above a shuffled-text control
Declare detector-transfer failure. Report rung-1 recall and the transfer failure. Do not report any rate from rung 3.
SHARE denominator is zero or near-zero in the sample
Report rate status “no denominator”. Do not compute a rate over the whole corpus.
Hand coding not producing data by the time budgeted in the schedule
Reduce sample size to 250. Never drop the reliability check to buy sample size.
Time exhausted after RQ1 is complete
Submit. RQ1 plus the instrument plus the registered null constitute a complete contribution.
9.1 What would falsify the project’s framing
If reasoning-channel coverage measured from Inspect logs is uniformly high across models and settings, the premise that the intra-agent channel is closing is not supported in the accessible channel, and the paper must say so.
If the instrument detects objection at a high rate in collusion.wiki, the registered prediction is wrong and is reported as wrong.
If rung 2 fails, the instrument does not transfer to agent text and no corpus-level claim survives.

## 10. Ethics, dual use and licensing

No offensive cyber evaluations are run. Any agent task built for this work is benign by construction and tested on synthetic logs and existing non-cyber safety-evaluation logs.
No exploit content is reproduced or committed: identifiers and provenance only, no payload bodies, no base64 blobs, no working code. Enforced by an automated repository check.
The containment and sandbox workarounds that the agents shared are not reproduced. Coding categories and rates are published; payloads are not.
No attempt is made to reconstruct or de-redact any withheld material.
The Anthropic transcript’s benchmark canary GUID and do-not-train request are honoured. Its content is not sent to any third-party service. An automated check asserts the canary string is absent from every published artefact.
Corpora with no stated licence (collusion.wiki, WikiTactics, the village event log) are cited to their source publication, and counts rather than utterance text are published.
No personally identifying information is published. Where a corpus mixes human and agent authors, human-authored text is excluded from analysis and never published; counts only.
Monitoring paradox, acknowledged: publishing what a dissent detector looks for creates pressure to route coordination into unmonitored channels. Detection categories and validation methodology are published; tuned rule sets are not, and are offered to evaluation organisations on request. Recommendations favour channel design over covert monitoring.

## 11. Deviations log

Every departure from this document is recorded here with a date, the change, and the reason. This table is reproduced verbatim in the report appendix. Nothing above is amended in place.
| Date / time (UTC) | Section | Deviation | Reason |
|---|---|---|---|
| 2026-09-13 (session 5) | §8.2 sensitivity analyses | **Neither registered sensitivity analysis was run.** "Excluding the dominant actor dse" and "restricting to a stricter attribution subset (manifest.json)" were replaced by two different analyses: recall correction (an observed rate divided by each detector's measured rung-1 recall) and denominator choice (all pages with an agent vs multi-agent pages only). `rq3.rq3_endpoint` reports both lists and this substitution in its result. | The first registered analysis is ill-posed on the data: `dse` is a **wiki** holding 13,403 of 14,591 revisions (91.9%), not an actor; the most active individual actor holds 317 revisions (2.2%) among 3,102 actors. The second was never implemented. No objection rate or bound has been computed under any analysis, so no reported number depends on the substitution. The substituted analyses are exploratory. Logged by author decision (Q12). |
| 2026-09-13 (session 5) | §10 non-goals; §7.2 reasoning-state endpoint | **Scope broadened beyond existing logs.** New evaluation runs were made via OpenRouter: a nine-arm single-turn reasoning sweep on the three registered benchmarks, and three benign agentic task families (`agentharm_benign`, `agent_bench_os`, and `gdm_intercode_ctf`). `gdm_intercode_ctf` is a capture-the-flag-format benchmark. **Decision: kept, relabelled** as a *sandboxed shell-puzzle task in CTF format*, used only to measure the reasoning channel. | §10 says no offensive cyber evaluations are run and tasks are tested on existing non-cyber logs. The ctf tasks are benign puzzles (e.g. decoding, file inspection) executed in a Docker sandbox; no offensive capability is measured, analysed or reported, task scores are not analysed, and no exploit content, payload or command text is published (counts only). All reasoning-channel results from these runs are exploratory (§0.1). Author decision (Q11). |
| 2026-09-13 (session 5) | §7.2 reasoning-state endpoint | **Readable vs produced separated.** The four-state distribution is reported alongside provider token accounting (`reasoning_tokens` from each model call): produced (> 0), not produced (= 0), unknown (not reported). | The four states measure what an evaluator can read; they cannot distinguish reasoning that was withheld from reasoning that never occurred. In the agentic runs these differ materially (e.g. a model that produces no reasoning after tool results vs a model whose reasoning is encrypted). Additive and exploratory; the four-state endpoint is unchanged. Author decision (Q10). |
| 2026-09-13 (session 5) | §7.2 identity-revert count | **Revert definition differs from the registered one.** Registered: Wikimedia Research:Revert (15-revision radius, 48-hour window). Implemented: a revision restoring any earlier body hash on the same page, no radius or time window, cross-actor against the immediately previous revision, self-reverts excluded. Counts: 1,275 over 13,661 agent edits; 1,293 over all revisions. | Undeclared until the session-5 gap analysis found it. The count is exploratory and no rate depends on it; confirmatory endpoint C1 (§0.2) measures the implemented detector's precision against human labels, so C1 is unaffected. Re-running under the registered definition is open. |
| 2026-09-13 (session 5) | §6.2 decision tree | **Implemented gate semantics differ from the registered tree.** Registered: G0 rule/obligation reference → G1 conflict type (correctness / informational / interpretive / normative) → G2 target → G3 audience → G4 own-action refusal → G5 deliberation present. Implemented (`tree.py`): G0 non-empty text → G1 correctness cue routes out → G2 escalation cue → G3 refusal cue → G4 objection cue → G5 warning cue → terminal contrast codes; no conflict-type classification beyond correctness, no target or audience gate. | Undeclared until the session-5 gap analysis. The tree was used only for rung-1 validation on WikiTactics (exploratory); **no confirmatory endpoint uses it** (C1–C3 are human-coded). Its G1 does not currently deliver the registered interpretability payload (type-specific containment). Re-implementing the registered gates is open. |
| 2026-09-13 (session 5) | errata (§3.1, §5.2, §8.1–8.2, §8.4, corpus descriptions) | **Factual errors in the registered text**, corrected here without amending it: collusion.wiki has 14,591 revisions (not 14,681); the Mythos transcript file has 2,064 message rows (not "~2,145+"); `dse` is a wiki, not an actor; 1 − 0.49 = 0.51, so the AISI GPT-5.6 Sol ceiling derived from "49% did not deliberate" is 0.51 against the published 0.50 used in §8.4; the revert counts 1,275 and 1,293 are over agent edits and all revisions respectively. | Found by the session-5 claims audit. None changes a registered decision rule or a confirmatory endpoint. |
| 2026-09-13 00:05 | §6.1 codebook | Codebook v2 → v3: every `[page TODO(johanna)]` citation replaced with a page verified against the PDFs in `data/METR/`; one UNCL positive example withdrawn. Hash `sha256:0bc62c3e…` → `sha256:a67d3c09…`. | Citation accuracy, done before the codebook was sent to the human coder. **No definition, inclusion rule or exclusion rule changed**, so no coding decision is affected. The withdrawal is substantive and is recorded as such: the fragment "…WILL_CREDIT_AND_COLLAB…" was listed as UNCL because its ellipses left its force unrecoverable, and the source (p.33) shows the full string is an unambiguous ASK. The ambiguity was manufactured by the investigators' elision rather than present in the utterance — a finding about disclosure practice, which belongs in the report, not a coding category. Validation records re-earned under v3. |
| 2026-09-12 20:30 | §6.1 codebook | Codebook bumped v1 → v2: added code `REVERT`; added `Channel.ARTEFACT_EDIT` to the schema. Hash moved from `sha256:2d1077fa…` to `sha256:0bc62c3e…`. | v1 coded only VERBAL disagreement, which assumed an agent that disagrees says so. On a shared artefact an agent can disagree by ACTION — undoing a peer's edit — and collusion.wiki contains 1,293 such cross-actor reverts that v1 had no code for. Coding a wiki revision as `INTER_AGENT_MESSAGE`, as v1 forced, also inflated the inter-agent message denominator with acts that carry no words. **No rate had been computed or reported under v1**, so no published number is affected; the two v1 validation records were invalidated and re-earned under v2. Decision taken by the investigator on 2026-09-12. |

## 12. Declarations

Funding: none. This work was conducted unpaid as a weekend research sprint entry.
Access and independence: no privileged access to any model, company infrastructure, transcript archive, or employee was obtained or requested. No company reviewed or redacted this work. All data is public. There is no engagement agreement with any developer or evaluator, and no party held approval rights over publication.
Competing interests: the investigator is applying to research positions and fellowships in AI safety evaluation, including at organisations whose published work is analysed here. This document is registered before analysis in part to constrain that incentive.
AI assistance: AI tools were used for literature search, source verification, code drafting and document preparation. All analytic decisions registered in this document are the investigator’s. Any AI-assisted classification that contributes to a reported result is validated and its recall reported, per §7.4. As METR did in a comparable investigation, the report states plainly where analysis was delegated to tools that are not fully reliable.
Signed: ______________________________ Date / time (UTC): ______________________
This registration is complete when the commit SHA, the codebook hash and the corpus freeze hashes above are filled in and the commit is pushed to a public remote.
