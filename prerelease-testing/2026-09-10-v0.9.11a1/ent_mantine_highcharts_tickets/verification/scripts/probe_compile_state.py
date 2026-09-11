"""What substates does the compiler's initial_state snapshot contain?"""
import os
import sys

os.chdir(sys.argv[1])
sys.path.insert(0, os.getcwd())
import reflex  # noqa: E402

assert "/envs/" in reflex.__file__ and "/home/user/reflex/" not in reflex.__file__, reflex.__file__
from reflex.compiler import utils as cutils  # noqa: E402
from reflex.utils import prerequisites  # noqa: E402

app = prerequisites.get_app(reload=False).app
print("app._state:", app._state)
keys = sorted(cutils.compile_state(app._state))
print("compile_state keys:")
for k in keys:
    print("   ", k)
