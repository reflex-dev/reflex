"""Who imports reflex_enterprise.auth.oidc.state, and when relative to compile?"""
import builtins
import os
import sys
import traceback

os.chdir(sys.argv[1])
sys.path.insert(0, os.getcwd())
import reflex  # noqa: E402

assert "/envs/" in reflex.__file__ and "/home/user/reflex/" not in reflex.__file__, reflex.__file__

_real_import = builtins.__import__
seen = []


def traced(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "reflex_enterprise.auth.oidc.state" and name not in sys.modules:
        seen.append(name)
        print("\n>>> IMPORT of", name, "triggered from:")
        for line in traceback.format_stack()[:-1][-14:]:
            print("   ", line.rstrip().replace("\n", " | "))
    return _real_import(name, globals, locals, fromlist, level)


builtins.__import__ = traced
from reflex.utils import prerequisites  # noqa: E402

app_mod = prerequisites.get_app(reload=False)
print("### after app module import, oidc.state imported?", "reflex_enterprise.auth.oidc.state" in sys.modules)
app = app_mod.app
print("### building ASGI app")
_ = app()
print("### after app(), oidc.state imported?", "reflex_enterprise.auth.oidc.state" in sys.modules)
