"""Claim D: where console.deprecate locations point, per scenario.

Usage: <venv>/bin/python -u derive_d.py <expected-venv-name> <scenario>
Scenarios: direct, exec, model_here, model_import, both_models, memo, env, pkg_model
"""

import os
import sys

if sys.argv[2] == "env":
    os.environ["REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS"] = "1"
import reflex as rx  # noqa: E402

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
scenario = sys.argv[2]
print(f"--- scenario {scenario}", flush=True)
if scenario == "direct":
    rx.Var.create([1, 2]).foreach(lambda x: x)
elif scenario == "exec":
    exec("import reflex as rx\nrx.Var.create([3]).foreach(lambda x: x)\n")
elif scenario in ("model_here", "both_models"):

    class UserModelHere(rx.Model, table=True):
        x: int = 0

    if scenario == "both_models":
        import um_model  # noqa: F401  (second model, different user file)
elif scenario == "model_import":
    import um_model  # noqa: F401
elif scenario == "memo":

    @rx.memo
    def my_memo(x):
        return rx.text(x)

elif scenario == "env":
    from reflex_base import environment

    fn = getattr(environment, "state_manager_disk_debounce", None)
    print("state_manager_disk_debounce exists:", fn is not None, flush=True)
    if fn:
        print("value:", fn(), flush=True)
elif scenario == "pkg_model":
    import reflex_magic_link_auth  # noqa: F401
print("--- end", flush=True)
