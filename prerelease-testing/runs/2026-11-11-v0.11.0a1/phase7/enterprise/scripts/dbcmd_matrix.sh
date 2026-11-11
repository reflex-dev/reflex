#!/usr/bin/env bash
# FINDING-009 re-verify: run `reflex db <cmd>` in a FRESH copy (no .web, no reflex.db) of an app, per venv.
# Usage: dbcmd_matrix.sh <src app dir> <label> <venv...>    (venv: name under p7/envs, the work dir's envs/, or $SB/envs)
# OVERLAY=<dir> is prepended to PYTHONPATH (faker/pandas for the ag_grid demo; the venvs themselves are never modified).
# Cases: migrate (app ships alembic/), init (alembic removed), makemig, migrate_web (`reflex compile` first).
set -u
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad; W=$SB/p7/work/ent
SRC=$1; L=$2; shift 2
B=$W/db; mkdir -p $B
venv() { for d in $SB/p7/envs/$1 $W/envs/$1 $SB/envs/$1; do [ -x $d/bin/reflex ] && { echo $d; return; }; done; }
for V in "$@"; do
  VE=$(venv $V)
  for C in migrate init makemig migrate_web; do
    R=$B/${L}_${V}_$C; rm -rf $R; mkdir -p $R
    (cd $SRC && tar --exclude=.web --exclude=__pycache__ --exclude='*.db' --exclude=.states -cf - .) | (cd $R && tar -xf -)
    LOG=$R/cmd.log; : > $LOG
    run() { (cd $R && env CI=true REFLEX_TELEMETRY_ENABLED=false VE_VENV=$VE ${OVERLAY:+PYTHONPATH=$OVERLAY} REFLEX_DB_URL=sqlite:///reflex.db $VE/bin/reflex "$@" >> $LOG 2>&1 < /dev/null); }
    case $C in
      migrate) run db migrate; e=$?;;
      init) rm -rf $R/alembic $R/alembic.ini; run db init; e=$?;;
      makemig) run db makemigrations --message x; e=$?;;
      migrate_web) run compile > /dev/null; echo "[compile exit=$?]" >> $LOG; run db migrate; e=$?;;
    esac
    tbl=$( [ -f $R/reflex.db ] && sqlite3 $R/reflex.db .tables 2>/dev/null | tr -s ' \n' ' ' )
    echo "$V $C exit=$e web=$([ -d $R/.web ] && echo yes || echo no) tables=[${tbl}] | $(grep -m1 -o 'ValueError: Library [^.]*' $LOG)$(grep -m1 -o 'compile exit=[0-9]*' $LOG)$(grep -m1 -o -E '(Error|Exception): .{0,120}' $LOG | grep -v ValueError)"
  done
done
