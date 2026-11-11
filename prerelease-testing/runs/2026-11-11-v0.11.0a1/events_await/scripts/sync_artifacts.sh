#!/usr/bin/env bash
# Copy the reusable artifacts (sources, scripts, probes) into the repo run directory. No git.
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
A=$SB/apps/events_await
D=/home/user/reflex/prerelease-testing/runs/2026-11-11-v0.11.0a1/events_await
cd "$A" || exit 1
tar cf - \
  --exclude=.web --exclude=node_modules --exclude=.states --exclude=reflex.lock --exclude=assets/external \
  --exclude='*.db' --exclude=__pycache__ --exclude='*.png' --exclude='up1.txt' --exclude='up2.bin' \
  --exclude=.gitignore --exclude=AGENTS.md --exclude=CLAUDE.md --exclude=requirements.txt --exclude='.mypy_cache' \
  awaitapp legacyapp scripts probes $(ls -d typing 2>/dev/null) | (cd "$D" && tar xf -)
mkdir -p "$D/evidence"
cp out/deco_matrix_*.txt "$D/evidence/" 2>/dev/null
du -sh "$D"
