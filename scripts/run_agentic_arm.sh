#!/usr/bin/env bash
# Long-horizon arm: emission across a MULTI-TURN agentic trajectory.
#
# Every other arm in this project is a 1-2 turn benchmark, which cannot speak to
# the setting the argument is about - an agent taking many actions. agentharm's
# BENIGN split gives genuine multi-step tool use with no sandbox and no
# dual-use content; the harmful split is deliberately not used, since the
# question here is channel observability, not harm.
#
# Two models, chosen to test different things:
#   gpt-oss-120b       emits raw reasoning - does coverage VARY by step?
#   gpt-5-nano medium  withholds it       - does redaction HOLD at every step?
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
  echo "### finished agentic arm $arm at $(date +%H:%M:%S)"
}

run_arm "gpt-oss-120b" "openrouter/openai/gpt-oss-120b"
run_arm "gpt-5-nano-medium" "openrouter/openai/gpt-5-nano" --reasoning-effort medium
echo "AGENTIC ARMS COMPLETE $(date +%H:%M:%S)"
