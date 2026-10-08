#!/bin/bash
# Usage: run_la.sh <venv> <dev|prod> <label> <FP> <BP> [ENV=VAL...] -- reflex-local-auth demo: fresh run dir + db migrate,
# start, drive_local_auth.py (38 checks) + drive_fresh_storage.py + la_storage.py (#7493 storage/echo checks), stop.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_hydration_router
V=$1; MODE=$2; L=$3; FP=$4; BP=$5; shift 5
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
NAME=la-$L; RUN=$W/run/$NAME; O=$W/results/local_auth; mkdir -p $O
rm -rf $RUN/local_auth_demo $RUN/alembic $RUN/reflex.db; mkdir -p $RUN
cp -r $W/src/local_auth_demo/alembic $W/src/local_auth_demo/alembic.ini $RUN/
cp -r $W/src/local_auth_demo/local_auth_demo $W/src/local_auth_demo/rxconfig.py $RUN/
(cd $RUN && env REFLEX_TELEMETRY_ENABLED=false RVH_VENV=$V $SB/envs/$V/bin/reflex db migrate > $W/logs/$NAME-migrate.log 2>&1; echo "migrate exit $?")
$W/scripts/srv.sh start $NAME $V $MODE $W/src/local_auth_demo $FP $BP "$@"
$NP $DRV $W/drivers/waitsrv.py 500 http://localhost:$FP/ http://localhost:$BP/ping > /dev/null || { $W/scripts/srv.sh stop $NAME; exit 1; }
sleep 4
(cd $W/drivers/tp && $NP timeout 900 $DRV drive_local_auth.py http://localhost:$FP $O $L $RUN/reflex.db > $O/$L.local_auth.txt 2>&1)
grep -E "checks|PASS|FAIL|ok=|passed" $O/$L.local_auth.txt | tail -3
(cd $W/drivers && $NP timeout 600 $DRV la_storage.py http://localhost:$FP $O/$L.la_storage.json 2>&1 | tail -12)
$W/scripts/srv.sh stop $NAME > /dev/null
