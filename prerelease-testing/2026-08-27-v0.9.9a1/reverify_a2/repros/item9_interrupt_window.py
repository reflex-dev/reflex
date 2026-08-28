"""Item 9: PR #6994 interrupt-window semantics against the INSTALLED a2 package.

Standalone adaptation of two regression tests from tests/units/utils/test_processes.py:
  A) test_run_concurrently_context_unblocks_main_thread_on_task_failure
  B) test_run_concurrently_context_no_interrupt_after_body_exception
"""
import sys, threading, time
import reflex
assert "site-packages" in reflex.__file__ and "envs/" in reflex.__file__, reflex.__file__
print("reflex.__file__:", reflex.__file__)
from reflex.utils.processes import run_concurrently_context

DEFAULT_TIMEOUT = 30
rc = {"A": False, "B": False}

def _raise_system_exit():
    raise SystemExit(1)

# --- Test A: SystemExit in a task promptly unblocks a blocked with-body ---
def test_A():
    block = threading.Event()
    start = time.monotonic()
    raised = None
    try:
        with run_concurrently_context(_raise_system_exit):
            block.wait(timeout=10)  # simulate backend blocking main thread
    except SystemExit as e:
        raised = e
    elapsed = time.monotonic() - start
    ok = raised is not None and elapsed < 5
    print(f"[A] SystemExit propagated={raised is not None} elapsed={elapsed:.3f}s (<5 required) -> {'PASS' if ok else 'FAIL'}")
    rc["A"] = ok

# --- Test B: a task failing AFTER the body raised must not deliver a stray KeyboardInterrupt ---
def test_B():
    task_may_fail = threading.Event()
    interrupt_callback_ran = threading.Event()

    def _fail_on_release():
        task_may_fail.wait(timeout=DEFAULT_TIMEOUT)
        raise SystemExit(1)

    body_err = None
    stray_kbd = None
    try:
        try:
            with run_concurrently_context(_fail_on_release) as tasks:
                tasks[0].add_done_callback(lambda _t: interrupt_callback_ran.set())
                raise ValueError("body failed")
        except ValueError as e:
            body_err = e
        # context unwound; now release the task so it fails late
        task_may_fail.set()
        assert interrupt_callback_ran.wait(timeout=DEFAULT_TIMEOUT), "worker task did not finish"
        # a stray interrupt would surface here as KeyboardInterrupt
        time.sleep(0.3)
    except KeyboardInterrupt as e:
        stray_kbd = e
    ok = (body_err is not None) and (stray_kbd is None)
    print(f"[B] body ValueError propagated={body_err is not None} stray_KeyboardInterrupt={stray_kbd is not None} -> {'PASS' if ok else 'FAIL'}")
    rc["B"] = ok

test_A()
test_B()
print("RESULT:", "ALL-PASS" if all(rc.values()) else f"FAIL {rc}")
sys.exit(0 if all(rc.values()) else 1)
