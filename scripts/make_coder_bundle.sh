#!/usr/bin/env bash
# Build a self-contained bundle for the human coder.
#
# Why a bundle rather than repo access. The coder must not see the results, the
# build log or the pre-registration: they state what we expect to find, and a
# coder who has read them is no longer an independent measurement. The brief
# asks them not to look, but a request is not a control. This bundle simply does
# not contain those files, which makes the blindness structural.
#
# It also avoids making the repository public, which would publish the
# pre-registration and results before they are ready - and would not help
# anyway, since the corpus is gitignored and has to be transferred separately
# regardless.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="${1:-/tmp/coder-bundle}"
rm -rf "$OUT"
mkdir -p "$OUT"

# Code the tool needs, and nothing else.
mkdir -p "$OUT/src/channels/loaders" "$OUT/scripts" "$OUT/data/codebook"
cp src/channels/__init__.py src/channels/schema.py src/channels/errors.py \
   src/channels/codebook.py src/channels/annotate.py \
   src/channels/provenance.py src/channels/_vendored_stats.py "$OUT/src/channels/"
cp src/channels/loaders/__init__.py src/channels/loaders/base.py \
   src/channels/loaders/collusion_wiki.py "$OUT/src/channels/loaders/"
cp scripts/annotate.py "$OUT/scripts/"
cp data/codebook/v1.yaml "$OUT/data/codebook/"
cp -r coder-kit "$OUT/"
cp pyproject.toml "$OUT/"
[ -f uv.lock ] && cp uv.lock "$OUT/"

# The corpus. Large, and licence-restricted: research use, not redistribution.
mkdir -p "$OUT/data/german-collusion-wiki"
# The export may arrive gzipped, plain, or nested one level deep inside a
# directory that shares the archive's name, depending on how it was unpacked.
# -type f is what stops `find` matching the directory instead of the file.
for stem in revisions pages labels; do
  src=$(find data/german-collusion-wiki -type f \
        \( -name "$stem.jsonl" -o -name "$stem.jsonl.gz" \) | head -1)
  [ -n "$src" ] || { echo "missing $stem under data/german-collusion-wiki"; exit 1; }
  cp "$src" "$OUT/data/german-collusion-wiki/"
done

cat > "$OUT/LICENCE_NOTE.md" <<'NOTE'
# Before you start — about this data

The wiki data in `data/german-collusion-wiki/` comes from collusion.wiki and has
**no stated licence**. It is shared with you for this coding task only.

Please:
- do not redistribute it or post any of it publicly,
- do not paste page text or messages into any chatbot, LLM or online tool,
- delete the folder when you have finished.

Your labels contain no page text, so they are safe to send back.
NOTE

cat > "$OUT/RUN_ME_FIRST.md" <<'NOTE'
# Run me first

1. Install: `uv sync --extra dev`  (or `pip install -e .`)
2. Check:   `bash coder-kit/check_setup.sh`
3. Read:    `coder-kit/README.md`

Everything you need is in `coder-kit/`. Start there.
NOTE

# Prove the bundle carries nothing it should not.
for forbidden in RESULTS_SUMMARY.md BUILD_LOG.md README.md docs results; do
  if [ -e "$OUT/$forbidden" ]; then
    echo "REFUSED: bundle contains $forbidden, which would un-blind the coder"
    exit 1
  fi
done

# Zip with Python's zipfile: `zip` is not installed on every machine, and the
# coder should not have to care which archiver the author happened to have.
ZIP="${OUT%/}.zip"
rm -f "$ZIP"
.venv/bin/python - "$OUT" "$ZIP" <<'PYZIP'
import sys, zipfile
from pathlib import Path

source, target = Path(sys.argv[1]), Path(sys.argv[2])
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(source.rglob("*")):
        if path.is_file():
            archive.write(path, Path(source.name) / path.relative_to(source))
PYZIP

size=$(du -sh "$OUT" | cut -f1)
zipsize=$(du -h "$ZIP" | cut -f1)
echo "bundle built at $OUT ($size)"
echo "zip written to  $ZIP ($zipsize)  <- send this"
echo "contains: annotation tool, codebook, corpus, coder-kit"
echo "excludes: results, build log, preregistration, project README"
