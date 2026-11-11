"""launch.py <logfile> <cwd> <cmd...>: start cmd in its own session (setsid) detached; print its pid."""

import os
import subprocess
import sys

log, cwd, *cmd = sys.argv[1:]
with open(log, "ab") as f:
    p = subprocess.Popen(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
print(p.pid, flush=True)
os._exit(0)
