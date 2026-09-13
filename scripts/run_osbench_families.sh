#!/usr/bin/env bash
# Third task family: agent_bench_os - real OS/bash tasks in a Docker sandbox.
#
# Completes a 3-task x 6-model design:
#   agentharm_benign   mock tools, no sandbox
#   gdm_intercode_ctf  real shell, puzzle-oriented
#   agent_bench_os     real shell, ordinary system administration
#
# Three families matter because the first two disagreed: gpt-oss-120b declines
# on agentharm and does not on intercode_ctf. With one task per model a task
# effect and a model effect are indistinguishable; with three they are not.
#
# agentdojo was piloted and rejected - 2-4 turns per sample is too short to
# carry a positional profile.
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

LOGROOT="data/inspect-runs-osbench"
N="${N:-50}"

run_arm() {  # arm model extra...
  local arm="$1" model="$2"; shift 2
  mkdir -p "$LOGROOT/$arm"
  echo "=== [$(date +%H:%M:%S)] $arm :: agent_bench_os n=$N ==="
  .venv/bin/inspect eval inspect_evals/agent_bench_os \
    --model "$model" --no-score --log-dir "$LOGROOT/$arm" \
    --limit "$N" --max-connections 4 --max-tokens 8192 \
    --timeout 240 --max-retries 3 --fail-on-error 0.2 "$@" 2>&1 | tail -3
  echo "### finished osbench family $arm at $(date +%H:%M:%S)"
}

run_arm "gpt-oss-120b"     "openrouter/openai/gpt-oss-120b"
run_arm "kimi-k2-thinking" "openrouter/moonshotai/kimi-k2-thinking"
run_arm "claude-haiku-4.5" "openrouter/anthropic/claude-haiku-4.5" --reasoning-tokens 2048
run_arm "qwen3-32b"        "openrouter/qwen/qwen3-32b"
run_arm "minimax-m2"       "openrouter/minimax/minimax-m2"
run_arm "nemotron-3.5"     "openrouter/nvidia/nemotron-3.5-lightning"
echo "OSBENCH FAMILIES COMPLETE $(date +%H:%M:%S)"
