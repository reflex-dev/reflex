"""Kill a pid and all its descendants by pid (never by pattern)."""
import os, signal, sys, time

def children(pid):
    try:
        return [int(x) for x in open(f"/proc/{pid}/task/{pid}/children").read().split()]
    except OSError:
        return []

def tree(pid, acc=None):
    acc = acc if acc is not None else []
    for c in children(pid):
        tree(c, acc)
    acc.append(pid)
    return acc

def alive(p):
    try: os.kill(p, 0); return True
    except OSError: return False

roots = [int(a) for a in sys.argv[1:]]
pids = []
for r in roots:
    pids += tree(r)
print("tree:", pids)
for p in pids:
    try: os.kill(p, signal.SIGTERM)
    except OSError: pass
for _ in range(20):
    time.sleep(0.5)
    if not any(alive(p) for p in pids): break
left = [p for p in pids if alive(p)]
for p in left:
    try: os.kill(p, signal.SIGKILL)
    except OSError: pass
time.sleep(1.0)
print("still alive:", [p for p in pids if alive(p)])
