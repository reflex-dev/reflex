"""#6933: hammer get_config()/reload_config() from N threads in a fresh process
whose cwd is an app dir whose rxconfig.py imports a sibling module.

Run:  cd <appdir> && <venv>/bin/python .../threads_get_config.py [threads] [mode]
mode: get_config (default) | reload_config | mixed
"""
import os
import sys
import threading
import traceback

import reflex  # noqa: F401
assert "/envs/" in reflex.__file__, reflex.__file__

from reflex_base.config import get_config, reload_config  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 16
MODE = sys.argv[2] if len(sys.argv) > 2 else "get_config"

errors = []
results = []
barrier = threading.Barrier(N)
syspath_seen = []


def work(i: int):
    try:
        barrier.wait()
        for _ in range(5):
            if MODE == "reload_config" or (MODE == "mixed" and i % 2):
                cfg = reload_config()
            else:
                cfg = get_config()
            results.append(cfg.app_name)
            syspath_seen.append(len(sys.path))
    except BaseException as e:  # noqa: BLE001
        errors.append((i, repr(e), traceback.format_exc()))


threads = [threading.Thread(target=work, args=(i,), name=f"w{i}") for i in range(N)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(f"mode={MODE} threads={N} pid={os.getpid()}")
print("reflex:", reflex.__file__)
print("ok_results:", len(results), "distinct:", sorted(set(results)))
print("syspath len range:", min(syspath_seen or [0]), max(syspath_seen or [0]), "final:", len(sys.path))
print("cwd in sys.path at end:", os.getcwd() in sys.path)
print("errors:", len(errors))
for i, e, tb in errors[:3]:
    print(f"--- thread {i}: {e}")
    print(tb)
sys.exit(1 if errors else 0)
