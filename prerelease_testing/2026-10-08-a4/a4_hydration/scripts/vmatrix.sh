#!/bin/bash
# vmatrix.sh <venv:a3|a4> <dev|prod|prodredis> [RUNS_RAW=3] [RUNS_RESTORE=3]
# The verifier's A3-11 / A3-12 scenarios through a 100 ms RTT proxy (50 ms each way), copied from
# a3_hydration/pr7505/scripts/vh_matrix.sh and pointed at the PUBLISHED venvs.
#   dev:       app 3660/8660, proxy 8661 -> 8660 (backend only), REFLEX_API_URL=http://localhost:8661, driver -> 3660
#   prod:      app 3662 (one port), proxy 3663 -> 3662, REFLEX_API_URL=http://localhost:3663, driver -> 3663
#   prodredis: as prod + redis-server on 8669 (REFLEX_REDIS_URL; 9 granian workers on 4 CPUs)
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; V=$SB/apps/a4_hydration/v
VE=$1; MODE=$2; NR=${3:-3}; NS=${4:-3}
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
NAME=vh-$VE-dev; [ $MODE != dev ] && NAME=vh-$VE-prod
if [ $MODE = dev ]; then
  $V/scripts/vlproxy.sh start 8661 8660 50
  $V/scripts/vsrv.sh start $NAME $VE dev $V/src/vhsync 3660 8660 REFLEX_API_URL=http://localhost:8661
  $NP $DRV $V/drivers/waitsrv.py 400 http://localhost:3660/ http://localhost:8660/ping > /dev/null || echo "server not up"
  FP=3660
else
  EXTRA=""
  if [ $MODE = prodredis ]; then redis-server --port 8669 --save '' --appendonly no > $V/logs/redis-8669.log 2>&1 & echo $! > $V/run/redis.pid; sleep 1; EXTRA=REFLEX_REDIS_URL=redis://localhost:8669; fi
  $V/scripts/vlproxy.sh start 3663 3662 50
  $V/scripts/vsrv.sh start $NAME $VE prod $V/src/vhsync 3662 3662 REFLEX_API_URL=http://localhost:3663 $EXTRA
  $NP $DRV $V/drivers/waitsrv.py 500 http://localhost:3662/ http://localhost:3662/ping > /dev/null || echo "server not up"
  FP=3663
fi
sleep 4
T=${VE}${MODE}
$V/scripts/vraw.sh ${T}_rtt100_raw3 $NR $FP 3 300 pick-red 200 10
$V/scripts/vrun.sh ${T}_rtt100_restore7_st300_1click $NS $FP restore 7 --stagger 300 --clicks pick-red@200 --observe 10
$V/scripts/vraw.sh ${T}_rtt100_rawdocs6_st0 2 $FP 6 0 docs 0 10
if [ $MODE = dev ]; then
  $V/scripts/vrun.sh ${T}_docsrestart4 2 $FP docs-restart 4 --restart-cmd "echo '# reload' >> $V/run/$NAME/vhsync/vhsync.py" --restart-wait 15
fi
$V/scripts/vsrv.sh stop $NAME
if [ $MODE = dev ]; then $V/scripts/vlproxy.sh stop 8661; else $V/scripts/vlproxy.sh stop 3663; fi
[ -f $V/run/redis.pid ] && { kill $(cat $V/run/redis.pid); rm -f $V/run/redis.pid; echo "redis stopped"; }
true
