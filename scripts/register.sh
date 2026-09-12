#!/usr/bin/env bash
# Stamp the pre-registration with the commit that registers it.
#
# Run this LAST, when everything you intend to register is committed and you are
# ready to push. It fills the timestamp, commits, and prints the SHA to paste
# back - a registration whose SHA was written before the commit existed would be
# recording an intention, not a registration.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "working tree is dirty. Commit or stash first, then re-run." >&2
  exit 1
fi

NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
python3 - "$NOW" <<'PY'
import sys
from pathlib import Path
now = sys.argv[1]
p = Path("docs/PREREGISTRATION.md")
t = p.read_text()
t = t.replace("| Registration timestamp (UTC) | `TODO(johanna)` |",
              f"| Registration timestamp (UTC) | `{now}` |")
p.write_text(t)
PY

git add docs/PREREGISTRATION.md
git commit -q -m "registration: stamp the pre-registration at $NOW

Confirmatory scope is C1-C3, the human annotation, for which no label exists at
this commit. Every other analysis is recorded as exploratory in section 0."
SHA=$(git rev-parse HEAD)

python3 - "$SHA" <<'PY'
import sys
from pathlib import Path
sha = sys.argv[1]
p = Path("docs/PREREGISTRATION.md")
t = p.read_text().replace(
    "| Registration commit SHA | `TODO(johanna)` — filled by `scripts/register.sh` at the registration commit |",
    f"| Registration commit SHA | `{sha}` |")
p.write_text(t)
PY

git add docs/PREREGISTRATION.md
git commit -q -m "registration: record the registering commit SHA $SHA"
echo
echo "Registered at $NOW"
echo "Registration commit: $SHA"
echo
echo "Now push, so the registration is public BEFORE the labels exist:"
echo "  git push origin $(git rev-parse --abbrev-ref HEAD)"
