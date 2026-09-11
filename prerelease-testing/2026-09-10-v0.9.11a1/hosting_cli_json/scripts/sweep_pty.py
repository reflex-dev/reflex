"""Run every `reflex cloud` leaf under a real pseudo-terminal.

stdout AND stdin are a pty (so ``sys.stdout.isatty()`` is True and a prompt
really blocks), stderr is a pipe so the two streams stay separable. Nothing is
ever written to the pty, so a command that prompts hangs until the timeout --
which is exactly the failure mode #6917 is about.

Usage: python sweep_pty.py <reflex-bin> <outdir> <label> [timeout]
"""

import errno
import json
import os
import pty
import re
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

REFLEX = sys.argv[1]
OUTDIR = Path(sys.argv[2])
LABEL = sys.argv[3] if len(sys.argv) > 3 else "pty"
TIMEOUT = float(sys.argv[4]) if len(sys.argv) > 4 else 45.0
OUTDIR.mkdir(parents=True, exist_ok=True)
RAW = OUTDIR / f"raw_{LABEL}"
RAW.mkdir(exist_ok=True)

ENV = dict(os.environ, REFLEX_TELEMETRY_ENABLED="false", NO_COLOR="1", COLUMNS="200", TERM="dumb")
for k in ("REFLEX_CLOUD_TOKEN", "CP_TOKEN"):
    ENV.pop(k, None)
CWD = "/tmp"


def run_pty(args, timeout=TIMEOUT):
    """Run under a pty; return (rc_or_TIMEOUT, stdout_text, stderr_text, seconds)."""
    master, slave = pty.openpty()
    t0 = time.time()
    p = subprocess.Popen(
        [REFLEX, *args],
        stdin=slave,
        stdout=slave,
        stderr=subprocess.PIPE,
        env=ENV,
        cwd=CWD,
        close_fds=True,
        start_new_session=True,
    )
    os.close(slave)
    out = bytearray()
    err = bytearray()
    streams = {master: out, p.stderr.fileno(): err}
    timed_out = False
    while True:
        if p.poll() is not None and not streams:
            break
        remaining = timeout - (time.time() - t0)
        if remaining <= 0:
            timed_out = True
            break
        r, _, _ = select.select(list(streams), [], [], min(0.5, max(remaining, 0.01)))
        for fd in r:
            try:
                chunk = os.read(fd, 65536)
            except OSError as e:
                chunk = b"" if e.errno == errno.EIO else b""
            if not chunk:
                streams.pop(fd, None)
                continue
            streams[fd] += chunk
        if p.poll() is not None and not r:
            # drain once more
            for fd in list(streams):
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    chunk = b""
                if chunk:
                    streams[fd] += chunk
                else:
                    streams.pop(fd, None)
            if not streams:
                break
    elapsed = time.time() - t0
    if timed_out:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception:
            pass
        rc = "TIMEOUT"
    else:
        rc = p.wait()
    try:
        os.close(master)
    except Exception:
        pass
    try:
        p.stderr.close()
    except Exception:
        pass
    return rc, out.decode(errors="replace"), err.decode(errors="replace"), round(elapsed, 1)


def run_pipe(args, timeout=TIMEOUT):
    try:
        p = subprocess.run([REFLEX, *args], capture_output=True, text=True,
                           timeout=timeout, env=ENV, cwd=CWD, input="")
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT", "", ""


def subcommands(path):
    rc, out, err = run_pipe([*path, "--help"], timeout=60)
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


leaves = []
for c1 in subcommands(["cloud"]):
    subs = subcommands(["cloud", c1])
    if subs:
        for c2 in subs:
            s2 = subcommands(["cloud", c1, c2])
            leaves += [["cloud", c1, c2, c3] for c3 in s2] if s2 else [["cloud", c1, c2]]
    else:
        leaves.append(["cloud", c1])

VARIANTS = [("tty_plain", []), ("tty_nointeractive", ["--no-interactive"]), ("tty_json", ["--json"])]

report = {"label": LABEL, "timeout": TIMEOUT, "leaf_count": len(leaves), "checks": {}}
for leaf in leaves:
    name = " ".join(leaf)
    entry = {}
    for label, extra in VARIANTS:
        rc, out, err, secs = run_pty([*leaf, *extra])
        slug = name.replace(" ", "_") + "__" + label
        (RAW / f"{slug}.out").write_text(out)
        (RAW / f"{slug}.err").write_text(err)
        entry[label] = {
            "rc": rc,
            "secs": secs,
            "stdout_head": (out.strip().splitlines() or [""])[0][:160],
            "stdout_tail": (out.strip().splitlines() or [""])[-1][:160],
            "stdout_bytes": len(out),
            "stderr_head": (err.strip().splitlines() or [""])[0][:160],
            "stderr_bytes": len(err),
        }
        print(f"{name:32} {label:18} rc={rc} {secs}s", flush=True)
    report["checks"][name] = entry

(OUTDIR / f"sweep_{LABEL}.json").write_text(json.dumps(report, indent=1))
print(json.dumps({"leaf_count": len(leaves), "out": str(OUTDIR / f'sweep_{LABEL}.json')}))
