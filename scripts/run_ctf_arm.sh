#!/usr/bin/env bash
# Longest-horizon arm: a real shell in a Docker sandbox, up to 50 messages.
#
# agentharm gives genuine multi-step tool use but caps out around 9 turns.
# gdm_intercode_ctf gives the agent a real filesystem and shell and lets it run
# up to 50 messages, which is the closest thing in reach to the setting the
# argument is about.
#
# NOTE: --no-score is NOT passed here, unlike every other arm. This task's
# SOLVER calls score() internally to decide whether the agent has found the
# flag; suppressing scoring makes the run error out. Its scorer is a local
# string check, not a model, so this costs nothing and involves no judge.
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
    --timeout 240 --max-retries 3 --fail-on-error 0.2 \
    "$@" 2>&1 | tail -3
  echo "### finished ctf arm $arm at $(date +%H:%M:%S)"
}

run_arm "gpt-oss-120b" "openrouter/openai/gpt-oss-120b"
echo "CTF ARM COMPLETE $(date +%H:%M:%S)"
