#!/usr/bin/env bash
# Within-model control: is ABSENT a capability limit or a configuration choice?
#
# deepseek-v3.2 at its DEFAULT config returns no reasoning block at all
# (rtok=0). The same model, same prompts, same provider, with reasoning
# explicitly enabled returns raw chain-of-thought. Running both arms turns
# "this model does not emit reasoning" into "this REQUEST did not ask for it",
# which is the difference between a capability claim and a disclosure claim.
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

LOGROOT="data/inspect-runs-reasoning"
CONN="${CONN:-12}"
MODEL="openrouter/deepseek/deepseek-v3.2"

run_one() {
  local arm="$1" task="$2"; shift 2
  mkdir -p "$LOGROOT/$arm"
  echo "=== [$(date +%H:%M:%S)] $arm :: $task ==="
  .venv/bin/inspect eval "inspect_evals/$task" \
    --model "$MODEL" --no-score --log-dir "$LOGROOT/$arm" \
    --max-connections "$CONN" --max-tokens 8192 "$@" 2>&1 | tail -3
}

ARM="deepseek-v3.2-reasoning-on"
run_one "$ARM" strong_reject -T jailbreak_method=None -T epochs=1 --reasoning-tokens 2048
run_one "$ARM" sycophancy --reasoning-tokens 2048
run_one "$ARM" xstest -T subset=safe --reasoning-tokens 2048
run_one "$ARM" xstest -T subset=unsafe --reasoning-tokens 2048
echo "### finished arm $ARM at $(date +%H:%M:%S)"
