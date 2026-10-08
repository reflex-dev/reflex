"""Import a lockmod module (fevar / mystate) and report where/how it fails.

Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I run_lockmod.py <fevar|mystate>
"""
import importlib
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lockmod"))
import reflex as rx  # noqa: E402

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

print("reflex", version("reflex"))
name = sys.argv[1]
try:
    mod = importlib.import_module(name)
except Exception as e:  # noqa: BLE001
    tb = traceback.extract_tb(e.__traceback__)
    user = [f for f in tb if f.filename.endswith(f"{name}.py")]
    print(f"IMPORT FAILED: {type(e).__name__}: {e}")
    print("  user frames:", [(os.path.basename(f.filename), f.lineno, f.line) for f in user])
    print("  last frame :", os.path.basename(tb[-1].filename), tb[-1].lineno)
    print("  var name in message:", any(k in str(e) for k in ("holder", "_lock")))
    print("  chained cause/context:", repr(e.__cause__), "|", repr(e.__context__)[:120])
    print("  notes:", getattr(e, "__notes__", None))
    raise SystemExit(0)
print("import OK")
# what a running app does: compile the initial state (root + all substates), then a session touching other vars
from reflex.compiler.utils import compile_state  # noqa: E402

try:
    compile_state(rx.State)
    print("compile_state(rx.State): OK")
except Exception as e:  # noqa: BLE001
    print(f"compile_state(rx.State) FAILED: {type(e).__name__}: {e}")
cls = getattr(mod, "CacheState", None)
if cls is not None:
    try:
        s = cls(_reflex_internal_init=True)
        print("instance OK; hits =", s.hits)
        try:
            s.hits += 1
            print("touch other var OK:", s.hits)
        except Exception as e:  # noqa: BLE001
            print("touch other var FAILED", type(e).__name__, e)
        try:
            s._lock
            print("access _lock OK")
        except Exception as e:  # noqa: BLE001
            print(f"access _lock FAILED: {type(e).__name__}: {e}")
    except Exception as e:  # noqa: BLE001
        print(f"instance FAILED: {type(e).__name__}: {e}")
