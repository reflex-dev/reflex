"""No-server probe: does `rx.theme(appearance=...)` reach the compiled JSX?

Run with the python of any venv that has reflex installed, from a NEUTRAL cwd
(never /home/user/reflex, which shadows the installed package):

    cd $SB && $SB/envs/base0910/bin/python apps/up_local_basic_github/probes/theme_appearance_probe.py
    cd $SB && $SB/envs/smoke/bin/python    apps/up_local_basic_github/probes/theme_appearance_probe.py
"""

import json
import re
import sys

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__
print("reflex:", rx.constants.Reflex.VERSION, rx.__file__)
try:
    from importlib.metadata import version

    print("reflex-components-radix:", version("reflex-components-radix"))
except Exception as e:  # noqa: BLE001
    print("radix version unknown:", e)


class S(rx.State):
    appearance: str = "dark"


cases = {
    "static appearance='dark'": rx.theme(rx.text("hi"), appearance="dark"),
    "static color_mode='dark'": rx.theme(rx.text("hi"), color_mode="dark"),
    "Var appearance=S.appearance": rx.theme(rx.text("hi"), appearance=S.appearance),
    "static accent_color='red' (control)": rx.theme(rx.text("hi"), accent_color="red"),
}

out = {}
for name, comp in cases.items():
    rendered = str(comp.render())
    props = re.findall(r'"([a-zA-Z_]+)":', rendered)
    has_appearance = "appearance" in rendered
    out[name] = {
        "appearance_in_render": has_appearance,
        "render_head": rendered[:400],
    }
    print(f"\n--- {name}\n  appearance present in render: {has_appearance}")
    print("  render:", rendered[:300].replace("\n", " "))

print("\nSUMMARY:", json.dumps({k: v["appearance_in_render"] for k, v in out.items()}))
if len(sys.argv) > 1:
    with open(sys.argv[1], "w") as f:
        json.dump(out, f, indent=2)
