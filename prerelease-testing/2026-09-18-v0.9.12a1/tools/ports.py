#!/usr/bin/env python3
"""List listening TCP ports with owning pid and command (no `ss`/`netstat` in this container).

Usage: ports.py            -> all listeners
       ports.py 3100 8100  -> only these ports (exit 1 if any is bound)
"""
import os, sys, glob

def listeners():
    inodes = {}
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = open(path).read().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if parts[3] != "0A":  # LISTEN
                continue
            port = int(parts[1].rsplit(":", 1)[1], 16)
            inodes[parts[9]] = port
    owners = {}
    for fd in glob.glob("/proc/[0-9]*/fd/*"):
        try:
            target = os.readlink(fd)
        except OSError:
            continue
        if target.startswith("socket:["):
            ino = target[8:-1]
            if ino in inodes:
                pid = int(fd.split("/")[2])
                owners.setdefault(inodes[ino], set()).add(pid)
    out = []
    for port in sorted(set(inodes.values())):
        pids = sorted(owners.get(port, ()))
        cmds = []
        for pid in pids:
            try:
                cmds.append(open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode()[:110])
            except OSError:
                cmds.append("?")
        out.append((port, pids, cmds))
    return out

want = {int(a) for a in sys.argv[1:]}
rows = [r for r in listeners() if not want or r[0] in want]
for port, pids, cmds in rows:
    print(f"{port}\tpids={','.join(map(str, pids)) or '?'}\t{' | '.join(cmds)}")
sys.exit(1 if want and rows else 0)
