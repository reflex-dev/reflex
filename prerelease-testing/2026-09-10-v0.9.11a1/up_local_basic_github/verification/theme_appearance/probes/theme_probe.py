"""Independent probe: does rx.theme(appearance=...) survive into the rendered tag?"""
import json
import sys
from importlib.metadata import version

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__
info = {
    "reflex": rx.constants.Reflex.VERSION,
    "reflex_file": rx.__file__,
    "radix": version("reflex-components-radix"),
}
print(json.dumps(info, indent=2))


class ProbeState(rx.State):
    ap: str = "dark"


cases = {
    "appearance='dark'": lambda: rx.theme(rx.text("hi"), appearance="dark"),
    "color_mode='dark'": lambda: rx.theme(rx.text("hi"), color_mode="dark"),
    "appearance=State.var": lambda: rx.theme(rx.text("hi"), appearance=ProbeState.ap),
    "accent_color='red' CONTROL": lambda: rx.theme(rx.text("hi"), accent_color="red"),
    "has_background=False CONTROL": lambda: rx.theme(rx.text("hi"), has_background=False),
    "appearance='dark'+accent": lambda: rx.theme(rx.text("hi"), appearance="dark", accent_color="red"),
}
out = {}
for name, f in cases.items():
    comp = f()
    tag = comp._render()
    rendered = comp.render()
    props = rendered.get("props", [])
    # also check the raw component attribute
    attr = getattr(comp, "appearance", None)
    out[name] = {
        "component_appearance_attr": str(attr),
        "rendered_props": props,
        "appearance_in_props": any("appearance" in p.lower() for p in props),
        "full_render_str": str(rendered)[:500],
    }
    print(f"\n--- {name}")
    print("   comp.appearance =", attr)
    print("   rendered props  =", props)

print("\nSUMMARY:", json.dumps({k: v["appearance_in_props"] for k, v in out.items()}))
if len(sys.argv) > 1:
    with open(sys.argv[1], "w") as fh:
        json.dump({"info": info, "cases": out}, fh, indent=2)
