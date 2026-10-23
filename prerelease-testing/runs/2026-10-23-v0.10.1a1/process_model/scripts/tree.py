"""Process tree probe: tree.py <root pid> [--json out]  -> pid, ppid, state, threads, RSS, PSS, cmd for the tree.

Run with the driver venv (no reflex import). Sums PSS (from /proc/<pid>/smaps_rollup) over the python
processes and over everything.
"""

import json
import os
import sys


def table():
    out = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        pid = int(name)
        try:
            with open(f"/proc/{pid}/stat") as f:
                s = f.read()
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode(errors="replace").strip()
        except OSError:
            continue
        rest = s[s.rfind(")") + 2 :].split()
        out[pid] = {"pid": pid, "ppid": int(rest[1]), "pgid": int(rest[2]), "state": rest[0], "threads": int(rest[17]), "cmd": cmd[:150]}
    return out


def mem(pid):
    rss = pss = None
    try:
        with open(f"/proc/{pid}/smaps_rollup") as f:
            for line in f:
                if line.startswith("Rss:"):
                    rss = int(line.split()[1])
                elif line.startswith("Pss:"):
                    pss = int(line.split()[1])
    except OSError:
        pass
    return rss, pss


def main():
    root = int(sys.argv[1])
    out = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
    t = table()
    kids = {}
    for p in t.values():
        kids.setdefault(p["ppid"], []).append(p["pid"])
    rows = []

    def walk(pid, depth):
        if pid not in t:
            return
        rss, pss = mem(pid)
        row = dict(t[pid], depth=depth, rss_kb=rss, pss_kb=pss)
        rows.append(row)
        for k in sorted(kids.get(pid, [])):
            walk(k, depth + 1)

    walk(root, 0)
    py = [r for r in rows if "python" in r["cmd"] or "/bin/reflex" in r["cmd"]]
    summary = {
        "n_procs": len(rows),
        "n_python": len(py),
        "pss_total_kb": sum(r["pss_kb"] or 0 for r in rows),
        "pss_python_kb": sum(r["pss_kb"] or 0 for r in py),
        "rss_python_kb": sum(r["rss_kb"] or 0 for r in py),
    }
    for r in rows:
        print(f"{'  ' * r['depth']}{r['pid']} ppid={r['ppid']} st={r['state']} thr={r['threads']} rss={r['rss_kb']} pss={r['pss_kb']} {r['cmd'][:110]}")
    print("SUMMARY", json.dumps(summary))
    if out:
        json.dump({"rows": rows, "summary": summary}, open(out, "w"), indent=1)


main()
