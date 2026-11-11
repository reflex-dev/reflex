#!/usr/bin/env bash
# Copy app sources and scripts (no build output, logs or results) into the repo artifact dir.
set -eu
W=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/client_vars
D=/home/user/reflex/prerelease-testing/runs/2026-11-11-v0.11.0a1/client_vars
mkdir -p "$D/src"
cd "$W"
tar cf - --exclude=.web --exclude=node_modules --exclude=.states --exclude=reflex.lock --exclude=external \
  --exclude='*.db' --exclude=__pycache__ --exclude=.gitignore --exclude=word_lists --exclude=results --exclude=logs \
  --exclude=overkey_prev --exclude=run --exclude=hyd --exclude='*.bak.md' --exclude='*.png' --exclude=uploaded_files . | (cd "$D/src" && tar xf -)
du -sh "$D"
