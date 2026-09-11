"""Same reserve_stdout probe, but stdout is a PIPE and stderr is a PTY.

That is what `reflex cloud ... --json > out.json` looks like at a terminal, and
it is the configuration in which a stderr spinner can actually animate.
"""
import os, pty, select, subprocess, sys, time
from pathlib import Path

PY = sys.argv[1]
OUTDIR = Path(sys.argv[2]); OUTDIR.mkdir(parents=True, exist_ok=True)
script = OUTDIR / "_reserve_pty_child.py"   # reuse the child from the sibling probe
assert script.exists(), script

env = dict(os.environ, NO_COLOR="1", COLUMNS="120", TERM="xterm", REFLEX_TELEMETRY_ENABLED="false")
emaster, eslave = pty.openpty()
p = subprocess.Popen([PY, str(script)], stdin=subprocess.DEVNULL,
                     stdout=subprocess.PIPE, stderr=eslave, env=env, cwd="/tmp", close_fds=True)
os.close(eslave)
out, err = bytearray(), bytearray()
streams = {p.stdout.fileno(): out, emaster: err}
t0 = time.time()
while streams and time.time() - t0 < 120:
    r, _, _ = select.select(list(streams), [], [], 0.5)
    for fd in r:
        try: c = os.read(fd, 65536)
        except OSError: c = b""
        if not c: streams.pop(fd, None)
        else: streams[fd] += c
rc = p.wait(timeout=10); os.close(emaster)
so, se = out.decode(errors="replace"), err.decode(errors="replace")
(OUTDIR / "reserve_ptyerr.stdout.txt").write_text(so)
(OUTDIR / "reserve_ptyerr.stderr.txt").write_text(se)
print("rc", rc)
for tag in ("unreserved", "reserved", "released"):
    for what in ("spinner", "progressbar", "print", "cell"):
        m = f"MARK {tag} {what}"
        print(f"{m:34} stdout={'X' if m in so else '.'} stderr={'X' if m in se else '.'}")
for line in se.splitlines():
    if line.startswith(("META", "STDOUT-IS-TTY")): print(line.strip())
