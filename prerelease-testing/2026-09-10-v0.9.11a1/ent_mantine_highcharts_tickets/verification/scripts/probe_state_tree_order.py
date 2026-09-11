"""When do the OIDC auth substates join the state tree, relative to compile?"""
import os
import sys

os.chdir(sys.argv[1])
sys.path.insert(0, os.getcwd())
import reflex  # noqa: E402

assert "/envs/" in reflex.__file__ and "/home/user/reflex/" not in reflex.__file__, reflex.__file__
print("reflex:", reflex.__file__)

from reflex.state import State  # noqa: E402


def names():
    return sorted(s.get_full_name() for s in State._get_all_substate_classes()) if hasattr(State, "_get_all_substate_classes") else sorted(s.get_full_name() for s in State.get_substates())


print("modules with oidc loaded before app import:", [m for m in sys.modules if "oidc" in m])
from reflex.utils import prerequisites  # noqa: E402

app_mod = prerequisites.get_app(reload=False)
print("after get_app: oidc modules:", [m for m in sys.modules if "auth.oidc" in m or m.endswith("auth.enforcement")])
print("after get_app substates:", names())
app = app_mod.app
print("--- now build the ASGI app / api (what serving does) ---")
_ = app()
print("after app(): oidc modules:", [m for m in sys.modules if "auth.oidc" in m or m.endswith("auth.enforcement")])
print("after app() substates:", names())
