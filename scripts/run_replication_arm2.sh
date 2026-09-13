#!/usr/bin/env bash
# Replication, part 2: three further model families on agentharm_benign.
#
# Holding the TASK fixed and varying the MODEL is the test that decides whether
# the positional decline seen on gpt-oss-120b is a property of the task or was a
# single-arm artefact. Six families in total across the two scripts: OpenAI,
# Anthropic, Alibaba, Moonshot, MiniMax, NVIDIA.
#
# All three below were probed first and confirmed to return RAW reasoning; a
# model that withholds it (gpt-5-nano) cannot contribute to a coverage profile
# and is deliberately not included.
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

LOGROOT="data/inspect-runs-agentic"
N="${N:-50}"

run_arm() {  # arm model
  local arm="$1" model="$2"
  mkdir -p "$LOGROOT/$arm"
  echo "=== [$(date +%H:%M:%S)] $arm :: agentharm_benign n=$N ==="
  .venv/bin/inspect eval inspect_evals/agentharm_benign \
    --model "$model" --no-score --log-dir "$LOGROOT/$arm" \
    -T split=test_public --limit "$N" \
    --max-connections 6 --max-tokens 8192 \
    --timeout 180 --max-retries 3 --fail-on-error 0.1 2>&1 | tail -3
  echo "### finished replication arm $arm at $(date +%H:%M:%S)"
}

run_arm "kimi-k2-thinking" "openrouter/moonshotai/kimi-k2-thinking"
run_arm "minimax-m2"       "openrouter/minimax/minimax-m2"
run_arm "nemotron-3.5"     "openrouter/nvidia/nemotron-3.5-lightning"
echo "REPLICATION ARMS 2 COMPLETE $(date +%H:%M:%S)"
