#!/bin/bash
# variant.sh <venv> <name> <python-file-that-edits-models-in-cwd> [snapshot=snap_blog_rw]
# Copies the rewritten-app snapshot, applies the edit, runs `reflex db makemigrations`, prints the revision.
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
V=$SB/envs/$1; NAME=$2; EDIT=$3; SNAP=${4:-snap_blog_rw}
W=$SB/apps/db_models/variants/$NAME; rm -rf $W; mkdir -p $W; cp -a $SB/apps/db_models/$SNAP/. $W/; cd $W
export REFLEX_TELEMETRY_ENABLED=false
python3 $SB/apps/db_models/repros/$EDIT
$V/bin/reflex db makemigrations --message $NAME > mm.log 2>&1; echo "makemigrations rc=$?"
grep -vE "reflex.Model has been|use database ORM|removed in 1.0.0|^\(/tmp|envs/db_models|uction.py|^\s*$" mm.log | head -30
f=$(ls alembic/versions/*_${NAME}.py 2>/dev/null)
if [ -n "$f" ]; then echo "--- REVISION $f"; sed -n '/def upgrade/,/def downgrade/p' $f | grep -v '^\s*$'; else echo "--- no revision written"; fi
