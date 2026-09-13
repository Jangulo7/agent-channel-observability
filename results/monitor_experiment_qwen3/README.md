# Powered monitor experiment — qwen3, reasoning-gated vs action-gated recall

The recall ceiling c·r₂ is arithmetic; Haiku could not power its consequence (48/50
refused). qwen3-32b complies with AgentHarm harmful and discloses raw CoT, so it does.
Two arms over the same 50 harmful behaviours, provider pinned, AgentHarm's own grader as
ground truth (positive = harmful-graded trajectory); two gpt-5-nano monitors per step,
one reading only reasoning, one only actions.

- `qwen3-on` — reasoning on (post-tool CoT readable 122/122): **42 positives**, refusal 0.10.
- `qwen3-nothink` — `/no_think` (post-tool CoT readable 12/130, i.e. dark): **38 positives**, refusal 0.28.

Regenerate: `scripts/run_monitor_qwen_arms.py` then
`scripts/run_monitor_experiment.py --logs data/monitor-experiment/agent-qwen3 --out results/monitor_experiment_qwen3`.

## Result — the coverage→recall link, measured

Cumulative recall by step (caught by step j / positives reaching step j):

| step | CoT visible | CoT dark | action visible | action dark |
|---|---|---|---|---|
| 0 | 0.929 | 0.000 | 0.476 | 0.263 |
| 1 | 0.952 | 0.000 | 0.690 | 0.605 |
| 2 | 1.000 | 0.062 | 0.828 | 0.750 |
| 3 | 1.000 | 0.167 | 0.909 | 0.708 |

Reasoning-monitor abstentions: 0/161 turns (visible) vs 144/155 (dark). The CoT monitor
catches 93% of harmful trajectories at the first step and 100% by step 2 when reasoning is
visible; 0% at step 0 and ≤17% through step 3 when it is dark — a drop of ~0.83–0.93. The
action monitor retains most of its recall in both arms because actions stay observable.

## Caveats

- **Not a perfectly clean A/B.** `/no_think` also raised refusals (0.10 → 0.28) and yields
  different trajectories (42 vs 38 positives), so the action-monitor difference between
  arms is partly a trajectory effect, not purely the channel. The CoT-monitor collapse is
  unambiguous and is the measured quantity.
- Monitor is `gpt-5-nano` (cheap); the visible-vs-dark contrast on the *same* monitor is
  the valid comparison. A stronger monitor might raise both columns.
- 38–42 positives; per-step n shrinks at late steps (low-n tail), so read the early steps.
- Harmful-split run is the authorised, logged §13 deviation; `/no_think` is a logged prompt
  manipulation; only counts, rates and verdicts are stored.
