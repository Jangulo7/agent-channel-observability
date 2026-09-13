#!/usr/bin/env bash
# intercode_ctf across the same six model families already run on agentharm.
#
# This completes a 2-task x 6-model design. With only one task per model we
# could not tell a task effect from a model effect; agentharm alone showed four
# different positional shapes, and intercode_ctf on gpt-oss-120b did not
# reproduce that model's decline. Running every family on both tasks is what
# separates the two explanations.
#
# agentdojo was piloted as a third family and rejected: 2-4 turns per sample is
# too short to carry a positional profile at all.
#
# NOTE: no --no-score here. This task's SOLVER calls score() to detect the flag.
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

LOGROOT="data/inspect-runs-ctf"
N="${N:-50}"

run_arm() {  # arm model extra...
  local arm="$1" model="$2"; shift 2
  mkdir -p "$LOGROOT/$arm"
  echo "=== [$(date +%H:%M:%S)] $arm :: intercode_ctf n=$N ==="
  .venv/bin/inspect eval inspect_evals/gdm_intercode_ctf \
    --model "$model" --log-dir "$LOGROOT/$arm" \
    --limit "$N" --max-connections 6 --max-tokens 8192 \
    --timeout 240 --max-retries 3 --fail-on-error 0.2 "$@" 2>&1 | tail -3
  echo "### finished ctf family $arm at $(date +%H:%M:%S)"
}

run_arm "kimi-k2-thinking"  "openrouter/moonshotai/kimi-k2-thinking"
run_arm "claude-haiku-4.5"  "openrouter/anthropic/claude-haiku-4.5" --reasoning-tokens 2048
run_arm "qwen3-32b"         "openrouter/qwen/qwen3-32b"
run_arm "minimax-m2"        "openrouter/minimax/minimax-m2"
run_arm "nemotron-3.5"      "openrouter/nvidia/nemotron-3.5-lightning"
echo "CTF FAMILIES COMPLETE $(date +%H:%M:%S)"
