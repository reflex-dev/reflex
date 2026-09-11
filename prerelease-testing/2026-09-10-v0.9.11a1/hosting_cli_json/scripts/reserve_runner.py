"""Run reserve_probe.py with separated streams and report stdout/stderr placement."""
import json, os, subprocess, sys, re
from pathlib import Path

PY = sys.argv[1]
PROBE = sys.argv[2]
OUT = Path(sys.argv[3])
EXPECT = sys.argv[4] if len(sys.argv) > 4 else "/envs/smoke/"

env = dict(os.environ, EXPECT_ENV=EXPECT, NO_COLOR="1", COLUMNS="200",
           REFLEX_TELEMETRY_ENABLED="false", TERM="dumb")
p = subprocess.run([PY, PROBE], capture_output=True, text=True, cwd="/tmp", env=env, timeout=180)
OUT.with_suffix(".stdout.txt").write_text(p.stdout)
OUT.with_suffix(".stderr.txt").write_text(p.stderr)

def marks(text):
    return [m.strip() for m in re.findall(r"MARK [^\n]*", text)]

so, se = marks(p.stdout), marks(p.stderr)
allm = sorted(set(so) | set(se))
rows = [{"mark": m, "stdout": m in so, "stderr": m in se} for m in allm]
meta = re.findall(r"META [^\n]*", p.stderr)
report = {"rc": p.returncode, "meta": meta, "marks": rows,
          "stdout_nonmark_lines": [l for l in p.stdout.splitlines() if l.strip() and "MARK" not in l]}
OUT.write_text(json.dumps(report, indent=1))
print(f"rc={p.returncode}")
for m in meta: print(m)
print(f"{'mark':60} stdout stderr")
for r in rows:
    print(f"{r['mark'][:58]:60} {'X' if r['stdout'] else '.':6} {'X' if r['stderr'] else '.'}")
if report["stdout_nonmark_lines"]:
    print("--- non-MARK stdout lines ---")
    for l in report["stdout_nonmark_lines"][:40]: print(repr(l[:160]))
