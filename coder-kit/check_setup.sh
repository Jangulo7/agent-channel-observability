#!/usr/bin/env bash
# Check the coder's machine is ready, then offer 5 practice items.
#
# Practice uses its own sample id, so nothing done here touches the real sample.
set -uo pipefail
cd "$(dirname "$0")/.."

ok=0
fail=0
say() { printf '  %-46s %s\n' "$1" "$2"; }
check() { if eval "$2" >/dev/null 2>&1; then say "$1" "OK"; ok=$((ok+1)); else say "$1" "MISSING"; fail=$((fail+1)); fi; }

echo
echo "Checking your setup"
echo "-------------------"
check "python environment (.venv)"        "test -x .venv/bin/python"
check "channels package importable"       ".venv/bin/python -c 'import channels'"
check "annotation tool present"           "test -f scripts/annotate.py"
check "codebook present"                  "test -f data/codebook/v1.yaml"
check "wiki corpus present"               ".venv/bin/python -c \"
from pathlib import Path
from channels.loaders.collusion_wiki import CollusionWikiLoader
raise SystemExit(0 if CollusionWikiLoader(Path('data/german-collusion-wiki')).available() else 1)\""
check "output folder writable"            "mkdir -p results/annotations && test -w results/annotations"

echo
if [ "$fail" -ne 0 ]; then
  echo "$fail check(s) failed. Send this output on before starting."
  exit 1
fi

echo "All $ok checks passed."
.venv/bin/python - <<'PY'
from pathlib import Path
from channels.codebook import codebook_hash
from channels.loaders.collusion_wiki import CollusionWikiLoader
from channels.schema import Channel
utts = list(CollusionWikiLoader(Path("data/german-collusion-wiki")).load())
edits = [u for u in utts if u.channel is Channel.ARTEFACT_EDIT and u.corpus_meta.get("is_revert")]
msgs = [u for u in utts if u.channel is Channel.INTER_AGENT_MESSAGE and u.text]
print(f"  Round 1 draws 150 items from {len(edits):,} undone edits")
print(f"  Round 2 draws 300 items from {len(msgs):,} messages")
print(f"  codebook {codebook_hash()[:26]}...")
PY

echo
read -r -p "Try 5 practice items now? They do not count. [y/N] " reply
if [ "${reply:-n}" = "y" ] || [ "${reply:-n}" = "Y" ]; then
  echo
  echo "Practice round. Answers are saved under the name 'practice' and ignored."
  echo
  .venv/bin/python scripts/annotate.py \
    --task revert_validity --coder practice --n 5 --seed 1
  echo
  echo "Practice done. That is exactly what the real thing looks like."
fi

echo
echo "When you are ready, read coder-kit/TASK_1_EDITS.md and run:"
echo "  uv run python scripts/annotate.py --task revert_validity --coder YOUR_NAME"
