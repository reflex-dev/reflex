"""#6933 stress: N threads load the config while M threads plainly import the
project-local sibling module that rxconfig.py depends on.

_get_config() evicts rxconfig's project-local deps from sys.modules and removes
its sys.path entry when it is done, so a plain `import sibling_settings` racing
that window is the shape that used to raise ModuleNotFoundError.

Run from the app dir:  <venv>/bin/python threads_config_vs_import.py [loaders] [importers] [rounds]
"""
import importlib
import os
import sys
import threading
import traceback

import reflex  # noqa: F401
assert "/envs/" in reflex.__file__, reflex.__file__
from reflex_base.config import reload_config  # noqa: E402

LOADERS = int(sys.argv[1]) if len(sys.argv) > 1 else 8
IMPORTERS = int(sys.argv[2]) if len(sys.argv) > 2 else 8
ROUNDS = int(sys.argv[3]) if len(sys.argv) > 3 else 40

sys.path.insert(0, os.getcwd())  # what a user's own code would rely on

errors = []
ok = {"load": 0, "import": 0}
lock = threading.Lock()
barrier = threading.Barrier(LOADERS + IMPORTERS)


def loader(i):
    try:
        barrier.wait()
        for _ in range(ROUNDS):
            reload_config()
            with lock:
                ok["load"] += 1
    except BaseException as e:  # noqa: BLE001
        with lock:
            errors.append(("loader", i, repr(e), traceback.format_exc()))


def importer(i):
    try:
        barrier.wait()
        for _ in range(ROUNDS):
            m = importlib.import_module("sibling_settings")
            assert m.APP_NAME == "cfgapp"
            with lock:
                ok["import"] += 1
    except BaseException as e:  # noqa: BLE001
        with lock:
            errors.append(("importer", i, repr(e), traceback.format_exc()))


ts = [threading.Thread(target=loader, args=(i,), name=f"L{i}") for i in range(LOADERS)]
ts += [threading.Thread(target=importer, args=(i,), name=f"I{i}") for i in range(IMPORTERS)]
for t in ts:
    t.start()
for t in ts:
    t.join()

print(f"RESULT loaders={LOADERS} importers={IMPORTERS} rounds={ROUNDS} "
      f"ok_load={ok['load']} ok_import={ok['import']} errors={len(errors)}")
for kind, i, e, tb in errors[:3]:
    print(f"--- {kind} {i}: {e}")
    print(tb)
sys.exit(1 if errors else 0)
