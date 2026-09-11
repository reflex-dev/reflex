"""Off-TTY sweep of every `reflex cloud` leaf command.

For each leaf, run several flag variants under a pipe (stdout/stderr both
captured, so isatty() is False) with no cloud token, and record:
  * exit code
  * whether stdout is EXACTLY one parseable JSON document (or empty)
  * whether any human-readable text leaked onto stdout
  * stderr head

Usage: python sweep_pipe.py <path-to-reflex-bin> <outdir> [label]
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REFLEX = sys.argv[1]
OUTDIR = Path(sys.argv[2])
LABEL = sys.argv[3] if len(sys.argv) > 3 else "pipe"
OUTDIR.mkdir(parents=True, exist_ok=True)
RAW = OUTDIR / f"raw_{LABEL}"
RAW.mkdir(exist_ok=True)

ENV = dict(os.environ, REFLEX_TELEMETRY_ENABLED="false", NO_COLOR="1", COLUMNS="200")
for k in ("REFLEX_CLOUD_TOKEN", "CP_TOKEN"):
    ENV.pop(k, None)

CWD = "/tmp"


def run(args, timeout=60, stdin_data=""):
    try:
        p = subprocess.run(
            [REFLEX, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=ENV,
            cwd=CWD,
            input=stdin_data,
        )
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        dec = lambda b: b.decode(errors="replace") if isinstance(b, bytes) else (b or "")
        return "TIMEOUT", dec(e.stdout), dec(e.stderr)


def subcommands(path):
    rc, out, err = run([*path, "--help"])
    text = out + err
    cmds, in_cmds = [], False
    for line in text.splitlines():
        if re.match(r"^\s*(Commands|╭─+ Commands)", line):
            in_cmds = True
            continue
        if in_cmds:
            m = re.match(r"^\s*[│|]?\s*([a-z][a-z0-9-]*)\s{2,}", line)
            if m:
                cmds.append(m.group(1))
            elif re.match(r"^\s*╰", line):
                in_cmds = False
    return cmds


def classify_stdout(out, json_mode):
    """Return (kind, detail). kind in empty/one_json/multi_or_bad/plain_text."""
    stripped = out.strip()
    if not stripped:
        return "empty", ""
    try:
        json.loads(out)
        return "one_json", ""
    except Exception as e:
        pass
    # try JSON-lines
    lines = [l for l in out.splitlines() if l.strip()]
    bad = []
    for l in lines:
        try:
            json.loads(l)
        except Exception:
            bad.append(l)
    if not bad:
        return "json_lines", f"{len(lines)} lines"
    return "polluted", f"{len(bad)}/{len(lines)} non-JSON lines; first={bad[0][:160]!r}"


VARIANTS = [
    ("plain", []),
    ("json", ["--json"]),
    ("debug", ["--loglevel", "debug"]),
    ("json_debug", ["--json", "--loglevel", "debug"]),
    ("json_nointeractive", ["--json", "--no-interactive"]),
    ("json_interactive", ["--json", "--interactive"]),
]

leaves = []
for c1 in subcommands(["cloud"]):
    subs = subcommands(["cloud", c1])
    if subs:
        for c2 in subs:
            subs2 = subcommands(["cloud", c1, c2])
            if subs2:
                leaves += [["cloud", c1, c2, c3] for c3 in subs2]
            else:
                leaves.append(["cloud", c1, c2])
    else:
        leaves.append(["cloud", c1])

report = {
    "label": LABEL,
    "reflex": REFLEX,
    "leaf_count": len(leaves),
    "leaves": [" ".join(l) for l in leaves],
    "checks": {},
}
for leaf in leaves:
    name = " ".join(leaf)
    entry = {}
    for label, extra in VARIANTS:
        rc, out, err = run([*leaf, *extra], timeout=60)
        json_mode = "--json" in extra
        kind, detail = classify_stdout(out, json_mode)
        slug = name.replace(" ", "_") + "__" + label
        (RAW / f"{slug}.out").write_text(out)
        (RAW / f"{slug}.err").write_text(err)
        entry[label] = {
            "rc": rc,
            "stdout_kind": kind,
            "stdout_detail": detail,
            "stdout_head": (out.strip().splitlines() or [""])[0][:200],
            "stdout_bytes": len(out),
            "stderr_lines": len([l for l in err.splitlines() if l.strip()]),
            "stderr_head": (err.strip().splitlines() or [""])[0][:200],
            "stderr_tail": (err.strip().splitlines() or [""])[-1][:200],
        }
    report["checks"][name] = entry

(OUTDIR / f"sweep_{LABEL}.json").write_text(json.dumps(report, indent=1))
print(json.dumps({"leaf_count": len(leaves), "out": str(OUTDIR / f"sweep_{LABEL}.json")}))
