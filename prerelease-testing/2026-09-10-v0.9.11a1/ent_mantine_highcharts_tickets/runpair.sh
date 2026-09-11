#!/bin/bash
# runpair.sh <demo> <venv> <fport> <bport> <label> [routes...]
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
E="$SB/apps/ent_mantine_highcharts_tickets"
demo=$1; venv=$2; fport=$3; bport=$4; label=$5; shift 5
for p in $(ps aux | grep "frontend-port $fport" | grep -v grep | awk '{print $2}'); do kill $p 2>/dev/null; done
sleep 4
python3 - "$fport" "$bport" <<'PY'
import glob, os, sys
want={int(sys.argv[1]), int(sys.argv[2])}
inodes={}
for line in open('/proc/net/tcp').read().splitlines()[1:]:
    f=line.split(); port=int(f[1].split(':')[1],16)
    if f[3]=='0A' and port in want: inodes[f[9]]=port
for fd in glob.glob('/proc/[0-9]*/fd/*'):
    try: t=os.readlink(fd)
    except OSError: continue
    if t.startswith('socket:[') and t[8:-1] in inodes:
        try: os.kill(int(fd.split('/')[2]),9); print("killed orphan", fd.split('/')[2])
        except OSError: pass
PY
sleep 2
cd "$E/$demo" && CI=true nohup "$SB/envs/$venv/bin/reflex" run --frontend-port $fport --backend-port $bport > "$E/logs/${demo}_${label}.log" 2>&1 &
sleep 110
curl -s -o /dev/null -w "front=%{http_code} ping=" "http://localhost:$fport/"; curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:$bport/ping"
cd "$E" && timeout 300 "$SB/envs/driver/bin/python" drive_ent.py "$fport" "$E/out/${demo}_${label}.json" "$@" 2>&1 | tail -14
