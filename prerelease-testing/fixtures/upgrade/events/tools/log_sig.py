"""Normalized signature of a reflex server log, for diffing two runs of the same app on two versions.

Usage: log_sig.py A.log B.log
Keeps warning/error/traceback/exception/EVLOG BACKEND_EXC lines, replaces numbers, hex ids, tokens, timestamps and
venv paths with placeholders, counts them, and prints the lines whose counts differ between A and B.
"""

import collections
import re
import sys

KEEP = re.compile(r"(?i)traceback|error|exception|warning|deprecat|BACKEND_EXC |FRONTEND_EXC|Unexpected|killed|failed")
SUBS = [
    (re.compile(r"/tmp/\S+?/envs/[^/]+/"), "<VENV>/"),
    (re.compile(r"/tmp/\S+?/apps/\S+?/run/[^/]+/"), "<RUN>/"),
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"), "<UUID>"),
    (re.compile(r"0x[0-9a-f]+"), "<HEX>"),
    (re.compile(r"\d+(\.\d+)?"), "<N>"),
]


def sig(path):
    c = collections.Counter()
    for line in open(path, errors="replace"):
        line = line.rstrip()
        if not KEEP.search(line):
            continue
        for rx, rep in SUBS:
            line = rx.sub(rep, line)
        c[line[:220]] += 1
    return c


a, b = sig(sys.argv[1]), sig(sys.argv[2])
for k in sorted(set(a) | set(b)):
    if a[k] != b[k]:
        print(f"A={a[k]:4d} B={b[k]:4d}  {k}")
print(f"(lines kept: A={sum(a.values())} B={sum(b.values())}; distinct: A={len(a)} B={len(b)})")
