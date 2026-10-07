import sys
import reflex as rx
venv = sys.argv[1]
assert f"/scratchpad/envs/{venv}/" in rx.__file__, rx.__file__
import importlib.metadata as m
print("version", m.version("reflex"))
for mod, name in [("reflex.vars", "VarData"), ("reflex.vars.base", "VarData"), ("reflex_base.vars.base", "VarData"), ("reflex.utils.imports", "ImportVar"), ("reflex_base.utils.imports", "ImportVar")]:
    try:
        exec(f"from {mod} import {name}")
        print("ok", mod, name)
    except Exception as e:
        print("no", mod, name, type(e).__name__)
print("has client_state", hasattr(rx._x, "client_state"))
class S(rx.State):
    items: list[int] = [0, 1, 2, 3]
    step: int = 2
    d: dict[str, int] = {"x": 1}
    key: str = "x"
    rows: list[dict[str, str]] = [{"name": "b"}]
for label, f in [
    ("step_var_slice", lambda: S.items[::S.step]),
    ("neg1", lambda: S.items[-1::-1]),
    ("pluck", lambda: S.rows.pluck("name")),
    ("reverse", lambda: S.items.reverse()),
    ("sort", lambda: S.items.sort()),
    ("dict_items", lambda: S.d.items()),
    ("dict_entries", lambda: S.d.entries()),
    ("objkey_var", lambda: S.d[S.key]),
    ("deep_equals", lambda: S.d.deep_equals({"x": 1})),
]:
    try:
        v = f()
        print(f"[{label}] OK {str(v)[:150]}")
    except BaseException as e:
        print(f"[{label}] ERR {type(e).__name__}: {str(e)[:150]}")
