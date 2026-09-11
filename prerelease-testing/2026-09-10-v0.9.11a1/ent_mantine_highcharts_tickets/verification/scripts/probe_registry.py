"""Compare the registry's substate set with the compiler's initial_state snapshot."""
import os
import sys

os.chdir(sys.argv[1])
sys.path.insert(0, os.getcwd())
import reflex  # noqa: E402

assert "/envs/" in reflex.__file__ and "/home/user/reflex/" not in reflex.__file__, reflex.__file__
from reflex.compiler import utils as cutils  # noqa: E402
from reflex.state import State  # noqa: E402
from reflex.utils import prerequisites  # noqa: E402
from reflex_base.registry import RegistrationContext  # noqa: E402

app = prerequisites.get_app(reload=False).app
print("oidc.state in sys.modules:", "reflex_enterprise.auth.oidc.state" in sys.modules)
print("registry substates of State:", sorted(s.get_full_name() for s in State.get_substates()))
reg = RegistrationContext.get()
print("registry id:", id(reg))
print("all registry keys with oidc:", [k for k in reg.base_state_substates if "oidc" in k])
inst = State(_reflex_internal_init=True)
print("instance substates:", sorted(inst.substates))
print("compile_state keys:", sorted(cutils.compile_state(app._state)))
