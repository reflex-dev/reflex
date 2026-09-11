
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
