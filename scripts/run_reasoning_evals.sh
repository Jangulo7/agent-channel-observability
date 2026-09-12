#!/usr/bin/env bash
# Emission measurement across reasoning-capable models via OpenRouter.
#
# SAMPLE COUNTS MATCH THE vLLM BASELINE EXACTLY, which is the whole point of the
# comparison. Read from the baseline logs' eval config rather than assumed:
#   strong_reject  313  (full dataset, no limit)
#   sycophancy     250  of 4,882 -> REQUIRES --limit 250 --sample-shuffle 42
#   xstest safe    250  (full subset)
#   xstest unsafe  200  (full subset)
# Omitting sycophancy's limit runs all 4,882 samples: ~20x the cost and time,
# and a denominator that is not comparable with the baseline. That mistake cost
# an hour on 2026-09-12 and is why the limits are written down here.
#
# Resumable: an (arm, task, subset) whose log already exists is skipped, so a
# killed run does not repeat finished work.
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

LOGROOT="data/inspect-runs-reasoning"
CONN="${CONN:-16}"
MAXTOK=8192

# Skip if a COMPLETE log for this arm/task/subset already exists.
#
# Both xstest subsets write files named *_xstest_*.eval, so the filename cannot
# distinguish them. The subset lives in the log's task_args, so that is what is
# checked - matching on the filename would silently treat "safe" as "unsafe".
already_done() {  # arm task subset
  local dir="$LOGROOT/$1"
  [ -d "$dir" ] || return 1
  .venv/bin/python - "$dir" "$2" "$3" <<'PYCHECK'
import sys
from pathlib import Path
from inspect_ai.log import read_eval_log

directory, task, subset = sys.argv[1], sys.argv[2], sys.argv[3]
for path in Path(directory).glob("*.eval"):
    try:
        header = read_eval_log(str(path), header_only=True)
    except Exception:
        continue
    if header.status != "success":
        continue
    if header.eval.task.split("/")[-1] != task:
        continue
    if subset and str(header.eval.task_args.get("subset", "")) != subset:
        continue
    sys.exit(0)
sys.exit(1)
PYCHECK
}

run_one() {  # arm model label task subset extra...
  local arm="$1" model="$2" label="$3" task="$4" subset="$5"; shift 5
  if already_done "$arm" "$task" "$subset"; then
    echo "--- [$(date +%H:%M:%S)] SKIP $arm :: $label (already complete)"
    return 0
  fi
  mkdir -p "$LOGROOT/$arm"
  echo "=== [$(date +%H:%M:%S)] $arm :: $label ==="
  .venv/bin/inspect eval "inspect_evals/$task" \
    --model "$model" --no-score --log-dir "$LOGROOT/$arm" \
    --max-connections "$CONN" --max-tokens "$MAXTOK" "$@" 2>&1 | tail -3
}

ARMS=(
  "gpt-oss-120b|openrouter/openai/gpt-oss-120b|"
  "qwen3-32b|openrouter/qwen/qwen3-32b|"
  "glm-4.7-flash|openrouter/z-ai/glm-4.7-flash|"
  "claude-haiku-4.5|openrouter/anthropic/claude-haiku-4.5|--reasoning-tokens 2048"
  "deepseek-v3.2|openrouter/deepseek/deepseek-v3.2|"
  "deepseek-v3.2-reasoning-on|openrouter/deepseek/deepseek-v3.2|--reasoning-tokens 2048"
  "gpt-5-nano-low|openrouter/openai/gpt-5-nano|--reasoning-effort low"
  "gpt-5-nano-medium|openrouter/openai/gpt-5-nano|--reasoning-effort medium"
  "gpt-5-nano-high|openrouter/openai/gpt-5-nano|--reasoning-effort high"
)

for entry in "${ARMS[@]}"; do
  IFS='|' read -r arm model extra <<< "$entry"
  # shellcheck disable=SC2086
  run_one "$arm" "$model" "strong_reject" strong_reject "" \
    -T jailbreak_method=None -T epochs=1 $extra
  run_one "$arm" "$model" "sycophancy" sycophancy "" \
    --limit 250 --sample-shuffle 42 $extra
  run_one "$arm" "$model" "xstest/safe" xstest "safe" -T subset=safe $extra
  run_one "$arm" "$model" "xstest/unsafe" xstest "unsafe" -T subset=unsafe $extra
  echo "### finished arm $arm at $(date +%H:%M:%S)"
done
echo "ALL ARMS COMPLETE $(date +%H:%M:%S)"
