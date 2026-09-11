#!/bin/bash
# stopapp.sh <fport> <bport>   — graceful stop + orphan sweep for the reserved ports
for p in $(ps aux | grep -E "frontend-port $1|backend-port $2" | grep -v grep | awk '{print $2}'); do kill $p 2>/dev/null; done
sleep 3
python3 - "$1" "$2" <<'PY'
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
ps aux | grep -E "reflex|vite|granian" | grep -v grep | awk '{print $2, $11, $12, $13, $14, $15}' | head
