#!/bin/bash
# cycle.sh <slug> <fport> <bport> <label> <pip args...>
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
U="$SB/apps/up_dataviz_local_lorem"
slug=$1; fport=$2; bport=$3; label=$4; shift 4
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
if [ $# -gt 0 ]; then
  (cd "$SB" && VIRTUAL_ENV="$SB/envs/up2_$slug" uv pip install --prerelease=allow --upgrade "$@") > "$U/logs/${slug}_${label}_install.log" 2>&1
  echo "install rc=$? :"; grep -E '^ [-+]' "$U/logs/${slug}_${label}_install.log" | head -20
fi
cd "$U/$slug" && nohup "$SB/envs/up2_$slug/bin/reflex" run --frontend-port $fport --backend-port $bport > "$U/logs/${slug}_${label}_run.log" 2>&1 &
sleep 100
curl -s -o /dev/null -w "front=%{http_code} ping=" "http://localhost:$fport/"; curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:$bport/ping"
cd "$U" && timeout 250 "$SB/envs/driver/bin/python" drive_up.py "$slug" "$fport" "$U/out/${slug}_${label}.json" 2>&1 | tail -16
