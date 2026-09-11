"""Exercise reflex_base.utils.log.reserve_stdout() directly.

Writes a marker line for every console/table/rule/spinner/progress/log-record
surface, three times: before reserving stdout, while reserved, and after
releasing it. The runner compares which markers landed on fd 1 vs fd 2.

Run it with the venv python from a NEUTRAL cwd (never the reflex checkout).
"""

import logging
import os
import sys
import threading
import time

import reflex_base

EXPECT = os.environ.get("EXPECT_ENV", "/envs/smoke/")
assert EXPECT in reflex_base.__file__, reflex_base.__file__

from reflex_base.utils import console  # noqa: E402
from reflex_base.utils import log as rlog  # noqa: E402

rlog.enable_managed_logging()
logger = logging.getLogger("reflex_base.reserve_probe")
logger.setLevel(logging.DEBUG)
rlog.set_log_level_by_name = getattr(rlog, "set_log_level_by_name", None)
try:
    from reflex_base.constants import LogLevel

    rlog.set_log_level(LogLevel.DEBUG)
except Exception as e:  # pragma: no cover
    print(f"META set_log_level failed: {e}", file=sys.stderr)


def emit(tag: str) -> None:
    console.print(f"MARK {tag} console.print")
    console.info(f"MARK {tag} console.info")
    console.success(f"MARK {tag} console.success")
    console.warn(f"MARK {tag} console.warn")
    console.error(f"MARK {tag} console.error")
    console.debug(f"MARK {tag} console.debug")
    console.rule(f"MARK {tag} rule")
    console.print_table([[f"MARK {tag} tablecell", "x"]], headers=["h1", "h2"])
    with console.status(f"MARK {tag} status"):
        time.sleep(0.05)
    prog = console.progress()
    print(f"META {tag} progress.disable={prog.disable}", file=sys.stderr)
    with prog:
        t = prog.add_task(f"MARK {tag} progress", total=2)
        prog.update(t, advance=1)
        time.sleep(0.05)
    logger.info(f"MARK {tag} logger.info")
    logger.warning(f"MARK {tag} logger.warning")
    logger.error(f"MARK {tag} logger.error")
    logger.debug(f"MARK {tag} logger.debug")


print(f"META is_stdout_reserved_initial={rlog.is_stdout_reserved()}", file=sys.stderr)
emit("before")

rlog.reserve_stdout()
print(f"META is_stdout_reserved_after_set={rlog.is_stdout_reserved()}", file=sys.stderr)
emit("reserved")

# Nesting: a second reserve then a single release -- is there a depth counter?
rlog.reserve_stdout(True)
rlog.reserve_stdout(True)
rlog.reserve_stdout(False)
print(f"META nested_state_after_2set_1unset={rlog.is_stdout_reserved()}", file=sys.stderr)
console.print("MARK nested console.print")

# Back to reserved for the threading probe.
rlog.reserve_stdout(True)
stop = threading.Event()


def worker():
    console.print("MARK thread console.print")
    logger.info("MARK thread logger.info")
    stop.set()


th = threading.Thread(target=worker, name="probe-worker")
th.start()
th.join(5)
print(f"META thread_ran={stop.is_set()}", file=sys.stderr)

# Release and re-emit.
rlog.reserve_stdout(False)
print(f"META is_stdout_reserved_after_release={rlog.is_stdout_reserved()}", file=sys.stderr)
emit("after")

# Exception safety: nothing scoped, so a raise leaves stdout reserved.
try:
    rlog.reserve_stdout(True)
    raise RuntimeError("boom")
except RuntimeError:
    pass
print(f"META reserved_after_exception={rlog.is_stdout_reserved()}", file=sys.stderr)
console.print("MARK afterexc console.print")
rlog.reserve_stdout(False)

# Is it usable as a context manager, as the name suggests?
try:
    with rlog.reserve_stdout():
        pass
    print("META context_manager=OK", file=sys.stderr)
except Exception as e:
    print(f"META context_manager={type(e).__name__}: {e}", file=sys.stderr)

print("META done", file=sys.stderr)
