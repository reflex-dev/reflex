#!/bin/bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; V=$SB/apps/verify_hydration; A=$SB/apps/a311
$V/scripts/vlproxy.sh start 8661 8660 50
$V/scripts/vsrv.sh start vh-fix-dev a311fix dev $A/src/vhsync 3660 8660 REFLEX_API_URL=http://localhost:8661
env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python $V/drivers/waitsrv.py 400 http://localhost:3660/ http://localhost:8660/ping > /dev/null || echo "server not up"
sleep 4
$V/scripts/vraw.sh fix_rtt100_raw3 3 3660 3 300 pick-red 200 10
$V/scripts/vrun.sh fix_rtt100_restore7_st300_1click 4 3660 restore 7 --stagger 300 --clicks pick-red@200 --observe 10
$V/scripts/vraw.sh fix_rtt100_rawdocs6_st0 2 3660 6 0 docs 0 10
$V/scripts/vrun.sh fix_docsrestart4 2 3660 docs-restart 4 --restart-cmd "echo '# reload' >> $V/run/vh-fix-dev/vhsync/vhsync.py" --restart-wait 15
$V/scripts/vsrv.sh stop vh-fix-dev; $V/scripts/vlproxy.sh stop 8661
