"""Is the CachedVarOperation AttributeError masking reachable from ordinary
pure-reflex user code (no reflex-enterprise, no hand-written Var subclass)?

LiteralObjectVar._cached_var_name / LiteralArrayVar._cached_var_name call
LiteralVar.create(value) lazily, i.e. INSIDE a cached property. A user-registered
@rx.serializer that raises AttributeError therefore hits the same masking.
"""

import importlib.metadata as md
import json
import sys
import traceback

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__
print("reflex:", md.version("reflex"), "| reflex-base:", md.version("reflex-base"))
print("module:", rx.__file__)
print()

results = {}


class Thing:
    """A user object with a buggy serializer."""


@rx.serializer
def serialize_thing(t: Thing) -> str:
    """Serialize a Thing (buggy on purpose: `.name` does not exist)."""
    return t.name  # noqa  -> AttributeError: 'Thing' object has no attribute 'name'


def report(tag, fn):
    print(f"=== {tag} ===")
    try:
        out = fn()
        print(f"  no exception -> {out!r}")
        results[tag] = {"raised": None, "returned": repr(out)}
    except BaseException as e:  # noqa: BLE001
        tb = traceback.format_exc()
        results[tag] = {
            "raised": f"{type(e).__module__}.{type(e).__name__}",
            "msg": str(e),
            "cause": repr(e.__cause__),
            "real_error_visible": "has no attribute 'name'" in tb,
            "tb": tb.strip().splitlines(),
        }
        print(f"  {results[tag]['raised']}: {results[tag]['msg']}")
        print(f"  __cause__: {results[tag]['cause']}")
        print(f"  real AttributeError visible in traceback: {results[tag]['real_error_visible']}")
    print()


# top level: serializer error is NOT hidden
report("direct_literalvar_create", lambda: str(rx.Var.create(Thing())))

# nested in a dict -> LiteralObjectVar._cached_var_name
report("nested_in_dict_str", lambda: str(rx.Var.create({"a": Thing()})))

# nested in a list -> LiteralArrayVar._cached_var_name
report("nested_in_list_str", lambda: str(rx.Var.create([Thing()])))

# nested dict used as a component prop (the way a real app would hit it)
def as_component_prop():
    """Render a component whose prop is a dict containing the bad object."""
    return rx.box(rx.text("hi"), custom_attrs={"data-x": "y"}, style={"color": Thing()}).render()


report("component_prop_render", as_component_prop)

with open(sys.argv[1], "w") as f:
    json.dump(
        {"reflex": md.version("reflex"), "reflex_base": md.version("reflex-base"), "results": results},
        f,
        indent=2,
    )
print("wrote", sys.argv[1])
