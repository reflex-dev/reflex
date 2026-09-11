"""Serializer-level probe for the bundled-library dynamic-component claims.

Run with any reflex venv python, from a NEUTRAL cwd (not /home/user/reflex):
    <venv>/bin/python serializer_probe.py

Checks, without any server/browser:
1. bundle_library('lucide-react') at "import time" -> present in context list.
2. reset_bundled_libraries() (what compile_app does at the start of a frontend
   compile) wipes it back to defaults -> user registration lost.
3. With lucide-react registered (backend-worker situation), serializing a
   component containing rx.icon('apple') emits a BARE subpath specifier
   `from "lucide-react/dist/esm/icons/apple.mjs"` that the window-rewrite loop
   never touches -> guaranteed browser TypeError in the eval'd data-URI module.
4. Without lucide-react registered, the same import goes to the jsdelivr CDN.
"""

import sys

import reflex as rx
from reflex.components.dynamic import bundle_library, reset_bundled_libraries

print("reflex version:", rx.constants.Reflex.VERSION)

from reflex.components import dynamic as _dyn

if hasattr(_dyn, "bundled_libraries"):  # 0.9.8: module-level list

    def current_bundled():
        return list(_dyn.bundled_libraries)
else:  # 0.9.9a1: context attribute
    from reflex_base.registry import RegistrationContext

    def current_bundled():
        return list(RegistrationContext.ensure_context().bundled_libraries)

from reflex.utils.serializers import serialize

baseline = current_bundled()
print("default bundled:", baseline)

bundle_library("lucide-react")
after_user = current_bundled()
print("after user bundle_library:", after_user)
assert "lucide-react" in after_user, "bundle_library had no effect at all"

component = rx.vstack(rx.icon("apple"), rx.text("hi"))
code = serialize(component)
assert isinstance(code, str)

bare_line = next(
    (line for line in code.splitlines() if "lucide-react/dist" in line), None
)
cdn_line = next(
    (line for line in code.splitlines() if "cdn.jsdelivr.net" in line and "lucide" in line),
    None,
)
window_line = next(
    (line for line in code.splitlines() if "__reflex" in line and "lucide" in line), None
)
print("\n--- serialized with lucide-react REGISTERED (backend-worker context) ---")
print("bare subpath import line:", bare_line)
print("cdn import line:", cdn_line)
print("window rewrite line:", window_line)

subpath_broken = (
    bare_line is not None
    and bare_line.lstrip().startswith("import ")
    and 'from "lucide-react/dist' in bare_line
)
print("VERDICT subpath-not-rewritten:", subpath_broken)

# Now simulate what compile_app() does at the start of every frontend compile.
reset_bundled_libraries()
after_reset = current_bundled()
print("\nafter reset_bundled_libraries (compile_app behavior):", after_reset)
wiped = "lucide-react" not in after_reset
print("VERDICT user registration wiped by reset:", wiped)

code2 = serialize(rx.vstack(rx.icon("apple")))
cdn_line2 = next(
    (line for line in code2.splitlines() if "cdn.jsdelivr.net" in line and "lucide" in line),
    None,
)
bare_line2 = next(
    (
        line
        for line in code2.splitlines()
        if 'from "lucide-react' in line and "cdn" not in line
    ),
    None,
)
print("\n--- serialized with lucide-react NOT registered (post-reset context) ---")
print("cdn import line:", cdn_line2)
print("bare import line:", bare_line2)

sys.exit(0 if (subpath_broken and wiped) else 1)
