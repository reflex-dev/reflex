"""Does a REJECTED token still drop the CLI into the interactive login prompt?

stdin is an open pipe that never delivers a byte -- the realistic CI/agent shape
(a pipe or an inherited terminal that nobody types into). A command that returns
is fine; a command that sits until the timeout is the hang #6917 set out to kill.

Usage: python bad_token_hang.py <reflex-bin> <label> <outdir> [timeout]
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REFLEX = sys.argv[1]
LABEL = sys.argv[2]
OUTDIR = Path(sys.argv[3])
TIMEOUT = float(sys.argv[4]) if len(sys.argv) > 4 else 90.0
OUTDIR.mkdir(parents=True, exist_ok=True)

BASE = dict(os.environ, REFLEX_TELEMETRY_ENABLED="false", NO_COLOR="1", COLUMNS="200")
BASE.pop("REFLEX_ACCESS_TOKEN", None)

CASES = [
    ("no_token_nointeractive", ["cloud", "apps", "list", "--json", "--no-interactive"], {}),
    ("bad_token_opt_json", ["cloud", "apps", "list", "--json", "--token", "bogus-token-123"], {}),
    ("bad_token_opt_nointeractive", ["cloud", "apps", "list", "--json", "--no-interactive", "--token", "bogus-token-123"], {}),
    ("bad_token_env_nointeractive", ["cloud", "apps", "list", "--json", "--no-interactive"], {"REFLEX_ACCESS_TOKEN": "bogus-token-123"}),
    ("bad_token_env_plain", ["cloud", "apps", "list"], {"REFLEX_ACCESS_TOKEN": "bogus-token-123"}),
    ("bad_token_env_whoami_json", ["cloud", "whoami", "--json"], {"REFLEX_ACCESS_TOKEN": "bogus-token-123"}),
    ("bad_token_env_project_list", ["cloud", "project", "list", "--json", "--no-interactive"], {"REFLEX_ACCESS_TOKEN": "bogus-token-123"}),
]

results = []
for name, args, extra in CASES:
    env = dict(BASE, **extra)
    # An open pipe nobody writes to: read() blocks instead of returning EOF.
    r_fd, w_fd = os.pipe()
    t0 = time.time()
    p = subprocess.Popen([REFLEX, *args], stdin=r_fd, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, env=env, cwd="/tmp",
                         start_new_session=True)
    os.close(r_fd)
    try:
        out, err = p.communicate(timeout=TIMEOUT)
        rc = p.returncode
        hung = False
    except subprocess.TimeoutExpired:
        hung = True
        rc = "TIMEOUT"
        p.kill()
        out, err = p.communicate()
    os.close(w_fd)
    elapsed = round(time.time() - t0, 1)
    out = out.decode(errors="replace")
    err = err.decode(errors="replace")
    (OUTDIR / f"badtoken_{LABEL}_{name}.out").write_text(out)
    (OUTDIR / f"badtoken_{LABEL}_{name}.err").write_text(err)
    results.append({
        "case": name, "args": args, "env": list(extra),
        "rc": rc, "hung": hung, "secs": elapsed,
        "stdout_bytes": len(out),
        "prompted": "hit 'Enter'" in err or "hit 'Enter'" in out,
        "stderr_head": (err.strip().splitlines() or [""])[0][:160],
    })
    print(f"{name:32} rc={rc} hung={hung} {elapsed}s prompted={results[-1]['prompted']}", flush=True)

(OUTDIR / f"badtoken_{LABEL}.json").write_text(json.dumps(results, indent=1))
