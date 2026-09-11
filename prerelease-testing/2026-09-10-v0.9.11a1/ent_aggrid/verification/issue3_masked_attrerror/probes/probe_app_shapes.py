"""Which ordinary app-level shapes hit the masked-AttributeError path?"""

import importlib.metadata as md
import json
import sys
import traceback

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__
print("reflex:", md.version("reflex"), "| reflex-base:", md.version("reflex-base"))

results = {}


class Point:
    """A user domain object."""

    def __init__(self, x: int):
        self.x = x


@rx.serializer
def serialize_point(p: Point) -> str:
    """Buggy serializer: `.label` does not exist."""
    return p.label  # noqa


def report(tag, fn):
    try:
        out = fn()
        results[tag] = {"raised": None, "returned": repr(out)[:120]}
    except BaseException as e:  # noqa: BLE001
        tb = traceback.format_exc()
        results[tag] = {
            "raised": f"{type(e).__module__}.{type(e).__name__}",
            "msg": str(e)[:200],
            "cause": repr(e.__cause__),
            "real_error_visible": "has no attribute 'label'" in tb,
        }
    r = results[tag]
    flag = "MASKED" if (r["raised"] and not r["real_error_visible"]) else ("ok" if r["raised"] else "no-exc")
    print(f"{flag:7} {tag}: {r['raised']}: {r.get('msg','')}")


report("custom_attrs_list", lambda: rx.box(custom_attrs={"data-p": [Point(1)]}).render())
report("custom_attrs_dict", lambda: rx.box(custom_attrs={"data-p": {"a": Point(1)}}).render())
report("style_list", lambda: rx.box(style={"gridTemplateColumns": [Point(1)]}).render())
report("foreach_literal_list", lambda: rx.foreach([Point(1)], lambda p: rx.text(p.to_string())).render())
report("var_create_list_str", lambda: str(rx.Var.create([Point(1)])))
report("var_create_list_json", lambda: rx.Var.create([Point(1)]).json())
report("var_create_nested_list_str", lambda: str(rx.Var.create({"k": [Point(1)]})))
report("var_create_tuple_str", lambda: str(rx.Var.create((Point(1),))))
report("cond_list", lambda: str(rx.cond(True, [Point(1)], [])))


class ListState(rx.State):
    """State holding a list of user objects."""

    pts: list[Point] = []


report("state_default_list", lambda: str(ListState.pts))
report("state_setvar_list", lambda: str(rx.Var.create([Point(2)]) + ListState.pts))

with open(sys.argv[1], "w") as f:
    json.dump({"reflex": md.version("reflex"), "results": results}, f, indent=2)
print("wrote", sys.argv[1])
