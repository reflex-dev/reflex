#!/bin/bash
# Usage: seed_sweep.sh <venv> <fp> <bp> <variant> <seed>...  -- one dev server per seed, runs drive_cvstore.py <variant>
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_thirdparty_1
V=$1; FP=$2; BP=$3; VAR=$4; shift 4
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
for s in "$@"; do
  PYTHONHASHSEED=$s $W/start.sh $V $W/apps/$V/cvstore $FP $BP $W/logs/sweep-$V-dev-seed$s.log > /dev/null
  $W/wait_up.sh http://localhost:$FP/ 400 $W/pids/cvstore-$V.pid > /dev/null || { echo "seed $s: server not up"; $W/stop.sh $W/pids/cvstore-$V.pid; continue; }
  sleep 2
  pred=$(cd $W/probes && PYTHONHASHSEED=$s $SB/envs/$V/bin/python -c "print('stable-path:' + ('FRESH' if list({'ls'}.union({'check'}))[0]=='check' else 'STALE'))")
  res=$(cd $W/drivers && $SB/envs/driver/bin/python drive_cvstore.py http://localhost:$FP $W/out/sweep sweep-$V-seed$s $VAR 2>&1 | grep -E "^   (reload |after-client-nav)" | sed 's/  */ /g' | tr '\n' '|')
  echo "$V seed=$s predicted[$pred] -> $res"
  $W/stop.sh $W/pids/cvstore-$V.pid > /dev/null
  sleep 1
done
