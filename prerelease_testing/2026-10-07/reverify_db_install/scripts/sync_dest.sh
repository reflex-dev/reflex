#!/usr/bin/env bash
# copy reusable artifacts to the repo artifact dir (no git); excludes build state, dbs, venvs
W=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/reverify_db_install
DEST=/home/user/reflex/prerelease_testing/2026-10-07/reverify_db_install
mkdir -p "$DEST"
tar -C "$W" -cf - --exclude=.web --exclude=node_modules --exclude=.states --exclude=assets/external --exclude='*.db' --exclude=reflex.lock --exclude=__pycache__ --exclude=.venv --exclude=.git --exclude=AGENTS.md --exclude=CLAUDE.md --exclude=.gitignore scripts apps logs freeze out | tar -C "$DEST" -xf -
du -sh "$DEST"
