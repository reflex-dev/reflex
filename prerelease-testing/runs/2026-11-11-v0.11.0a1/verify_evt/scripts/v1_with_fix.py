"""Run v1_double_event.py with a patched scratch copy of reflex_base first on sys.path (demonstrates the fix shape)."""
import os, runpy, sys
sys.path.insert(0, os.environ["FIXLIB"])
import reflex_base
assert os.environ["FIXLIB"] in reflex_base.__file__, reflex_base.__file__
sys.argv = [sys.argv[1]]
runpy.run_path(sys.argv[0], run_name="__main__")
