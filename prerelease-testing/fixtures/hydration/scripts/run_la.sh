#!/bin/bash
# Usage: run_la.sh <venv> <dev|prod> <label> <FP> <BP> [ENV=VAL...] -- reflex-local-auth demo: fresh run dir + db migrate,
# start, drivers/tp/drive_local_auth.py (38 checks) + drivers/la_storage.py (14 storage/echo checks), stop.
# <venv> must have reflex[db] + reflex-local-auth (scripts/build_venvs.sh).
. "$(dirname "$0")/env.sh"
V=$1; MODE=$2; L=$3; FP=$4; BP=$5; shift 5
NAME=la-$L; RUN=$W/run/$NAME; O=$W/results/local_auth; mkdir -p $O
rm -rf $RUN/local_auth_demo $RUN/alembic $RUN/reflex.db; mkdir -p $RUN
cp -r $F/src/local_auth_demo/alembic $F/src/local_auth_demo/alembic.ini $RUN/
cp -r $F/src/local_auth_demo/local_auth_demo $F/src/local_auth_demo/rxconfig.py $RUN/
(cd $RUN && env REFLEX_TELEMETRY_ENABLED=false RVH_VENV=$V $SB/envs/$V/bin/reflex db migrate > $W/logs/$NAME-migrate.log 2>&1; echo "migrate exit $?")
$F/scripts/srv.sh start $NAME $V $MODE $F/src/local_auth_demo $FP $BP "$@" || exit 1
$NP $DRV $F/drivers/waitsrv.py 500 http://localhost:$FP/ http://localhost:$BP/ping > /dev/null || { $F/scripts/srv.sh stop $NAME; exit 1; }
sleep 4
(cd $W && $NP timeout 900 $DRV $F/drivers/tp/drive_local_auth.py http://localhost:$FP $O $L $RUN/reflex.db > $O/$L.local_auth.txt 2>&1)
grep -E "checks|PASS|FAIL|ok=|passed" $O/$L.local_auth.txt | tail -3
(cd $W && $NP timeout 600 $DRV $F/drivers/la_storage.py http://localhost:$FP $O/$L.la_storage.json 2>&1 | tail -12)
$F/scripts/srv.sh stop $NAME > /dev/null
