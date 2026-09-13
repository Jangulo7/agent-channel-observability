# Long-horizon arm — SWE-bench Verified, does disclosure decay with depth?

**The transfer question the project could not previously answer.** Every earlier corpus
was short (median 4–5 assistant turns); nothing tested whether reasoning disclosure holds
over long agentic trajectories. This runs SWE-bench Verified (real repos in per-instance
Docker sandboxes) on three cheap open models, **scoring off** — the point is the
trajectory and its reasoning channel by step, not whether the bug was fixed. n = 10
instances per model (the same instances). Regenerate with `scripts/run_swebench_arm.py`
then `scripts/report_swebench_longhorizon.py` (`longhorizon.json`, counts only).

## Result

| model | n | median turns | max | censored at msg-limit | readable overall | steps 0–9 | steps 40+ |
|---|---|---|---|---|---|---|---|
| `nemotron-3.5-lightning` | 10 | 59 | 59 | 7/10 | **0.994** | 1.00 | 0.99 |
| `gpt-oss-120b` | 10 | 59 | 59 | 7/10 | **0.856** | 0.92 | 0.83 |
| `qwen3-32b` | 10 | 6.5 | 9 | 0/10 | 0.836 | 0.84 | — (never reaches) |

**What it shows.** For the two models that sustain long trajectories (median 59 assistant
turns, out to step 58), **reasoning disclosure does not collapse with depth.**
`nemotron-3.5` holds ~1.00 at every depth out to step 58; `gpt-oss-120b` dips mildly from
0.92 early to a ~0.83 plateau and stays there — a gentle reduction, not the decay-toward-
zero the original "coverage declines with depth" hypothesis feared. This is the project's
first evidence at this trajectory depth, and it is consistent with the revised thesis:
disclosure is largely a provider/configuration property, roughly stable across step
position for a given model, not a function of depth.

**`qwen3-32b` cannot test the question**: it submits in ~6 turns, so "cheap open model" is
not the same as "long-horizon-capable" — `gpt-oss-120b` and `nemotron-3.5` sustain long
SWE-bench runs, `qwen3-32b` does not.

## Caveats that must travel with the number

- **n = 10 trajectories per model**; per-step n ≤ 10, below `MIN_CELL_N = 30`, so per-step
  intervals are wide. This is **suggestive, not powered** — a direction, not an estimate.
- **7/10 trajectories are right-censored** at the 120-message limit (≈59 assistant turns),
  so the measured depth is a floor; these runs would go longer.
- **Scoring is off**: these are not necessarily *successful* trajectories, only long ones.
  The disclosure measurement does not depend on task success.
- Provider token accounting (`reasoning_tokens > 0`) tracks the readable classification on
  these arms; `by_step` in the JSON carries both.
