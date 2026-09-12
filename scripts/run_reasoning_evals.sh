#!/usr/bin/env bash
# Emission measurement across reasoning-capable models via OpenRouter.
#
# Eight model arms x four task runs = 32 evals, 1,013 samples per arm,
# matching the sample counts of the existing vLLM baseline exactly so the two
# corpora are directly comparable.
#
# --no-score: we measure the reasoning channel, not benchmark performance.
#   Skipping the judge removes a cost and a dependency without touching any
#   number this project reports.
# --max-tokens 8192: a cap, not a charge. Generous so that a long chain of
#   thought is never truncated into a misleading state classification.
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

LOGROOT="data/inspect-runs-reasoning"
CONN="${CONN:-16}"
MAXTOK=8192

run_one() {  # arm_dir model task extra_args...
  local arm="$1" model="$2" task="$3"; shift 3
  local dir="$LOGROOT/$arm"
  mkdir -p "$dir"
  echo "=== [$(date +%H:%M:%S)] $arm :: $task ==="
  .venv/bin/inspect eval "inspect_evals/$task" \
    --model "$model" --no-score --log-dir "$dir" \
    --max-connections "$CONN" --max-tokens "$MAXTOK" \
    "$@" 2>&1 | tail -4
}

# arm_name|model|extra generate args
ARMS=(
  "gpt-oss-120b|openrouter/openai/gpt-oss-120b|"
  "qwen3-32b|openrouter/qwen/qwen3-32b|"
  "glm-4.7-flash|openrouter/z-ai/glm-4.7-flash|"
  "claude-haiku-4.5|openrouter/anthropic/claude-haiku-4.5|--reasoning-tokens 2048"
  "deepseek-v3.2|openrouter/deepseek/deepseek-v3.2|"
  "gpt-5-nano-low|openrouter/openai/gpt-5-nano|--reasoning-effort low"
  "gpt-5-nano-medium|openrouter/openai/gpt-5-nano|--reasoning-effort medium"
  "gpt-5-nano-high|openrouter/openai/gpt-5-nano|--reasoning-effort high"
)

for entry in "${ARMS[@]}"; do
  IFS='|' read -r arm model extra <<< "$entry"
  # shellcheck disable=SC2086
  run_one "$arm" "$model" "strong_reject" -T jailbreak_method=None -T epochs=1 $extra
  run_one "$arm" "$model" "sycophancy" $extra
  run_one "$arm" "$model" "xstest" -T subset=safe $extra
  run_one "$arm" "$model" "xstest" -T subset=unsafe $extra
  echo "### finished arm $arm at $(date +%H:%M:%S)"
done
echo "ALL ARMS COMPLETE $(date +%H:%M:%S)"
