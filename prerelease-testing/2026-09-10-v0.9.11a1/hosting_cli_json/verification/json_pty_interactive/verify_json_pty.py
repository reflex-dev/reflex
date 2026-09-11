"""Minimal repro for `--json` not implying non-interactive (hosting-cli 0.1.72a1).

Runs `reflex cloud apps list` with stdout as a pty and as a pipe, crossed with
`--json` / `--no-interactive` / neither, and with stdin as a pty, an open pipe
nobody writes to, and /dev/null. Nothing is ever typed at the prompt.

Usage:
    python verify_json_pty.py <path-to-reflex> <timeout_s> <outdir>

Requires no reflex token to be present (REFLEX_ACCESS_TOKEN unset and no
hosting_v1.json), which is the state an agent or a CI job starts from.
"""

import json
import os
import pty
import select
import signal
import subprocess
import sys
import time

EXE, TIMEOUT, OUTDIR = sys.argv[1], float(sys.argv[2]), sys.argv[3]
os.makedirs(OUTDIR, exist_ok=True)


def run(label, extra_args, stdout_kind, stdin_kind):
    """Run one variant and return its result dict."""
    if stdout_kind == "pty":
        m_out, s_out = pty.openpty()
    else:
        m_out, s_out = os.pipe()
    keep = []
    if stdin_kind == "devnull":
        s_in = os.open(os.devnull, os.O_RDONLY)
    elif stdin_kind == "pipe_open":
        r, w = os.pipe()
        s_in, _ = r, keep.append(w)
    else:
        m_in, s_in = pty.openpty()
        keep.append(m_in)
    err_r, err_w = os.pipe()
    argv = [EXE, "cloud", "apps", "list", *extra_args]
    p = subprocess.Popen(
        argv, stdin=s_in, stdout=s_out, stderr=err_w, close_fds=True,
        start_new_session=True,
        env={**os.environ, "REFLEX_TELEMETRY_ENABLED": "false"},
    )
    for fd in (s_out, s_in, err_w):
        os.close(fd)
    out, err, fds, start, rc = bytearray(), bytearray(), {m_out, err_r}, time.time(), None
    while True:
        if p.poll() is not None and not fds:
            rc = p.returncode
            break
        rem = TIMEOUT - (time.time() - start)
        if rem <= 0:
            rc = "TIMEOUT"
            break
        ready, _, _ = select.select(list(fds), [], [], min(0.25, max(rem, 0.01)))
        for fd in ready:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                chunk = b""
            if not chunk:
                fds.discard(fd)
                continue
            (out if fd == m_out else err).extend(chunk)
        if p.poll() is not None and not ready:
            rc = p.returncode
            break
    if rc == "TIMEOUT":
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except OSError:
            pass
        p.wait()
    for fd in [m_out, err_r, *keep]:
        try:
            os.close(fd)
        except OSError:
            pass
    with open(os.path.join(OUTDIR, label + ".out"), "wb") as f:
        f.write(bytes(out))
    with open(os.path.join(OUTDIR, label + ".err"), "wb") as f:
        f.write(bytes(err))
    return {
        "label": label, "args": extra_args, "stdout": stdout_kind, "stdin": stdin_kind,
        "rc": rc, "elapsed": round(time.time() - start, 2),
        "stdout_bytes": len(out), "stderr_bytes": len(err),
        "hung": rc == "TIMEOUT",
    }


VARIANTS = [
    ("ptyout_json",           ["--json"],            "pty",  "pty"),
    ("ptyout_nointeractive",  ["--no-interactive"],  "pty",  "pty"),
    ("ptyout_plain",          [],                    "pty",  "pty"),
    ("pipeout_json",          ["--json"],            "pipe", "pty"),
    ("pipeout_nointeractive", ["--no-interactive"],  "pipe", "pty"),
    ("pipeout_plain",         [],                    "pipe", "pty"),
    ("ptyout_json_stdin_pipe_open", ["--json"],      "pty",  "pipe_open"),
    ("ptyout_json_stdin_devnull",   ["--json"],      "pty",  "devnull"),
]

results = [run(*v) for v in VARIANTS]
for r in results:
    print(json.dumps(r))
with open(os.path.join(OUTDIR, "summary.json"), "w") as f:
    json.dump({"exe": EXE, "timeout": TIMEOUT, "results": results}, f, indent=2)
