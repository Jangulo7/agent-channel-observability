#!/usr/bin/env bash
# Replication test for the positional decline.
#
# gpt-oss-120b on agentharm_benign showed coverage falling to 0.682 by step 5.
# gpt-oss-120b on intercode_ctf did NOT reproduce that: 0.933 at step 5, and its
# worst adequately-powered cell is 0.837. Same model, two task families,
# different answers - so the effect is either task-specific or noise.
#
# This arm holds the TASK fixed and varies the MODEL. If the decline reproduces
# on agentharm across three vendors, it is a property of the task and it is
# real. If it does not, the original result was a single-arm artefact and must
# be reported as one.
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

LOGROOT="data/inspect-runs-agentic"
N="${N:-50}"

run_arm() {  # arm model extra...
  local arm="$1" model="$2"; shift 2
  mkdir -p "$LOGROOT/$arm"
  echo "=== [$(date +%H:%M:%S)] $arm :: agentharm_benign n=$N ==="
  .venv/bin/inspect eval inspect_evals/agentharm_benign \
    --model "$model" --no-score --log-dir "$LOGROOT/$arm" \
    -T split=test_public --limit "$N" \
    --max-connections 8 --max-tokens 8192 \
    --timeout 180 --max-retries 3 --fail-on-error 0.1 \
    "$@" 2>&1 | tail -3
  echo "### finished replication arm $arm at $(date +%H:%M:%S)"
}

run_arm "claude-haiku-4.5" "openrouter/anthropic/claude-haiku-4.5" --reasoning-tokens 2048
run_arm "qwen3-32b" "openrouter/qwen/qwen3-32b"
echo "REPLICATION ARMS COMPLETE $(date +%H:%M:%S)"
