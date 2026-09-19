import os, sys, traceback, importlib
import reflex
assert os.environ["EXPECT_VENV"] in reflex.__file__, reflex.__file__
d, mod = sys.argv[1], sys.argv[2]
root = os.path.dirname(os.path.abspath(__file__))
appdir = os.path.join(root, d)
sys.path.insert(0, appdir); os.chdir(appdir)
try:
    importlib.import_module(f"{mod}.{mod}")
    print(f"OK   {d}")
except Exception as e:
    print(f"FAIL {d}: {type(e).__name__}: {e}")
    traceback.print_exc(limit=8)
