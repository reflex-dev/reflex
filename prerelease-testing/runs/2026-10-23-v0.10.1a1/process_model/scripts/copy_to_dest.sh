#!/usr/bin/env bash
# Copy reusable artifacts (apps without .web/node_modules/.states/db/pycache, scripts, out/, trimmed logs) to DEST.
set -u
SB=${SB:?}
PM=$SB/apps/process_model
DEST=${DEST:-/home/user/wt-testing/prerelease-testing/runs/2026-10-23-v0.10.1a1/process_model}
mkdir -p "$DEST/apps" "$DEST/scripts" "$DEST/out" "$DEST/logs" "$DEST/shots"
for a in forkapp hotapp noinit; do
  [ -d "$PM/$a" ] || continue
  rm -rf "$DEST/apps/$a"
  (cd "$PM" && tar cf - --exclude=.web --exclude=node_modules --exclude=.states --exclude='*.db' --exclude=__pycache__ --exclude='*.log' --exclude='*.log.q' --exclude='*.seq' "$a") | (cd "$DEST/apps" && tar xf -)
done
cp "$PM"/scripts/* "$DEST/scripts/"
cp "$PM"/out/*.json "$DEST/out/" 2>/dev/null
cp "$PM"/out/*.log "$DEST/out/" 2>/dev/null
cp "$PM"/out/*.txt "$DEST/out/" 2>/dev/null
# trimmed server logs: keep the first 60 and last 120 lines of each
for f in "$PM"/logs/*.log; do
  b=$(basename "$f" .log)
  { head -60 "$f"; echo "... [trimmed] ..."; tail -120 "$f"; } > "$DEST/logs/$b.trimmed.log"
done
du -sh "$DEST"
