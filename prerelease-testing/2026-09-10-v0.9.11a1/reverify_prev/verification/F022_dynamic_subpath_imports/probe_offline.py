"""Offline probe: dynamic-component serializer vs. subpath (package_path) imports.

Run from a neutral cwd with a venv python. No server, no browser.
"""
import sys

import reflex
assert "/envs/" in reflex.__file__, reflex.__file__
print("reflex:", reflex.__file__, reflex.constants.Reflex.VERSION)

import reflex as rx
from reflex_base.components.dynamic import (
    bundle_library,
    reset_bundled_libraries,

)
from reflex_base.registry import RegistrationContext
from reflex_base.utils.serializers import serialize

# serializer already loaded by `import reflex`
ctx = RegistrationContext.ensure_context()


def show(label, comp):
    code = serialize(comp)
    print(f"\n----- {label} -----")
    print("bundled_libraries:", ctx.bundled_libraries)
    for line in str(code).splitlines():
        if "lucide" in line or "recharts" in line or line.startswith(("import ", "const ")):
            print("   ", line)


# A: pristine context, icon in a dynamic component
show("A no bundle_library / rx.icon", rx.vstack(rx.icon("apple"), rx.text("hi")))

# B: user-level bundle_library, as the docs show
bundle_library("lucide-react")
show("B after bundle_library('lucide-react')", rx.vstack(rx.icon("apple"), rx.text("hi")))

# C: what compile_app() does at the start of every frontend compile
reset_bundled_libraries()
show("C after reset_bundled_libraries()", rx.vstack(rx.icon("apple"), rx.text("hi")))

# D: control - a bundled library WITHOUT a subpath import
class Plain(rx.Component):
    library = "some-lib@1.2.3"
    tag = "Plain"

bundle_library("some-lib")
show("D bundled lib, no subpath (control)", rx.vstack(Plain.create(), rx.text("hi")))

reset_bundled_libraries()
show("E unbundled lib, no subpath (control, CDN)", rx.vstack(Plain.create(), rx.text("hi")))


# F: any component using ImportVar(package_path=...) shows the same two bad forms,
#    so the defect is general to package_path, not specific to lucide icons.
from reflex_base.utils.imports import ImportVar


class Sub(rx.Component):
    """Component importing from a subpath of its library."""

    library = "my-lib@2.0.0"
    tag = "Widget"

    def _get_imports(self):
        imports_ = super()._get_imports()
        imports_.pop(self.library, None)
        imports_["my-lib@2.0.0"] = [ImportVar("Widget", package_path="/sub/mod.mjs")]
        return imports_


reset_bundled_libraries()
show("F package_path, NOT bundled (CDN branch)", rx.vstack(Sub.create()))
bundle_library("my-lib")
show("F package_path, bundled (window branch)", rx.vstack(Sub.create()))
