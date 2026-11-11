#!/usr/bin/env bash
# Issue 4: run `reflex db <cmd>` in a FRESH copy (no .web, no reflex.db) of an app, per venv.
# Usage: dbcmd_matrix.sh <src app dir> <label> <venv...>
#   For each venv and each case it copies the app to $SB/apps/verify_ent/db/<label>_<venv>_<case>, then runs:
#     migrate     : rm alembic-state; `reflex db migrate`               (app ships alembic/ -> stock path)
#     init        : rm -rf alembic alembic.ini; `reflex db init`
#     makemig     : `reflex db makemigrations --message x`               (after a `db migrate` attempt)
#     migrate_web : same as migrate but after a `reflex export --frontend-only --no-zip`-free compile:
#                   we create .web by `reflex compile` first (shows the .web-present path)
# Prints one line per run: venv case exit=<n> and the first ValueError line.
set -u
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
SRC=$1; L=$2; shift 2
B=$SB/apps/verify_ent/db; mkdir -p $B
for V in "$@"; do
  for C in migrate init makemig migrate_web; do
    R=$B/${L}_${V}_$C; rm -rf $R; mkdir -p $R
    (cd $SRC && tar --exclude=.web --exclude=__pycache__ --exclude='*.db' --exclude=.states -cf - .) | (cd $R && tar -xf -)
    LOG=$R/cmd.log; : > $LOG
    run() { (cd $R && env CI=true REFLEX_TELEMETRY_ENABLED=false VE_VENV=$SB/envs/$V REFLEX_DB_URL=sqlite:///reflex.db $SB/envs/$V/bin/reflex "$@" >> $LOG 2>&1 < /dev/null); }
    case $C in
      migrate) run db migrate; e=$?;;
      init) rm -rf $R/alembic $R/alembic.ini; run db init; e=$?;;
      makemig) run db makemigrations --message x; e=$?;;
      migrate_web) run compile > /dev/null; echo "[compile exit=$?]" >> $LOG; run db migrate; e=$?;;
    esac
    echo "$V $C exit=$e web=$([ -d $R/.web ] && echo yes || echo no) | $(grep -m1 -o 'ValueError: Library [^.]*' $LOG)$(grep -m1 -o 'compile exit=[0-9]*' $LOG)"
  done
done
