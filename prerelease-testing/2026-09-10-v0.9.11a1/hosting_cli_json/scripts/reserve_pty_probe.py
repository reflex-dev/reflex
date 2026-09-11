"""reserve_stdout under a real terminal: spinners/progress/prompts must not touch stdout.

Child writes markers; parent gives stdout a pty (so rich animates) and keeps
stderr a pipe.
"""
import os
import pty
import select
import subprocess
import sys
import time
from pathlib import Path

CHILD = r'''
import sys, time, logging
import reflex_base
assert "/envs/smoke/" in reflex_base.__file__, reflex_base.__file__
from reflex_base.utils import console
from reflex_base.utils import log as rlog
from reflex_base.constants import LogLevel
rlog.enable_managed_logging(); rlog.set_log_level(LogLevel.DEBUG)
print("STDOUT-IS-TTY", sys.stdout.isatty(), file=sys.stderr)

def block(tag):
    with console.status(f"MARK {tag} spinner"):
        time.sleep(0.6)
    p = console.progress()
    print(f"META {tag} progress.disable={p.disable}", file=sys.stderr)
    with p:
        t = p.add_task(f"MARK {tag} progressbar", total=2)
        for _ in range(2):
            p.update(t, advance=1); time.sleep(0.2)
    console.print(f"MARK {tag} print")
    console.print_table([[f"MARK {tag} cell", "y"]], headers=["h", "i"])

block("unreserved")
rlog.reserve_stdout(True)
block("reserved")
rlog.reserve_stdout(False)
block("released")
print("META done", file=sys.stderr)
'''

PY = sys.argv[1]
OUTDIR = Path(sys.argv[2])
OUTDIR.mkdir(parents=True, exist_ok=True)
script = OUTDIR / "_reserve_pty_child.py"
script.write_text(CHILD)

env = dict(os.environ, NO_COLOR="1", COLUMNS="120", TERM="xterm",
           REFLEX_TELEMETRY_ENABLED="false")
master, slave = pty.openpty()
p = subprocess.Popen([PY, str(script)], stdin=slave, stdout=slave,
                     stderr=subprocess.PIPE, env=env, cwd="/tmp", close_fds=True)
os.close(slave)
out, err = bytearray(), bytearray()
streams = {master: out, p.stderr.fileno(): err}
t0 = time.time()
while streams and time.time() - t0 < 120:
    r, _, _ = select.select(list(streams), [], [], 0.5)
    for fd in r:
        try:
            c = os.read(fd, 65536)
        except OSError:
            c = b""
        if not c:
            streams.pop(fd, None)
        else:
            streams[fd] += c
rc = p.wait(timeout=10)
os.close(master)
so, se = out.decode(errors="replace"), err.decode(errors="replace")
(OUTDIR / "reserve_pty.stdout.txt").write_text(so)
(OUTDIR / "reserve_pty.stderr.txt").write_text(se)
print("rc", rc)
for tag in ("unreserved", "reserved", "released"):
    for what in ("spinner", "progressbar", "print", "cell"):
        m = f"MARK {tag} {what}"
        print(f"{m:34} stdout={'X' if m in so else '.'} stderr={'X' if m in se else '.'}")
print("--- META ---")
for line in se.splitlines():
    if line.startswith(("META", "STDOUT-IS-TTY")):
        print(line)
